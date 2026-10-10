"""Run Brain's specialist workflow for a trusted owner-created GitHub issue."""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.company.diagnostics import write_failure_artifacts
from brain.company.mission_capabilities import plan_capabilities

from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.engine import CompanyWorkflowEngine
from brain.company.github_gateway import GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.tools import GitHubCompanyTools


def request_from_issue() -> tuple[str, str, int]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GitHub issue event context is missing.")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    body = issue.get("body") or ""
    owner = os.environ.get("GITHUB_REPOSITORY", "").split("/", 1)[0]
    if (issue.get("user") or {}).get("login", "").casefold() != owner.casefold():
        raise RuntimeError("Only an issue opened by the repository owner can run Brain.")
    if "/brain simulate" not in body:
        raise RuntimeError("Missing /brain simulate command.")
    repository = os.environ.get("BRAIN_TARGET_REPOSITORY", "").strip()
    if not repository:
        import re
        match = re.search(r"(?im)^repository:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s*$", body)
        repository = match.group(1) if match else ""
    if not repository or "/" not in repository:
        raise RuntimeError("Add a repository: owner/name line to the issue body.")
    if repository.split("/", 1)[0].casefold() != owner.casefold():
        raise RuntimeError("Target repository must belong to the Brain repository owner.")
    objective = body.split("/brain simulate", 1)[1].strip()
    import re
    objective = re.sub(r"(?im)^repository:\s*[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\s*$", "", objective).strip()
    if objective.lower().startswith("objective:"):
        objective = objective[len("objective:"):].strip()
    if not objective:
        objective = (
            "Inspect the target repository using actual source files, identify the three "
            "most critical verified defects, fix them on a dedicated branch, run the real "
            "test suite, conduct independent code review and security/QA checks, and report "
            "evidence. Do not merge or deploy."
        )
    return repository, objective, int(issue.get("number", 0))


async def build_gateway(
    repository: str,
    owner: str,
    primary_token: str,
    actions_token: str,
    capability_plan: Any,
    events: list[dict[str, Any]] | None = None,
    control_repository: str | None = None,
) -> GitHubRepositoryGateway:
    """Resolve credentials using mission scope and the token's actual repository boundary."""
    events = events if events is not None else []
    control_repo = (
        control_repository or os.environ.get("BRAIN_CONTROL_REPOSITORY", "")
        or os.environ.get("GITHUB_REPOSITORY", "")
    ).strip().casefold()
    primary = primary_token.strip()
    actions = actions_token.strip()
    is_control_repo_write = (
        "repository:write" in capability_plan.required_capabilities
        and bool(control_repo)
        and repository.casefold() == control_repo
    )
    # GITHUB_TOKEN is scoped to this workflow's repository and has explicit contents:write
    # permission. Prefer it only for writes to that same repository. For other repositories,
    # retain the configured PAT first because GITHUB_TOKEN cannot cross repository boundaries.
    ordered_tokens = (
        [("BRAIN_GITHUB_ACTIONS_TOKEN", actions), ("BRAIN_GITHUB_TOKEN", primary)]
        if is_control_repo_write
        else [("BRAIN_GITHUB_TOKEN", primary), ("BRAIN_GITHUB_ACTIONS_TOKEN", actions)]
    )
    candidates: list[tuple[str, str]] = []
    for label, token in ordered_tokens:
        if token and token not in [existing for _, existing in candidates]:
            candidates.append((label, token))

    failures: list[str] = []
    for label, token in candidates:
        candidate = GitHubRepositoryGateway(token=token, allowed_owner=owner)
        try:
            if (
                "repository:write" in capability_plan.required_capabilities
                and label == "BRAIN_GITHUB_ACTIONS_TOKEN"
                and is_control_repo_write
            ):
                # GitHub's repository metadata can report push=false for the workflow token
                # even when the job's explicit contents:write permission authorizes Git Data writes.
                # Do not mistake that metadata field for an authoritative token-scope check.
                snapshot = await candidate.inspect_repository(repository, max_files=1)
                detail = (
                    f"{label} passed read preflight for the control repository; effective write "
                    "permission will be established by the actual bounded change-set request."
                )
            elif "repository:write" in capability_plan.required_capabilities:
                permission_result = await candidate.verify_write_access(repository)
                if permission_result.get("write_access") is True:
                    detail = (
                        f"{label} repository metadata reports push permission for {repository}; "
                        "the actual write API has not yet been exercised."
                    )
                else:
                    detail = (
                        f"{label} can read target repository {repository}; GitHub did not expose push "
                        "permission metadata, so the requested write operation remains the authoritative check."
                    )
            else:
                snapshot = await candidate.inspect_repository(repository, max_files=1)
                detail = f"{label} passed target repository read preflight; default branch={snapshot.get('default_branch')}."
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "credential_preflight", "status": "PASS", "detail": detail})
            return candidate
        except Exception as exc:
            detail = f"{label} rejected for {repository}: {type(exc).__name__}: {exc}"
            failures.append(detail)
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "credential_preflight", "status": "FAIL", "detail": detail})

    details = "No GitHub credential is configured." if not candidates else "Attempts: " + " | ".join(failures)
    raise RuntimeError(
        f"No configured credential satisfied {capability_plan.required_capabilities} for target {repository}. {details}"
    )


