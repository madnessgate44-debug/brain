"""Standard-library fallback diagnostics for failed Brain bootstrap workflows."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


_STEP_OUTCOME_ENV = {
    "checkout": "CHECKOUT_OUTCOME",
    "setup_python": "SETUP_PYTHON_OUTCOME",
    "install_brain": "INSTALL_OUTCOME",
    "acquire_lock": "LEASE_OUTCOME",
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

    return {
        "status": "FAILED",
        "failure_type": "bootstrap_failure",
        "failure_message": (
            "The company workflow did not produce its own execution report. "
            "Use the exact run, commit, ref, and failed-step outcomes below to reproduce it."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "python_version": values.get("PYTHON_VERSION", ""),
        "step_outcomes": step_outcomes,
        "failed_steps": failed_steps,
        "mutation_status": "UNKNOWN",
        "tests_status": "UNKNOWN",
        "success_claimed": False,
        "recovery_action": (
            "Inspect the failed Actions step and logs. Do not infer repository mutation "
            "or test success without the mission runner's own evidence."
        ),
    }


def render_failure_markdown(report: Mapping[str, Any]) -> str:
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
        f"- Failure type: {report.get('failure_type', 'bootstrap_failure')}\n"
        f"- Repository: {report.get('repository', '')}\n"
        f"- Commit SHA: {report.get('commit_sha', '')}\n"
        f"- Ref: {report.get('ref', '')} ({report.get('ref_name', '')})\n"
        f"- Workflow run: {report.get('run_id', '')} attempt {report.get('run_attempt', '')}\n"
        f"- Run URL: {report.get('workflow_run_url', '')}\n"
        f"- Workflow/event/action: {report.get('workflow', '')} / "
        f"{report.get('event_name', '')} / {report.get('event_action')}\n"
        f"- Initiating issue: {report.get('issue_number')}\n"
        f"- Mutation status: {report.get('mutation_status', 'UNKNOWN')}\n"
        f"- Tests status: {report.get('tests_status', 'UNKNOWN')}\n\n"
        "## Step outcomes\n"
        f"{outcome_text}\n\n"
        "## Failed steps\n"
        f"{failed_text}\n\n"
        "## Failure detail\n"
        f"{report.get('failure_message', '')}\n\n"
        "## Recovery\n"
        f"{report.get('recovery_action', '')}\n"
    )


def ensure_failure_reports(
    env: Mapping[str, str] | None = None,
    event_payload: Mapping[str, Any] | None = None,
    markdown_path: str | Path = "brain-company-result.md",
    json_path: str | Path = "brain-company-result.json",
) -> bool:
    """Create only missing report files; never overwrite a mission-produced report."""
    md_path = Path(markdown_path)
    report_path = Path(json_path)
    if md_path.exists() and report_path.exists():
        return False

    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                report = build_bootstrap_failure_report(env, event_payload)
        except (OSError, json.JSONDecodeError):
            report = build_bootstrap_failure_report(env, event_payload)
    else:
        report = build_bootstrap_failure_report(env, event_payload)

    if not report_path.exists():
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    if not md_path.exists():
        md_path.write_text(render_failure_markdown(report), encoding="utf-8")
    return True


def main() -> int:
    ensure_failure_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
