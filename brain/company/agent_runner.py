"""Role-scoped execution for Brain's software-company workflow."""

import json
import re
from typing import Any

from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.roles import ROLE_BY_KEY
from brain.company.workflow import validate_stage_entry


class AgentOutputError(ValueError):
    """Raised when a specialist returns malformed structured output."""


_DECISION_VALUES = {
    "review_decision": {"PASS", "APPROVED", "NEEDS_WORK", "BLOCKED"},
    "security_decision": {"PASS", "APPROVED", "NEEDS_WORK", "BLOCKED"},
    "customer_review": {"PASS", "APPROVED", "NEEDS_WORK", "BLOCKED"},
    "release_decision": {"PASS", "READY_FOR_HUMAN_APPROVAL", "NEEDS_WORK", "BLOCKED"},

}


_SOURCE_BUDGET_CHARS = 90000
_ARCHITECT_SOURCE_BUDGET_CHARS = 30000
_REVIEW_DIFF_BUDGET_CHARS = 60000
_OTHER_DIFF_BUDGET_CHARS = 30000
_SOURCE_INDEX_LIMIT = 160
_SOURCE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\."
    r"(?:py|md|yml|yaml|json|toml|ts|tsx|js|jsx|html|css)(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)


def _compact_source_manifest(manifest: Any) -> dict[str, Any]:
    """Keep coverage facts and a bounded path index, not repeated full inventories."""
    if not isinstance(manifest, dict):
        return {}
    candidates = manifest.get("candidate_paths", [])
    read_paths = manifest.get("read_paths", [])
    failed_paths = manifest.get("failed_paths", {})
    omitted = manifest.get("omitted_by_aggregate_budget", [])
    return {
        "candidate_count": manifest.get("candidate_count", len(candidates) if isinstance(candidates, list) else None),
        "read_count": manifest.get("read_count"),
        "coverage_complete": manifest.get("coverage_complete"),
        "tree_truncated": manifest.get("tree_truncated"),
        "aggregate_bytes_read": manifest.get("aggregate_bytes_read"),
        "aggregate_byte_limit": manifest.get("aggregate_byte_limit"),
        "failed_path_count": len(failed_paths) if isinstance(failed_paths, dict) else None,
        "omitted_path_count": len(omitted) if isinstance(omitted, list) else None,
        "candidate_paths": candidates[:_SOURCE_INDEX_LIMIT] if isinstance(candidates, list) else [],
        "read_paths": read_paths[:_SOURCE_INDEX_LIMIT] if isinstance(read_paths, list) else [],
    }


def _select_source_contents(
    source_contents: Any,
    user_request: str,
    changed_files: Any = None,
    max_chars: int = _SOURCE_BUDGET_CHARS,
    planned_files: Any = None,
) -> dict[str, str]:
    """Select complete, task-relevant files under a strict prompt budget."""
    if not isinstance(source_contents, dict):
        return {}
    changed = {str(path) for path in changed_files} if isinstance(changed_files, list) else set()
    planned = {str(path) for path in planned_files if isinstance(path, str)} if isinstance(planned_files, list) else set()
    request_lower = user_request.casefold()
    explicit_paths = set(_SOURCE_PATH_RE.findall(user_request)) | planned | changed
    request_tokens = set(re.findall(r"[a-z0-9]+", request_lower))
    scored: list[tuple[int, int, str, str]] = []
    for raw_path, raw_content in source_contents.items():
        if not isinstance(raw_path, str) or not isinstance(raw_content, str):
            continue
        path = raw_path.replace("\\", "/")
        lower_path = path.casefold()
        path_tokens = set(re.findall(r"[a-z0-9]+", lower_path))
        score = 3 * len(request_tokens.intersection(path_tokens))
        if path in explicit_paths or lower_path in {item.casefold() for item in explicit_paths}:
            score += 1000
        if path in changed:
            score += 500
        if path in {"README.md", "pyproject.toml", "package.json"}:
            score += 5
        if path.startswith(".github/workflows/") and request_tokens.intersection(
            {"workflow", "workflows", "github", "actions", "ci", "check", "test", "browser", "chat", "gemini", "secret", "provider"}
        ):
            score += 12
        if path.startswith("tests/") and request_tokens.intersection(
            {"test", "tests", "verify", "verification", "check", "smoke", "ci"}
        ):
            score += 10
        if path.startswith("docs/") and request_tokens.intersection(
            {"doc", "docs", "report", "runtime", "status", "verification", "operational"}
        ):
            score += 10
        scored.append((score, len(raw_content), path, raw_content))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    has_relevant_paths = any(score > 0 for score, _, _, _ in scored)
    selected: dict[str, str] = {}
    used = 0
    for score, size, path, content in scored:
        if has_relevant_paths and score <= 0:
            continue
        explicit = path in explicit_paths or path in changed
        per_file_limit = 60000 if explicit else 25000
        if size > per_file_limit or used + size > max_chars:
            continue
        selected[path] = content
        used += size
        if used >= max_chars:
            break
    return selected