async def run(events: list[dict[str, Any]] | None = None, mission_context: dict[str, Any] | None = None) -> dict[str, Any]:
    events = events if events is not None else []
    started = datetime.now(timezone.utc).isoformat()
    repository, objective, issue_number = request_from_issue()
    mission = {"repository": repository, "objective": objective, "issue_number": issue_number}
    plan = plan_capabilities(objective)
    mission["capability_plan"] = {"mode": plan.mode, "required_capabilities": list(plan.required_capabilities), "rationale": plan.rationale}
    if mission_context is not None:
        mission_context.update(mission)
    events.append({"timestamp": started, "stage": "capability_planning", "status": "PASS", "detail": json.dumps(mission["capability_plan"])})
    if not os.environ.get("BRAIN_AI_API_KEY"):
        raise RuntimeError("BRAIN_AI_API_KEY is not configured; model invocation is required.")
    gateway = await build_gateway(
        repository=repository,
        owner=os.environ.get("BRAIN_GITHUB_OWNER", "madnessgate44-debug"),
        primary_token=os.environ.get("BRAIN_GITHUB_TOKEN", ""),
        actions_token=os.environ.get("BRAIN_GITHUB_ACTIONS_TOKEN", ""),
        capability_plan=plan,
        events=events,
        control_repository=os.environ.get(
            "BRAIN_CONTROL_REPOSITORY", "madnessgate44-debug/brain"
        ),
    )
    control_repository = os.environ.get(
        "BRAIN_CONTROL_REPOSITORY", "madnessgate44-debug/brain"
    )
    tools = GitHubCompanyTools(
        gateway=gateway,
        control_repository=control_repository,
        poll_seconds=5,
        timeout_seconds=900,
    )
    provider = OpenAICompatibleProvider(
        api_key=os.environ["BRAIN_AI_API_KEY"],
        base_url=os.environ.get(
            "BRAIN_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        ),
        model=os.environ.get("BRAIN_AI_MODEL", "gemini-2.5-flash"),
        timeout_seconds=45,
    )
    if plan.mode == "read_only":
        events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "repository_inspection", "status": "STARTED", "detail": "Collecting source evidence without repository mutation."})
        snapshot = await tools.inspect_repository(repository)
        events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "repository_inspection", "status": "PASS", "detail": f"Read {snapshot.get('source_files_read', 0)} source files at {snapshot.get('base_commit')}."})
        events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "model_audit", "status": "STARTED", "detail": "Invoking the configured model for evidence-bounded analysis."})
        prompt = (
            "Perform a detailed read-only software audit using only the supplied repository snapshot and source contents. "
            "Do not modify files or claim tests ran. Separate confirmed defects, risks, hypotheses, and missing evidence. "
            "For each finding include severity, exact file/symbol/line where possible, code evidence, impact, and remediation. "
            "Cover correctness, architecture, security/privacy, reliability, usability, product behavior, and tests where evidenced. "
            "List repository, default branch, base commit, files actually read, checks not run and why, strengths, limitations, "
            "and a prioritized action plan. Return a substantive Markdown report."
        )
        report = await provider.complete(prompt, json.dumps({"objective": objective, "repository_snapshot": snapshot}, ensure_ascii=False, default=str))
        if not report.strip():
            raise RuntimeError("Model returned an empty read-only audit report.")
        events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "model_audit", "status": "PASS", "detail": "Generated evidence-bounded read-only report."})
        return {
            "status": "AUDIT_COMPLETE",
            "mode": "read_only",
            "repository": repository,
            "branch": snapshot.get("default_branch"),
            "base_commit": snapshot.get("base_commit"),
            "files_inspected": snapshot.get("source_files_read", 0),
            "changed_files": [],
            "test_evidence": {"status": "NOT_RUN", "reason": "Read-only mission; no tests were executed or claimed."},
            "pull_request": {},
            "timeline": events,
            "release_gate": {"passed": False, "blockers": ["Read-only mission; no release requested."]},
            "report": report,
            "next_action": "Review the audit report; no repository changes were made.",
        }

    events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "company_workflow", "status": "STARTED", "detail": "Running specialist implementation, review, and verification workflow."})
    result = await CompanyWorkflowEngine(SpecialistAgentRunner(provider), tools).run(
        user_request=objective,
        repository=repository,
        initial_evidence={
            "request_source": "owner-created GitHub issue",
            "issue_number": issue_number,
            "scope_guard": "No merge, deployment, or default-branch write.",
        },
    )
    return result


