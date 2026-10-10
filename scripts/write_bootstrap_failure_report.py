"""Standard-library fallback diagnostics for failed Brain bootstrap workflows."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


_STEP_OUTCOME_ENV = {
    "checkout": "CHECKOUT_OUTCOME",
    "setup_python": "SETUP_PYTHON_OUTCOME",
    "install": "INSTALL_OUTCOME",
    "lease": "LOCK_OUTCOME",
    "mission_runner": "RUN_OUTCOME",
}
_FAILURE_OUTCOMES = {"failure", "cancelled", "timed_out"}


def _read_event_payload(env: Mapping[str, str]) -> dict[str, Any]:
    event_path = env.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        return {}
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_bootstrap_failure_report(
    env: Mapping[str, str] | None = None,
    event_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build safe, reproducible diagnostics without copying secret values."""
    values = dict(os.environ if env is None else env)
    payload = dict(_read_event_payload(values) if event_payload is None else event_payload)
    issue = payload.get("issue")
    issue_number = issue.get("number") if isinstance(issue, dict) else None
    step_outcomes = {
        step: values.get(env_key, "unknown").strip().casefold() or "unknown"
        for step, env_key in _STEP_OUTCOME_ENV.items()
    }
    failed_steps = [
        {"step": step, "outcome": outcome}
        for step, outcome in step_outcomes.items()
        if outcome in _FAILURE_OUTCOMES
    ]
    repository = values.get("GITHUB_REPOSITORY", "")
    server_url = values.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    run_id = values.get("GITHUB_RUN_ID", "")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if repository and run_id else ""
    timestamp = datetime.now(timezone.utc).isoformat()
    message = (
        "Brain did not produce its own execution report; a workflow bootstrap, lease, "
        "or reporting stage failed."
    )
    recovery = (
        "Inspect the failed Actions step and complete logs. Do not infer repository mutation "
        "or test success without the mission runner's own evidence."
    )

    return {
        "schema_version": "1.1",
        "status": "FAILED",
        "failure": {
            "type": "WorkflowBootstrapFailure",
            "message": message,
            "traceback": None,
            "probable_location": "GitHub Actions workflow step before or around Python mission execution",
        },
        "runtime": {
            "failed_at": timestamp,
            "repository": repository,
            "commit_sha": values.get("GITHUB_SHA", ""),
            "ref": values.get("GITHUB_REF", ""),
            "ref_name": values.get("GITHUB_REF_NAME", ""),
            "run_id": run_id,
            "run_attempt": values.get("GITHUB_RUN_ATTEMPT", ""),
            "workflow": values.get("GITHUB_WORKFLOW", ""),
            "event_name": values.get("GITHUB_EVENT_NAME", ""),
            "event_action": payload.get("action"),
            "issue_number": issue_number,
            "workflow_run_url": run_url,
            "runner_os": values.get("RUNNER_OS", ""),
            "python": sys.version,
        },
        "step_outcomes": step_outcomes,
        "failed_steps": failed_steps,
        "impact": {
            "success_claimed": False,
            "repository_mutation_status": "UNKNOWN; mission runner did not provide evidence",
            "tests_status": "UNKNOWN; mission runner did not provide evidence",
        },
        "recovery": {"attempted": False, "next_step": recovery},
    }