def _prepare_prompt_evidence(
    role_key: str,
    user_request: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build role-specific evidence views so the same multi-megabyte repo is not repeated."""
    prepared = dict(evidence)
    snapshot = evidence.get("repository_snapshot")
    if isinstance(snapshot, dict):
        manifest = snapshot.get("source_manifest", {})
        source_contents = snapshot.get("source_contents", {})
        files = snapshot.get("files", [])
        file_index = [
            item.get("path")
            for item in files
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ][: _SOURCE_INDEX_LIMIT] if isinstance(files, list) else []
        snapshot_view = {
            key: snapshot[key]
            for key in ("repository", "default_branch", "base_commit", "truncated", "source_files_read")
            if key in snapshot
        }
        snapshot_view["file_index"] = file_index
        snapshot_view["source_manifest"] = _compact_source_manifest(manifest)
        explicit_context_paths = set(_SOURCE_PATH_RE.findall(user_request))
        planned_paths = evidence.get("file_plan", [])
        changed_paths = evidence.get("changed_files", [])
        if isinstance(planned_paths, list):
            explicit_context_paths.update(path for path in planned_paths if isinstance(path, str))
        if isinstance(changed_paths, list):
            explicit_context_paths.update(path for path in changed_paths if isinstance(path, str))
        if role_key in {"architect", "developer"}:
            budget = _ARCHITECT_SOURCE_BUDGET_CHARS if role_key == "architect" else _SOURCE_BUDGET_CHARS
            selected = _select_source_contents(
                source_contents,
                user_request,
                evidence.get("changed_files"),
                max_chars=budget,
                planned_files=evidence.get("file_plan"),
            )
            snapshot_view["source_contents"] = selected
            snapshot_view["source_selection"] = {
                "selected_file_count": len(selected),
                "selected_chars": sum(len(content) for content in selected.values()),
                "budget_chars": budget,
                "omitted_explicit_paths": sorted(
                    path
                    for path in explicit_context_paths
                    if path in {
                        item.get("path")
                        for item in files
                        if isinstance(item, dict) and isinstance(item.get("path"), str)
                    }
                    and path not in selected
                ),
                "note": "Only complete files selected by task relevance are supplied; use the manifest to identify omitted context.",
            }
        elif role_key == "code_reviewer":
            changed = evidence.get("changed_files", [])
            if not isinstance(changed, list):
                changed = []
            selected = {
                path: source_contents[path]
                for path in changed
                if isinstance(path, str)
                and isinstance(source_contents, dict)
                and isinstance(source_contents.get(path), str)
                and len(source_contents[path]) <= _REVIEW_DIFF_BUDGET_CHARS
            } if isinstance(source_contents, dict) else {}
            snapshot_view["source_contents"] = selected
        prepared["repository_snapshot"] = snapshot_view

    change_set = prepared.get("change_set")
    if isinstance(change_set, dict):
        files = change_set.get("files", [])
        prepared["change_set"] = {
            "summary": change_set.get("summary"),
            "files": [
                {
                    "path": item.get("path"),
                    "content_chars": len(item.get("content", "")) if isinstance(item, dict) and isinstance(item.get("content"), str) else None,
                }
                for item in files
                if isinstance(files, list) and isinstance(item, dict)
            ][:30],
        }

    actual_diff = prepared.get("actual_diff")
    if isinstance(actual_diff, str):
        prepared["actual_diff_truncated"] = False
        prepared["actual_diff_original_chars"] = len(actual_diff)
        limit = _REVIEW_DIFF_BUDGET_CHARS if role_key == "code_reviewer" else _OTHER_DIFF_BUDGET_CHARS
        if len(actual_diff) > limit:
            omitted_chars = len(actual_diff) - limit
            prepared["actual_diff_truncated"] = True
            prepared["actual_diff"] = actual_diff[:limit] + f"\n[DIFF TRUNCATED: {omitted_chars} characters omitted from this role's context.]"
            if role_key in {"code_reviewer", "qa_engineer", "security_auditor", "customer_advocate", "release_manager"}:
                prepared["diff_review_blocked"] = True
    return prepared


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse a strict JSON object; do not silently accept prose as a deliverable."""
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        if value.endswith("```"):
            value = value[:-3].strip()
        if value.startswith("json\n"):
            value = value[5:].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"Specialist output is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AgentOutputError("Specialist output must be a JSON object.")
    return parsed


def _validate_specialist_output(raw: str, role: Any) -> dict[str, Any]:
    """Parse and validate the complete specialist contract without accepting partial output."""
    result = _parse_json_object(raw)
    if result.get("status") not in {"PASS", "NEEDS_WORK", "BLOCKED"}:
        raise AgentOutputError("Specialist status must be PASS, NEEDS_WORK, or BLOCKED.")
    if not isinstance(result.get("deliverables"), dict):
        raise AgentOutputError("Specialist must return a deliverables object.")
    missing_deliverables = [
        key for key in role.deliverables if key not in result["deliverables"]
    ]
    if missing_deliverables:
        raise AgentOutputError(
            "Specialist omitted required deliverables: " + ", ".join(missing_deliverables)
        )
    for key in ("findings", "blockers", "evidence_needed"):
        if not isinstance(result.get(key), list):
            raise AgentOutputError(f"Specialist field '{key}' must be an array.")
    for key in role.deliverables:
        if key not in _DECISION_VALUES:
            continue
        decision = result["deliverables"].get(key)
        if not isinstance(decision, str) or decision.strip().upper() not in _DECISION_VALUES[key]:
            allowed = ", ".join(sorted(_DECISION_VALUES[key]))
            raise AgentOutputError(
                f"Specialist deliverable '{key}' must be one of: {allowed}."
            )
    return result


class SpecialistAgentRunner:
    """Run one named specialist with explicit prerequisites and structured output."""

    def __init__(self, provider: OpenAICompatibleProvider):
        self.provider = provider

    async def run(
        self,
        role_key: str,
        user_request: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        validate_stage_entry(role_key, evidence)
        role = ROLE_BY_KEY[role_key]
        role_contract = ""
        if role_key == "developer":
            role_contract = (
                "\nImplementation contract: deliverables.change_set must be an object with "
                "a short 'summary' string and a 'files' array. Each array item must contain "
                "a safe repository-relative 'path' and complete UTF-8 text 'content'. "
                "Return 1–30 files, each at most 200 KB. Do not claim to have applied changes; "
                "the repository tool will commit them on an isolated branch. Only replace an existing "
                "file when its complete original contents are present in repository_snapshot.source_contents. "
                "If a requested existing file is omitted from that context, return BLOCKED and request its "
                "complete contents in evidence_needed; never reconstruct an omitted file from memory.\n"
            )
        elif role_key == "qa_engineer":
            role_contract = (
                "\nUse the supplied test_results from the real check runner. Do not invent "
                "test runs or mark unexecuted checks as passing.\n"
            )
        decision_field = next(
            (key for key in role.deliverables if key in _DECISION_VALUES), None
        )
        if decision_field:
            allowed = ", ".join(sorted(_DECISION_VALUES[decision_field]))
            role_contract += (
                f"\nMachine-readable decision contract: deliverables.{decision_field} "
                f"must be exactly one of these enum values: {allowed}. Do not put a sentence, "
                "summary, or explanation in this field. Put reasoning in findings, blockers, "
                "evidence_needed, or the role's separate explanatory deliverables.\n"
            )
        if role_key in {"code_reviewer", "qa_engineer", "security_auditor", "customer_advocate", "release_manager"}:
            role_contract += (
                "\nDiff completeness rule: if diff_review_blocked is true or actual_diff_truncated is true, "
                "do not approve this gate. Return BLOCKED or NEEDS_WORK and identify the missing diff evidence.\n"
            )
        if role_key in {"ux_designer", "customer_advocate"}:
            role_contract += (
                "\nScope applicability rule: adapt deliverables to the explicit request. "
                "For backend-only, documentation-only, test-only, configuration-only, "
                "infrastructure-only work, or a request that explicitly excludes UI changes, "
                "do not block because visual mockups, screen redesign, a visual design system, "
                "or user journey diagrams are out of scope. Describe only relevant user impact "
                "and place concise non-UI interaction details in required fields where applicable; "
                "mark purely visual details as not applicable with a short reason. Do not invent "
                "UI work or request user confirmation for a clear scope boundary. Raise a blocker "
                "only for a real unresolved product requirement.\n"
            )
        system_prompt = (
            "You are the " + role.title + " in a software company.\n"
            "Your responsibility: " + role.mission + "\n"
            "Use only supplied evidence. Distinguish facts, assumptions, and unknowns. "
            "Never claim that code was changed, tests were executed, a website was viewed, "
            "or a security check passed unless supplied tool evidence proves it.\n"
            "Return exactly one JSON object with keys: status, deliverables, findings, "
            "blockers, evidence_needed. status must be one of PASS, NEEDS_WORK, BLOCKED. "
            "deliverables must be an object containing every required deliverable key: "
            + ", ".join(role.deliverables)
            + ". findings, blockers, evidence_needed must be arrays."
            + role_contract
        )
        user_prompt = json.dumps(
            {
                "user_request": user_request,
                "role": role.key,
                "required_deliverables": list(role.deliverables),
                "available_evidence": _prepare_prompt_evidence(role_key, user_request, evidence),
                "independence_rules": list(role.must_be_independent_of),
            },
            ensure_ascii=False,
            default=str,
        )
        raw = await self.provider.complete(system_prompt, user_prompt)
        try:
            result = _validate_specialist_output(raw, role)
        except AgentOutputError as first_error:
            # One bounded repair attempt handles transient formatting/schema mistakes.
            # Never silently extract JSON from prose or retry indefinitely.
            repair_system_prompt = (
                system_prompt
                + "\nYour previous response failed strict validation: "
                + str(first_error)
                + ". Return one corrected JSON object only. Preserve the required schema; "
                + "do not add markdown fences or explanatory prose."
            )
            repair_user_prompt = json.dumps(
                {
                    "role": role.key,
                    "required_deliverables": list(role.deliverables),
                    "required_top_level_keys": [
                        "status", "deliverables", "findings", "blockers", "evidence_needed"
                    ],
                    "invalid_response_excerpt": raw[:12000],
                    "validation_error": str(first_error),
                    "original_request": user_prompt,
                },
                ensure_ascii=False,
                default=str,
            )
            repaired_raw = await self.provider.complete(
                repair_system_prompt, repair_user_prompt
            )
            try:
                result = _validate_specialist_output(repaired_raw, role)
            except AgentOutputError as second_error:
                raise AgentOutputError(
                    f"{role.key} output failed strict validation after one repair attempt: "
                    f"{second_error}"
                ) from second_error
        result["role"] = role.key
        result["role_title"] = role.title
        return result