def main() -> None:
    report_path = Path("brain-company-result.md")
    json_path = Path("brain-company-result.json")
    started_at = datetime.now(timezone.utc).isoformat()
    events: list[dict[str, Any]] = []
    mission: dict[str, Any] = {}
    try:
        result = asyncio.run(run(events, mission))
        mission = {
            "repository": result.get("repository"),
            "mode": result.get("mode", "implementation"),
            "branch": result.get("branch"),
            "issue_number": result.get("issue_number"),
        }
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        lines = [
            "# Brain company workflow result", "",
            f"- Status: **{result.get('status', 'UNKNOWN')}**",
            f"- Mode: `{result.get('mode', 'implementation')}`",
            f"- Repository: `{result.get('repository', 'unknown')}`",
            f"- Branch: `{result.get('branch', 'unknown')}`",
            f"- Base commit: `{result.get('base_commit', 'not recorded')}`",
            f"- Files inspected: {result.get('files_inspected', 'see JSON evidence')}",
            f"- Changed files: {', '.join(result.get('changed_files', [])) or 'none reported'}",
            f"- Test evidence: {result.get('test_evidence', {}).get('status', 'unavailable')}",
            f"- Pull request: {result.get('pull_request', {}).get('url', 'unavailable')}", "",
        ]
        if result.get("report"):
            lines.extend(["## Mission report", "", result["report"], ""])
        lines.extend(["## Execution timeline", ""])
        lines.extend(
            f"- {item.get('timestamp', '')} | {item.get('stage', item.get('role', 'stage'))} | {item.get('status', '')} | {item.get('detail', '')}"
            for item in result.get("timeline", [])
        )
        lines.extend(["", "## Release gate", f"- Passed: {result.get('release_gate', {}).get('passed', False)}",
            f"- Blockers: {', '.join(result.get('release_gate', {}).get('blockers', [])) or 'none'}", "",
            "## Next action", result.get("next_action", "Review the saved JSON artifact and evidence.")])
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(report_path.read_text(encoding="utf-8"))
    except BaseException as exc:
        if not events:
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "startup", "status": "FAIL", "detail": "Failure occurred before a workflow stage was recorded."})
        write_failure_artifacts(
            exc, report_path=report_path, json_path=json_path,
            mission=mission, events=events, started_at=started_at,
        )
        print(report_path.read_text(encoding="utf-8"))
        raise SystemExit(1) from None

if __name__ == "__main__":
    main()
