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
    runtime = report.get("runtime", {})
    failure = report.get("failure", {})
    impact = report.get("impact", {})
    recovery = report.get("recovery", {})
    failed_steps = report.get("failed_steps", [])
    if failed_steps:
        failed_text = "\n".join(
            f"- {item.get('step', 'unknown')}: {item.get('outcome', 'unknown')}"
            for item in failed_steps
        )
    else:
        failed_text = "- No failed step outcome was captured; inspect the complete Actions logs."

    outcomes = report.get("step_outcomes", {})
    outcome_text = "\n".join(
        f"- {step}: {outcome}" for step, outcome in outcomes.items()
    ) or "- No step outcomes captured."

    return (
        "# Brain execution failure report\n\n"
        f"- Status: {report.get('status', 'FAILED')}\n"
        f"- Failure type: {failure.get('type', 'WorkflowBootstrapFailure')}\n"
        f"- Repository: {runtime.get('repository', '')}\n"
        f"- Commit SHA: {runtime.get('commit_sha', '')}\n"
        f"- Ref: {runtime.get('ref', '')} ({runtime.get('ref_name', '')})\n"
        f"- Workflow run: {runtime.get('run_id', '')} attempt {runtime.get('run_attempt', '')}\n"
        f"- Run URL: {runtime.get('workflow_run_url', '')}\n"
        f"- Workflow/event/action: {runtime.get('workflow', '')} / "
        f"{runtime.get('event_name', '')} / {runtime.get('event_action')}\n"
        f"- Initiating issue: {runtime.get('issue_number')}\n"
        f"- Mutation status: {impact.get('repository_mutation_status', 'UNKNOWN')}\n"
        f"- Tests status: {impact.get('tests_status', 'UNKNOWN')}\n\n"
        "## Step outcomes\n"
        f"{outcome_text}\n\n"
        "## Failed steps\n"
        f"{failed_text}\n\n"
        "## Failure detail\n"
        f"{failure.get('message', '')}\n\n"
        "## Next action\n"
        f"{recovery.get('next_step', '')}\n"
    )


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
                if isinstance(parsed, dict) and isinstance(parsed.get("status"), str) and parsed.get("status"):
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
