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
    python3 scripts/start_session_loop.py --record <evidence.md>
                                          --issue <issue URL> --pull-request <PR URL>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://app.all-hands.dev/api/v1"
KEY_ENV = "OPENHANDS_API_KEY"
AUDIT = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "purpose_audit.py"


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
                time.sleep(min(2 ** attempt, 20))
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
                time.sleep(min(2 ** attempt, 20))
                continue
            raise
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last}")


def _first(payload: object) -> dict:
    """Return the first record from a V1 `?ids=` response.

    Those endpoints return a JSON *list* of records (the reference client's
    `app_conversations_get_batch` returns `r.json()` unchanged); a missing id comes back as
    `[null]`. Some deployments wrap the same data as `{"items": [...]}`. Accept both shapes, and
    treat `null`/empty as "no record" — never assume the payload is a dict.
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
    return first.get("conversation_ui_url") or f"https://app.all-hands.dev/canvas/conversations/{conv_id}"


def write_evidence(out_dir: Path, repo: str, branch: str, conv_id: str, url: str, dry: bool,
                   note: str = "") -> Path:
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


def _load_audit():
    """Load the depth check so this writer validates with the checker's own rules."""
    spec = importlib.util.spec_from_file_location("watcher_purpose_audit", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_url() -> str:
    """The workflow run this process is executing, when it is running inside Actions."""
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    return f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""


def record_trace(evidence: Path, issue: str, pull_request: str, run: str = "") -> Path:
    """Record the issue -> pull request trace in an existing evidence file.

    A `- link:` to a started conversation proves the loop started, not that it carried an issue
    to a pull request (W3), and an issue plus a pull request proves both exist, not that *this
    run* produced them. The trace therefore records the run too, taken from `--run` or from the
    Actions environment. The candidate text is parsed by `purpose_audit.evidence_trace` before it
    replaces the file, so this writer cannot emit a trace the audit would reject.
    """
    audit = _load_audit()
    status = "Status: LIVE — issue carried to a pull request"
    run = (run or _run_url()).strip()
    kept = [
        line for line in evidence.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith(("- issue:", "- pull_request:", "- run:", "- workflow run:"))
    ]
    # Rebuild the header: drop the old status line and the blank line that followed it.
    if any(line.startswith("Status:") for line in kept):
        at = next(i for i, line in enumerate(kept) if line.startswith("Status:"))
        del kept[at]
        while at < len(kept) and not kept[at].strip():
            del kept[at]
        while at > 0 and not kept[at - 1].strip():
            del kept[at - 1]
            at -= 1
    while kept and not kept[-1].strip():
        kept.pop()
    at = 1 if kept and kept[0].startswith("# ") else 0
    kept[at:at] = [status, ""]
    fields = [f"- issue: {issue.strip()}", f"- pull_request: {pull_request.strip()}"]
    if run:
        fields.append(f"- run: {run}")
    note_at = next(
        (i for i, line in enumerate(kept) if line.strip().startswith("- note:")), len(kept)
    )
    candidate = "\n".join(kept[:note_at] + fields + kept[note_at:]) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as probe:
        probe.write(candidate)
        probe_path = Path(probe.name)
    try:
        trace = audit.evidence_trace(probe_path)
    finally:
        probe_path.unlink()
    if (trace["issue"] != issue.strip() or trace["pull_request"] != pull_request.strip()
            or not trace["run"] or (run and trace["run"] != run)):
        raise ValueError(
            "the depth check would reject this trace: it needs "
            "https://github.com/<owner>/<repo>/issues/<n>, /pull/<n> and /actions/runs/<id> on "
            "one repository — pass --run or set GITHUB_REPOSITORY and GITHUB_RUN_ID"
        )
    evidence.write_text(candidate, encoding="utf-8")
    return evidence


def main() -> int:
    ap = argparse.ArgumentParser(description="Start the session agent's scheduled loop")
    ap.add_argument("--repo", default="madnessgate44-debug/brain")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--task-file", default="docs/SESSION_LOOP_TASK.md")
    ap.add_argument("--title", default="Session agent loop — find and fix a real defect")
    ap.add_argument("--out", default="watcher/knowledge/evidence")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record", metavar="EVIDENCE", default="",
                    help="record the issue -> PR trace in an existing evidence file and exit")
    ap.add_argument("--issue", default="", help="the GitHub issue URL this run carried")
    ap.add_argument("--pull-request", default="", help="the GitHub pull request URL this run opened")
    ap.add_argument("--run", default="",
                    help="the actions run URL that produced it (defaults to this run)")
    a = ap.parse_args()

    if a.record:
        if not (a.issue and a.pull_request):
            print("--record needs --issue and --pull-request", file=sys.stderr)
            return 2
        try:
            dest = record_trace(Path(a.record), a.issue, a.pull_request, a.run)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"trace recorded: {dest}")
        return 0

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
            dest = write_evidence(Path(a.out), a.repo, a.branch, "", "", dry=False,
                                  note=f"started start-task {start_id} but it was not ready: {exc}")
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
