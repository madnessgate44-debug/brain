"""Read-only repository audit path that never requires write-scoped credentials."""

import json
from typing import Any

from brain.company.github_gateway import GitHubGatewayError, GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.tools import GitHubCompanyTools


def is_read_only_audit(objective: str) -> bool:
    """Recognize explicit audit-only requests before any write preflight."""
    text = objective.casefold()
    markers = (
        "read-only", "read only", "audit only", "audit-only",
        "report findings only", "inspect and report", "do not edit",
        "do not modify", "no changes to",
    )
    return any(marker in text for marker in markers)


async def build_read_only_gateway(
    repository: str,
    owner: str,
    primary_token: str,
    actions_token: str,
) -> GitHubRepositoryGateway:
    """Choose a credential by actual read access, not assumed write scope."""
    candidates = []
    if primary_token.strip():
        candidates.append(primary_token.strip())
    if actions_token.strip() and actions_token.strip() not in candidates:
        candidates.append(actions_token.strip())

    failures = []
    for token in candidates:
        gateway = GitHubRepositoryGateway(token=token, allowed_owner=owner)
        try:
            await gateway.inspect_repository(repository, max_files=1)
        except GitHubGatewayError as exc:
            failures.append(str(exc)[:300])
            continue
        return gateway

    detail = "; ".join(failures) or "No GitHub token is configured."
    raise RuntimeError(
        "Read-only audit cannot access the target repository with the configured "
        f"credentials. Required access is repository metadata and contents: read. Details: {detail}"
    )


async def run_read_only_audit(
    repository: str,
    objective: str,
    owner: str,
    primary_token: str,
    actions_token: str,
    provider: OpenAICompatibleProvider,
    issue_number: int,
) -> dict[str, Any]:
    """Inspect real source files and produce an evidence-bounded report without writes."""
    gateway = await build_read_only_gateway(
        repository=repository,
        owner=owner,
        primary_token=primary_token,
        actions_token=actions_token,
    )
    tools = GitHubCompanyTools(gateway=gateway)
    snapshot = await tools.inspect_repository(repository)
    prompt = (
        "You are Brain's senior software auditor. Perform a read-only, evidence-based "
        "repository audit using only the supplied repository snapshot and source contents. "
        "Do not propose or claim changes have been applied. Do not infer files or features "
        "that are not evidenced. Distinguish confirmed defects, risks, hypotheses, and "
        "missing evidence. Prioritize findings by severity. For every finding provide: "
        "severity, exact file and symbol/line if possible, observed evidence, user impact, "
        "and recommended remediation. Review correctness, architecture, security/privacy, "
        "reliability, accessibility/usability, product-specific behavior, and test coverage "
        "where relevant. Include repository, default branch, base commit, files actually read, "
        "checks not run and why, strengths, limitations, and a prioritized action plan. "
        "Do not claim tests/build/lint were run; this path only reads repository files. "
        "Return a substantive Markdown audit report, not JSON."
    )
    user_context = json.dumps(
        {
            "objective": objective,
            "repository": repository,
            "initiating_issue": issue_number,
            "hard_limits": [
                "Read-only: no file writes, branches, commits, pull requests, merges, or deployments.",
                "No secrets or personal data in the report.",
                "Only state facts supported by the supplied repository snapshot.",
            ],
            "repository_snapshot": snapshot,
        },
        ensure_ascii=False,
        default=str,
    )
    report = await provider.complete(prompt, user_context)
    if not report.strip():
        raise RuntimeError("The auditor returned an empty report.")
    return {
        "status": "AUDIT_COMPLETE",
        "mode": "read_only_audit",
        "repository": repository,
        "branch": snapshot.get("default_branch"),
        "base_commit": snapshot.get("base_commit"),
        "files_inspected": snapshot.get("source_files_read", 0),
        "changed_files": [],
        "test_evidence": {
            "status": "NOT_RUN",
            "reason": "Read-only audit mode does not execute repository code or mutate the target repository.",
        },
        "pull_request": {},
        "timeline": [{"role": "read_only_auditor", "status": "REPORT_GENERATED"}],
        "release_gate": {"passed": False, "blockers": ["Audit-only mode; no release or change was requested."]},
        "report": report,
        "next_action": "Review the audit findings; no repository changes were made.",
    }