def render_failure_markdown(report: Mapping[str, Any]) -> str:
    """Render readable Markdown for either fallback diagnostics or mission results."""
    status = str(report.get("status") or "FAILED")
    runtime = report.get("runtime") if isinstance(report.get("runtime"), dict) else {}
    failure = report.get("failure") if isinstance(report.get("failure"), dict) else {}
    impact = report.get("impact") if isinstance(report.get("impact"), dict) else {}
    recovery = report.get("recovery") if isinstance(report.get("recovery"), dict) else {}

    def display(value: Any) -> str:
        if value is None:
            return "UNKNOWN"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        return str(value)

    repository = runtime.get("repository") or report.get("repository") or ""
    commit_sha = runtime.get("commit_sha") or report.get("commit_sha") or report.get("head_sha") or ""
    base_commit = report.get("base_commit") or ""
    branch = report.get("branch") or runtime.get("ref_name") or ""
    ref = runtime.get("ref") or ""
    run_id = runtime.get("run_id") or report.get("run_id") or ""
    run_attempt = runtime.get("run_attempt") or report.get("run_attempt") or ""
    run_url = runtime.get("workflow_run_url") or report.get("workflow_run_url") or ""
    workflow = runtime.get("workflow") or report.get("workflow") or ""
    event_name = runtime.get("event_name") or report.get("event_name") or ""
    event_action = runtime.get("event_action", report.get("event_action"))
    issue_number = runtime.get("issue_number", report.get("issue_number"))

    mutation_status = impact.get(
        "repository_mutation_status",
        report.get("mutation_status", "UNKNOWN (not provided in this report)"),
    )
    test_results = report.get("test_results", report.get("tests", report.get("checks")))
    tests_status = impact.get("tests_status", report.get("tests_status"))
    if tests_status is None and isinstance(test_results, dict):
        tests_status = test_results.get("status")
    if tests_status is None:
        tests_status = "UNKNOWN (not provided in this report)"

    stage_outcomes = report.get("stage_outcomes", report.get("step_outcomes", {}))
    failed_steps = report.get("failed_steps", [])
    if isinstance(stage_outcomes, dict):
        outcome_text = "\n".join(
            "- " + str(step) + ": " + display(outcome).replace("\n", "\n  ")
            for step, outcome in stage_outcomes.items()
        ) or "- No stage outcomes captured."
    else:
        outcome_text = display(stage_outcomes) if stage_outcomes else "- No stage outcomes captured."

    title = (
        "# Brain mission report"
        if status.upper() in {"PASS", "SUCCESS", "COMPLETED", "READY_FOR_HUMAN_APPROVAL"}
        else "# Brain execution report"
    )
    lines = [
        title,
        "",
        "- Status: " + status,
        "- Repository: " + display(repository),
        "- Commit SHA: " + display(commit_sha),
        "- Base commit: " + display(base_commit),
        "- Branch/ref: " + display(branch or ref),
        "- Workflow run: " + display(run_id) + " attempt " + display(run_attempt),
        "- Run URL: " + display(run_url),
        "- Workflow/event/action: " + display(workflow) + " / " + display(event_name) + " / " + display(event_action),
        "- Initiating issue: " + display(issue_number),
        "- Mutation status: " + display(mutation_status),
        "- Tests status: " + display(tests_status),
    ]

    summary = report.get("report") or report.get("summary") or report.get("objective")
    if summary:
        lines.extend(["", "## Summary", display(summary)])

    if stage_outcomes:
        lines.extend(["", "## Stage outcomes", outcome_text])

    if test_results is not None:
        lines.extend(["", "## Test results", display(test_results)])

    pull_request = report.get("pull_request")
    if pull_request:
        lines.extend(["", "## Pull request", display(pull_request)])

    post_pr_verification = report.get("post_pr_verification")
    if post_pr_verification:
        lines.extend(["", "## Post-PR verification", display(post_pr_verification)])

    failure_message = failure.get("message") or report.get("failure_message")
    if failure_message:
        lines.extend([
            "",
            "## Failure detail",
            "Failure type: " + display(failure.get("type") or report.get("failure_type")),
            display(failure_message),
        ])

    if failed_steps:
        lines.extend(["", "## Failed steps", display(failed_steps)])

    next_action = recovery.get("next_step") or report.get("next_action")
    if next_action:
        lines.extend(["", "## Next action", display(next_action)])

    return "\n".join(lines) + "\n"


def is_structurally_valid_report(parsed: Any) -> bool:
    """Validate supported report shapes without rejecting real mission reports.

    Supported shapes:
    - Fallback report: schema_version plus runtime, failure, and impact structures.
    - Mission report: non-empty status plus sufficient mission context/evidence
      such as base_commit, branch, stage_outcomes, test_results, pull_request,
      or post_pr_verification (or additional keys like report, metadata, findings).
    """
    if not isinstance(parsed, dict):
        return False

    # Check for Fallback Report shape
    has_schema_version = bool(parsed.get("schema_version"))
    has_runtime = isinstance(parsed.get("runtime"), dict)
    has_failure = isinstance(parsed.get("failure"), dict)
    has_impact = isinstance(parsed.get("impact"), dict)
    if has_schema_version and has_runtime and has_failure and has_impact:
        return True

    # Check for Mission Report shape
    status = parsed.get("status")
    if not isinstance(status, str) or not status.strip():
        return False

    mission_context_keys = {
        "base_commit",
        "branch",
        "stage_outcomes",
        "test_results",
        "pull_request",
        "post_pr_verification",
        "report",
        "metadata",
        "findings",
        "changes",
        "repository",
        "objective",
    }
    has_context = any(key in parsed for key in mission_context_keys)
    return has_context


def ensure_failure_reports(
    env: Mapping[str, str] | None = None,
    event_payload: Mapping[str, Any] | None = None,
    markdown_path: str | Path = "brain-company-result.md",
    json_path: str | Path = "brain-company-result.json",
) -> bool:
    """Validate JSON and Markdown report files, repairing or regenerating missing/malformed pairs."""
    md_path = Path(markdown_path)
    report_path = Path(json_path)

    json_valid = False
    report_data: dict[str, Any] | None = None
    if report_path.exists():
        try:
            content = report_path.read_text(encoding="utf-8")
            if content.strip():
                parsed = json.loads(content)
                if is_structurally_valid_report(parsed):
                    json_valid = True
                    report_data = parsed
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass

    md_valid = False
    if md_path.exists():
        try:
            md_content = md_path.read_text(encoding="utf-8")
            if md_content.strip():
                md_valid = True
        except (OSError, UnicodeDecodeError):
            pass

    if md_valid and json_valid:
        return False

    if report_data is None:
        report = build_bootstrap_failure_report(env, event_payload)
    else:
        report = report_data

    changed = False
    if not json_valid:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        changed = True

    if not md_valid:
        md_path.write_text(render_failure_markdown(report), encoding="utf-8")
        changed = True

    return changed


def main() -> int:
    ensure_failure_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
