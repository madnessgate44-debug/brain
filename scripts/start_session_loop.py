#!/usr/bin/env python3
"""Start the session agent's loop as a scheduled OpenHands Cloud conversation.

W4 (watcher/knowledge/WEAKNESSES.md): Watcher and Shadow have scheduled workflows; the session
agent had none, so it only ran when the owner opened a session. This gives it a loop.

It starts one self-contained Cloud conversation against the repo, waits for the sandbox to be
ready, and records the conversation link as evidence of a live run (the W3 gap — "no committed
evidence of a live issue -> PR run"). It never starts more than one conversation per run.

Reads OPENHANDS_API_KEY (Cloud API) from the environment. With no key, or with --dry-run, it
prints the exact payload and writes the evidence without contacting the API, so the wiring can
be verified for free.

    python3 scripts/start_session_loop.py [--repo owner/name] [--branch main]
                                          [--task-file docs/SESSION_LOOP_TASK.md]
                                          [--out watcher/knowledge/evidence] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://app.all-hands.dev/api/v1"
KEY_ENV = "OPENHANDS_API_KEY"


def build_payload(task: str, repo: str, branch: str, title: str) -> dict:
    """The POST body for POST /app-conversations (V1)."""
    return {
        "initial_message": {"content": [{"type": "text", "text": task}]},
        "selected_repository": repo,
        "selected_branch": branch,
        "title": title,
    }


def parse_start_task(payload: dict) -> tuple[str, str]:
    """Return (start_task_id, app_conversation_id) from a start response.

    POST /app-conversations is asynchronous: `id` is the start-task id, and
    `app_conversation_id` is only present once the sandbox is ready.
    """
    return payload.get("id", ""), payload.get("app_conversation_id", "")


def _post(url: str, body: dict, key: str, tries: int = 6) -> dict:
    data = json.dumps(body).encode("utf-8")
    last: Exception | None = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", "Bearer " + key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt, 20))
                continue
            raise
    raise RuntimeError(f"POST {url} failed after {tries} tries: {last}")


def _get(url: str, key: str, tries: int = 6) -> dict:
    last: Exception | None = None
    for attempt in range(tries):
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + key)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt, 20))
                continue
            raise
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last}")


def _first(payload: object) -> dict:
    """Return the first record from a V1 `?ids=` response.

    Those endpoints return a JSON *list* of records (the reference client's
    `app_conversations_get_batch` returns `r.json()` unchanged); a missing id comes back as
    `[null]`. Some deployments wrap the same data as `{"items": [...]}`. Accept both shapes,
    and treat `null`/empty as "no record" — never assume the payload is a dict.
    """
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items[0] if items and isinstance(items[0], dict) else {}
        return payload
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    return {}


def wait_for_ready(start_id: str, key: str, timeout_s: int = 300, interval_s: int = 5) -> str:
    """Poll the start-task until READY and return the app_conversation_id."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        task = _get(f"{API}/app-conversations/start-tasks?ids={start_id}", key)
        first = _first(task)
        if first.get("app_conversation_id"):
            return first["app_conversation_id"]
        if str(first.get("status", "")).upper() in {"ERROR", "FAILED"}:
            raise RuntimeError(f"start-task failed: {first.get('detail') or first.get('status')}")
        time.sleep(interval_s)
    raise RuntimeError(f"start-task {start_id} not ready within {timeout_s}s")


def ui_url(conv_id: str, key: str) -> str:
    first = _first(_get(f"{API}/app-conversations?ids={conv_id}", key))
    return (
        first.get("conversation_ui_url")
        or f"https://app.all-hands.dev/canvas/conversations/{conv_id}"
    )


def write_evidence(
    out_dir: Path, repo: str, branch: str, conv_id: str, url: str, dry: bool, note: str = ""
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"session-loop-{stamp}.md"
    if dry:
        status = "DRY RUN — no conversation started"
    elif conv_id and url:
        status = "LIVE — conversation started"
    else:
        status = "LIVE — conversation started, link not yet resolved"
    body = (
        f"# Session agent loop — {stamp} UTC\n\n"
        f"Status: {status}\n\n"
        f"- repository: {repo}\n"
        f"- branch: {branch}\n"
        f"- app_conversation_id: {conv_id or '(none)'}\n"
        f"- link: {url or '(none)'}\n"
    )
    if note:
        body += f"- note: {note}\n"
    dest.write_text(body, encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Start the session agent's scheduled loop")
    ap.add_argument("--repo", default="madnessgate44-debug/brain")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--task-file", default="docs/SESSION_LOOP_TASK.md")
    ap.add_argument("--title", default="Session agent loop — find and fix a real defect")
    ap.add_argument("--out", default="watcher/knowledge/evidence")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    task = Path(a.task_file).read_text(encoding="utf-8").strip()
    payload = build_payload(task, a.repo, a.branch, a.title)
    key = os.environ.get(KEY_ENV, "").strip()

    if a.dry_run or not key:
        reason = "dry run" if a.dry_run else f"{KEY_ENV} is not set"
        print(f"[{reason}] would POST {API}/app-conversations with:")
        print(json.dumps(payload, indent=2)[:800])
        dest = write_evidence(Path(a.out), a.repo, a.branch, "", "", dry=True)
        print(f"evidence: {dest}")
        return 0

    started = _post(f"{API}/app-conversations", payload, key)
    start_id, conv_id = parse_start_task(started)
    if not conv_id:
        try:
            conv_id = wait_for_ready(start_id, key)
        except RuntimeError as exc:
            # The conversation was started; record that fact so the run is not invisible, but
            # there is no link yet, so this does not count as a proven live run (see purpose_audit).
            dest = write_evidence(
                Path(a.out),
                a.repo,
                a.branch,
                "",
                "",
                dry=False,
                note=f"started start-task {start_id} but it was not ready: {exc}",
            )
            print(f"conversation started but not ready: {exc}")
            print(f"evidence: {dest}")
            return 1
    url = ui_url(conv_id, key)
    dest = write_evidence(Path(a.out), a.repo, a.branch, conv_id, url, dry=False)
    print(f"conversation started: {url}")
    print(f"evidence: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
