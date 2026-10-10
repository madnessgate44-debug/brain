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
from brain.company.github_gateway import GitHubGatewayError, GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.tools import GitHubCompanyTools


async def build_write_ready_gateway(
    repository: str,
    owner: str,
    primary_token: str,
    actions_token: str,
) -> GitHubRepositoryGateway:
    """Choose a token with verified write access before any model calls."""
    candidates = []
    if primary_token.strip():
        candidates.append(primary_token.strip())
    if actions_token.strip() and actions_token.strip() not in candidates:
        candidates.append(actions_token.strip())

    for token in candidates:
        gateway = GitHubRepositoryGateway(token=token, allowed_owner=owner)
        try:
            await gateway.verify_write_access(repository)
        except GitHubGatewayError:
            continue
        return gateway

    raise RuntimeError(
        "No configured GitHub token has verified repository write access. "
        "Grant Contents: write to BRAIN_GITHUB_TOKEN or to the GitHub Actions token "
        "through the workflow/repository permissions. No model calls were made."
    )


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


async def run(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    events = events if events is not None else []
    started = datetime.now(timezone.utc).isoformat()
    repository, objective, issue_number = request_from_issue()
    mission = {"repository": repository, "objective": objective, "issue_number": issue_number}
    plan = plan_capabilities(objective)
    mission["capability_plan"] = {"mode": plan.mode, "required_capabilities": list(plan.required_capabilities), "rationale": plan.rationale}
    events.append({"timestamp": started, "stage": "capability_planning", "status": "PASS", "detail": json.dumps(mission["capability_plan"])})
    if not os.environ.get("BRAIN_AI_API_KEY"):
        raise RuntimeError("BRAIN_AI_API_KEY is not configured; model invocation is required.")
    candidates = []
    primary = os.environ.get("BRAIN_GITHUB_TOKEN", "").strip()
    actions = os.environ.get("BRAIN_GITHUB_ACTIONS_TOKEN", "").strip()
    if primary:
        candidates.append(("BRAIN_GITHUB_TOKEN", primary))
    if actions and actions not in [token for _, token in candidates]:
        candidates.append(("BRAIN_GITHUB_ACTIONS_TOKEN", actions))
    gateway = None
    failures = []
    for label, token in candidates:
        candidate = GitHubRepositoryGateway(
            token=token,
            allowed_owner=os.environ.get("BRAIN_GITHUB_OWNER", "madnessgate44-debug"),
        )
        try:
            if plan.mode == "mutating":
                await candidate.verify_write_access(repository)
                detail = f"{label} passed target repository write preflight."
            else:
                snapshot = await candidate.inspect_repository(repository, max_files=1)
                detail = f"{label} passed target repository read preflight; default branch={snapshot.get('default_branch')}."
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "credential_preflight", "status": "PASS", "detail": detail})
            gateway = candidate
            break
        except Exception as exc:
            detail = f"{label} rejected for {repository}: {type(exc).__name__}: {exc}"
            failures.append(detail)
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "credential_preflight", "status": "FAIL", "detail": detail})
    if gateway is None:
        raise RuntimeError(
            f"No configured credential satisfied {plan.required_capabilities} for target {repository}. "
            + ("No GitHub credential is configured." if not candidates else "Attempts: " + " | ".join(failures))
        )
    tools = GitHubCompanyTools(
        gateway=gateway,
        control_repository=os.environ.get("BRAIN_CONTROL_REPOSITORY", "madnessgate44-debug/brain"),
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

    engine = CompanyWorkflowEngine(SpecialistAgentRunner(provider), tools)
    result = await engine.run(
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
        result = asyncio.run(run(events))
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
        report_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
        print(report_path.read_text(encoding="utf-8"))
    except BaseException as exc:
        if not events:
            events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": "startup", "status": "FAIL", "detail": "Failure occurred before a workflow stage was recorded."})
        write_failure_artifacts(
            exc, report_path=report_path, json_path=json_path,
            mission=mission, events=events, started_at=started_at,
        )
        print(report_path.read_text(encoding="utf-8"))
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()
