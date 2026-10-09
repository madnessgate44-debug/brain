"""Run an owner-authored browser mission from a GitHub issue event.

Issue bodies must contain /brain browser and one fenced JSON object with:
title, objective, allowed_domains, actions, and owner_approved.
No credentials are accepted in the payload. Reports and screenshots are saved for
the workflow artifact and a concise issue comment.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from brain.runtime.workers.browser_worker import BrowserWorker, BrowserPolicyError


def parse_issue_payload(event: dict[str, Any], repository_owner: str) -> dict[str, Any]:
    """Validate the issue author and extract a bounded browser task."""
    issue = event.get("issue") or {}
    user = issue.get("user") or {}
    if user.get("login", "").casefold() != repository_owner.casefold():
        raise ValueError("Only an issue authored by the repository owner may start a browser task.")
    body = issue.get("body") or ""
    if "/brain browser" not in body:
        raise ValueError("Issue body must include /brain browser.")
    matches = re.findall(r"```json\s*(.*?)\s*```", body, flags=re.DOTALL | re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError("Include exactly one fenced JSON object after /brain browser.")
    try:
        payload = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise ValueError("The browser task JSON is invalid.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The browser task must be a JSON object.")
    allowed_keys = {"title", "objective", "allowed_domains", "actions", "owner_approved"}
    if set(payload) - allowed_keys:
        raise ValueError("Unsupported browser task fields were supplied.")
    if not isinstance(payload.get("title"), str) or not payload["title"].strip():
        raise ValueError("title is required.")
    if not isinstance(payload.get("objective"), str) or not payload["objective"].strip():
        raise ValueError("objective is required.")
    domains = payload.get("allowed_domains")
    if not isinstance(domains, list) or not domains or len(domains) > 30:
        raise ValueError("allowed_domains must contain 1 to 30 domain rules.")
    if any(not isinstance(item, str) or not item.strip() or item.strip() == "*" for item in domains):
        raise ValueError("Every allowed_domains entry must be a non-wildcard domain rule.")
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > 25:
        raise ValueError("actions must contain 1 to 25 explicit browser actions.")
    if payload.get("owner_approved") is not True:
        raise ValueError("owner_approved must be true for an owner-authored issue task.")
    # The worker performs the authoritative operation/schema validation.
    from brain.runtime.workers.browser_worker import validate_browser_actions
    payload["actions"] = validate_browser_actions(actions)
    payload["allowed_domains"] = [item.strip() for item in domains]
    return payload


async def execute_payload(payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Execute the bounded task and save screenshots separately from JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "brain-browser-profile"
    worker = BrowserWorker(allowed_domains=payload["allowed_domains"], profile_dir=str(profile_root))
    result = await worker.execute(payload["actions"], owner_approved=payload["owner_approved"])
    for item in result.get("results", []):
        value = item.get("result")
        if item.get("op") == "screenshot" and isinstance(value, dict) and value.get("base64"):
            image_bytes = base64.b64decode(value.pop("base64"))
            filename = f"screenshot-action-{item['index'] + 1:02d}.png"
            (output_dir / filename).write_bytes(image_bytes)
            value["artifact"] = filename
    (output_dir / "browser-execution-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status = result.get("status", "failed").upper()
    completed = result.get("completed_actions", 0)
    requested = result.get("requested_actions", 0)
    lines = [
        "Public, non-sensitive browsing only. Do not use this issue runner for logged-in accounts or private data.",
        f"## Brain browser task: {status}",
        "",
        f"- **Task:** {payload['title']}",
        f"- **Actions completed:** {completed}/{requested}",
        f"- **Objective:** {payload['objective'][:1000]}",
        "",
        "### Action results",
    ]
    for item in result.get("results", []):
        if item.get("ok"):
            safe_result = dict(item.get("result", {}))
            if "text" in safe_result:
                safe_result["text"] = "[page text omitted from public issue comment; inspect workflow artifact if appropriate]"
            safe_result.pop("base64", None)
            summary = json.dumps(safe_result, ensure_ascii=False)
            lines.append(f"- Action {item.get('index', 0) + 1} ({item.get('op')}): PASS — {summary[:500]}")
        else:
            lines.append(f"- Action {item.get('index', 0) + 1} ({item.get('op')}): FAIL — {item.get('error')}: {item.get('message')}")
    lines.extend(["", "Full JSON report and screenshots (if any) are attached to the workflow run."])
    (output_dir / "browser-result.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not event_path or not owner:
        raise SystemExit("Missing GitHub event context.")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    output_dir = Path("browser-output")
    try:
        payload = parse_issue_payload(event, owner)
        result = asyncio.run(execute_payload(payload, output_dir))
    except (ValueError, BrowserPolicyError) as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        message = f"## Brain browser task: BLOCKED\n\n{str(exc)[:1000]}\n"
        (output_dir / "browser-result.md").write_text(message, encoding="utf-8")
        (output_dir / "browser-execution-report.json").write_text(
            json.dumps({"status": "blocked", "reason": str(exc)[:1000]}, indent=2),
            encoding="utf-8",
        )
        return 1
    return 0 if result.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
