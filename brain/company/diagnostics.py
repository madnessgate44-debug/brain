"""Structured, secret-safe execution diagnostics for Brain mission failures."""

from __future__ import annotations

import json
import os
import platform
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _redact(value: str) -> str:
    """Remove known secret values and common token/API-key shapes from diagnostics."""
    for name, secret in os.environ.items():
        if secret and any(marker in name.upper() for marker in ("TOKEN", "API_KEY", "SECRET", "PASSWORD")):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(api[_-]?key[\s:=]+)[^\s,;]+", r"\1[REDACTED]", value)
    return value


def failure_report(
    exc: BaseException,
    *,
    mission: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    """Build a detailed failure artifact without serializing credentials."""
    now = datetime.now(timezone.utc).isoformat()
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    last_frame = frames[-1] if frames else None
    rendered_traceback = _redact("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    event_log = [
        {key: _redact(str(value)) if isinstance(value, str) else value for key, value in event.items()}
        for event in (events or [])
    ]
    return {
        "schema_version": "1.0",
        "status": "FAILED",
        "failure": {
            "type": type(exc).__name__,
            "message": _redact(str(exc)),
            "traceback": rendered_traceback,
            "probable_location": f"{last_frame.filename}:{last_frame.lineno}" if last_frame else None,
        },
        "mission": mission or {},
        "timeline": event_log,
        "runtime": {
            "started_at": started_at,
            "failed_at": now,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "github_repository": os.environ.get("GITHUB_REPOSITORY"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
            "github_job": os.environ.get("GITHUB_JOB"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "working_directory": str(Path.cwd()),
        },
        "credential_diagnostics": {
            "BRAIN_AI_API_KEY_configured": bool(os.environ.get("BRAIN_AI_API_KEY")),
            "BRAIN_GITHUB_TOKEN_configured": bool(os.environ.get("BRAIN_GITHUB_TOKEN")),
            "BRAIN_GITHUB_ACTIONS_TOKEN_configured": bool(os.environ.get("BRAIN_GITHUB_ACTIONS_TOKEN")),
            "note": "Presence only; secret values and token contents are never recorded.",
        },
        "recovery": {
            "attempted": False,
            "actions": [],
            "next_step": "Use the exact failure, traceback, and timeline above to select a corrective action; do not infer success.",
        },
        "impact": {
            "success_claimed": False,
            "repository_mutation_status": "UNKNOWN unless a prior timeline event records it",
            "tests_status": "UNKNOWN unless a prior timeline event records it",
        },
    }


def write_failure_artifacts(
    exc: BaseException,
    *,
    report_path: Path,
    json_path: Path,
    mission: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    report = failure_report(exc, mission=mission, events=events, started_at=started_at)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    failure = report["failure"]
    lines = [
        "# Brain execution failure report",
        "",
        f"- **Status:** {report['status']}",
        f"- **Failure type:** `{failure['type']}`",
        f"- **Failure location:** `{failure['probable_location'] or 'unavailable'}`",
        f"- **Started:** {started_at or 'unavailable'}",
        f"- **Failed:** {report['runtime']['failed_at']}",
        f"- **Workflow run:** {report['runtime']['github_run_id'] or 'not running in GitHub Actions'}",
        "",
        "## Mission context",
        "```json",
        json.dumps(report["mission"], ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## Exact error",
        "```text",
        failure["message"],
        "```",
        "",
        "## Full traceback",
        "```text",
        failure["traceback"],
        "```",
        "",
        "## Execution timeline",
    ]
    lines.extend(
        f"- {event.get('timestamp', 'time unavailable')} | {event.get('stage', 'stage unknown')} | "
        f"{event.get('status', 'status unknown')} | {event.get('detail', '')}"
        for event in report["timeline"]
    )
    lines.extend([
        "",
        "## Credential diagnostics (presence only)",
        f"- AI provider key configured: {report['credential_diagnostics']['BRAIN_AI_API_KEY_configured']}",
        f"- Primary GitHub token configured: {report['credential_diagnostics']['BRAIN_GITHUB_TOKEN_configured']}",
        f"- Actions token configured: {report['credential_diagnostics']['BRAIN_GITHUB_ACTIONS_TOKEN_configured']}",
        "- Secret values intentionally omitted.",
        "",
        "## Impact and recovery",
        f"- Repository mutation status: {report['impact']['repository_mutation_status']}",
        f"- Tests status: {report['impact']['tests_status']}",
        "- Success claimed: no",
        f"- Next step: {report['recovery']['next_step']}",
        "",
        f"Machine-readable diagnostics: `{json_path.name}`",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
