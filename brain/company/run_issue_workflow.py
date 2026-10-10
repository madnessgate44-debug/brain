"""Run Brain's specialist workflow for a trusted owner-created GitHub issue."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.engine import CompanyWorkflowEngine
from brain.company.github_gateway import GitHubGatewayError, GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.read_only_audit import is_read_only_audit, run_read_only_audit
from brain.company.tools import GitHubCompanyTools


async def build_write_ready_gateway(
    repository: str,
    owner: str,
    primary_token: str,
    actions_token: str,
) -> GitHubRepositoryGateway:
    """Choose a token with verified write access before any mutating workflow."""
    candidates = []
    if primary_token.strip():
        candidates.append(primary_token.strip())
    if actions_token.strip() and actions_token.strip() not in candidates:
        candidates.append(actions_token.strip())

    failures = []
    for token in candidates:
        gateway = GitHubRepositoryGateway(token=token, allowed_owner=owner)
        try:
            await gateway.verify_write_access(repository)
        except GitHubGatewayError as exc:
            failures.append(str(exc)[:300])
            continue
        return gateway

    detail = "; ".join(failures) or "No GitHub token is configured."
    raise RuntimeError(
        "A mutating workflow requires repository write access, but no configured token "
        f"passed the preflight check. No model calls were made. Details: {detail}"
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
        match = re.search(r"(?im)^repository:\\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\\s*$", body)
        repository = match.group(1) if match else ""
    if not repository or "/" not in repository:
        raise RuntimeError("Add a repository: owner/name line to the issue body.")
    if repository.split("/")[0].casefold() != owner.casefold():
        raise RuntimeError("Target repository must belong to the Brain repository owner.")
    objective = body.split("/brain simulate", 1)[1].strip()
    import re
    objective = re.sub(r"(?im)^repository:\\s*[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\\s*$", "", objective).strip()
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


async def run() -> dict[str, Any]:
    repository, objective, issue_number = request_from_issue()
    if not os.environ.get("BRAIN_AI_API_KEY"):
        raise RuntimeError("BRAIN_AI_API_KEY Actions secret is missing.")

    owner = os.environ.get("BRAIN_GITHUB_OWNER", "madnessgate44-debug")
    primary_token = os.environ.get("BRAIN_GITHUB_TOKEN", "")
    actions_token = os.environ.get("BRAIN_GITHUB_ACTIONS_TOKEN", "")
    provider = OpenAICompatibleProvider(
        api_key=os.environ["BRAIN_AI_API_KEY"],
        base_url=os.environ.get(
            "BRAIN_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        ),
        model=os.environ.get("BRAIN_AI_MODEL", "gemini-2.5-flash"),
        timeout_seconds=120 if is_read_only_audit(objective) else 45,
    )

    # Audit-only requests need repository read access, not write scope. This branch
    # is selected before the write preflight and never invokes mutation-capable tools.
    if is_read_only_audit(objective):
        return await run_read_only_audit(
            repository=repository,
            objective=objective,
            owner=owner,
            primary_token=primary_token,
            actions_token=actions_token,
            provider=provider,
            issue_number=issue_number,
        )

    gateway = await build_write_ready_gateway(
        repository=repository,
        owner=owner,
        primary_token=primary_token,
        actions_token=actions_token,
    )
    tools = GitHubCompanyTools(
        gateway=gateway,
        control_repository=os.environ.get("BRAIN_CONTROL_REPOSITORY", "madnessgate44-debug/brain"),
        poll_seconds=5,
        timeout_seconds=900,
    )
    engine = CompanyWorkflowEngine(SpecialistAgentRunner(provider), tools)
    return await engine.run(
        user_request=objective,
        repository=repository,
        initial_evidence={
            "request_source": "owner-created GitHub issue",
            "issue_number": issue_number,
            "scope_guard": "No merge, deployment, or default-branch write.",
        },
    )


def main() -> None:
    report_path = Path("brain-company-result.md")
    json_path = Path("brain-company-result.json")
    try:
        result = asyncio.run(run())
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        if result.get("mode") == "read_only_audit":
            metadata = [
                "# Brain read-only audit execution",
                "",
                f"- Status: **{result.get('status', 'UNKNOWN')}**",
                f"- Repository: `{result.get('repository', 'unknown')}`",
                f"- Branch: `{result.get('branch', 'unknown')}`",
                f"- Base commit: `{result.get('base_commit', 'unknown')}`",
                f"- Source files read: {result.get('files_inspected', 0)}",
                "- Repository mutations: **none**",
                "- Automated tests: **not run in read-only audit mode**",
                "",
                "---",
                "",
                result.get("report", "No audit report was returned."),
            ]
            report_path.write_text("\\n".join(metadata) + "\\n", encoding="utf-8")
            print(report_path.read_text(encoding="utf-8"))
            return

        lines = [
            "# Brain company workflow result", "",
            f"- Status: **{result.get('status', 'UNKNOWN')}**",
            f"- Repository: `{result.get('repository', 'unknown')}`",
            f"- Branch: `{result.get('branch', 'unknown')}`",
            f"- Changed files: {', '.join(result.get('changed_files', [])) or 'none reported'}",
            f"- Test evidence: {result.get('test_evidence', {}).get('status', 'unavailable')}",
            f"- Test run: {result.get('test_evidence', {}).get('run_url', 'unavailable')}",
            f"- Pull request: {result.get('pull_request', {}).get('url', 'unavailable')}",
            "", "## Specialist timeline",
        ]
        lines.extend(
            f"- {item.get('role')}: {item.get('status')}"
            for item in result.get("timeline", [])
        )
        lines.extend([
            "", "## Release gate",
            f"- Passed: {result.get('release_gate', {}).get('passed', False)}",
            f"- Blockers: {', '.join(result.get('release_gate', {}).get('blockers', [])) or 'none'}",
            "", "## Next action",
            result.get("next_action", "Review the saved JSON artifact and logs."),
        ])
        report_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
        print(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        safe_message = str(exc)
        for secret_name in ("BRAIN_GITHUB_TOKEN", "BRAIN_AI_API_KEY", "BRAIN_GITHUB_ACTIONS_TOKEN"):
            secret = os.environ.get(secret_name, "")
            if secret:
                safe_message = safe_message.replace(secret, "[REDACTED]")
        report_path.write_text(
            "# Brain company workflow result\\n\\n"
            "**Status: BLOCKED / FAILED**\\n\\n"
            f"**Reason:** {safe_message[:1200]}\\n\\n"
            "No successful completion is claimed. Inspect the workflow job logs for sanitized execution details.\\n",
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps({"status": "BLOCKED", "error": safe_message[:1200]}),
            encoding="utf-8",
        )
        print(report_path.read_text(encoding="utf-8"))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
