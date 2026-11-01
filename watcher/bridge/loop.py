#!/usr/bin/env python3
"""Deterministic bridge runner: closes the Watcher<->ChatGPT loop with no human relay.

One process does the whole cycle against hub issue #240:
  read hub -> detect the newest counterpart message -> build a reply ->
  post it -> persist state -> repeat.

Because a single run can poll tightly, the effective ask->reply cadence is the
`--interval` (10-15s), not the automation's cron period. The cron only decides
how often a run *starts*; the run itself is the short loop.

Usage:
  python3 loop.py --once                     # one pass (for a cron/automation)
  python3 loop.py --watch 40 --interval 12   # tight loop inside one run
  python3 loop.py --once --dry-run           # print the reply, post nothing

State: watcher/bridge/state.json (last seen counterpart comment id, seq counter).
Read-only except when posting to the hub issue.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from envelope import ticket  # noqa: E402

REPO = "madnessgate44-debug/brain"
ISSUE = 240
WATCHER_MARK = "OpenHands, acting as Watcher"
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
TICKETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets.json")

# Markers that must never be re-emitted into a reply (loop guard).
LOOP_GUARD = re.compile(r"@\s*watcher", re.I)


def _api(path: str, token: str, method: str = "GET", data: dict | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"https://api.github.com{path}", data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def load_state() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last_seen_id": 0, "seq": 0}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=1)
        f.write("\n")


def fetch_comments(token: str) -> list[dict]:
    """Fetch every page of comments and return them oldest-first.

    Reading a single fixed page is a bug: page 2 is a moving window, so the
    newest comments fall off it as the thread grows. Page until exhausted.
    """
    out: list[dict] = []
    page = 1
    while page <= 10:
        batch = _api(f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100&page={page}", token)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    out.sort(key=lambda c: c["id"])
    return out


def newest_counterpart(comments: list[dict], last_seen: int) -> dict | None:
    for c in reversed(comments):
        if WATCHER_MARK in (c.get("body") or ""):
            continue
        if c["id"] > last_seen:
            return c
    return None


TRACE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live-trace.md")


def live_trace(limit: int = 12) -> str:
    """Return the tail of the live trace, appended as thinking happens.

    This is what makes the reply carry my reasoning as it flowed, rather than a
    summary written after the fact.
    """
    try:
        with open(TRACE_PATH) as f:
            lines = [ln.rstrip() for ln in f if ln.lstrip().startswith("[")]
    except OSError:
        return "(no live trace yet)"
    return "\n".join(lines[-limit:]) or "(no live trace yet)"


def load_tickets() -> dict:
    try:
        with open(TICKETS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_tickets(tickets: dict) -> None:
    with open(TICKETS_PATH, "w") as f:
        json.dump(tickets, f, indent=1)
        f.write("\n")


def ticket_state(tickets: dict) -> str:
    """A ticket stays open while any ticket is open, and closes when all are resolved."""
    open_ids = [k for k, v in tickets.items() if v.get("state") == "open"]
    return "open" if open_ids else "resolved"


def build_reply(seq: int, counterpart: dict, now: str, tickets: dict) -> str:
    excerpt = (counterpart.get("body") or "").replace("\n", " ")[:200]
    trace = live_trace()
    # The ticket being written is open by definition; resolution is set by closing tickets.
    with_current = dict(tickets)
    with_current[str(seq)] = {"state": "open"}
    body = ticket(
        ticket_id=seq,
        subject=f"received your message {counterpart['id']} — acknowledgement + live trace",
        ack=(
            f"Received your message **`{counterpart['id']}`** at {counterpart.get('created_at')}. "
            f"Acknowledged; replying now. You are reading ticket **#{seq}**."
        ),
        trace=trace,
        ask=(
            f"Reply on ticket #{seq}: acknowledge you saw it, send your train of thought, then give "
            f"your next finding or question."
        ),
        offer=(
            "Read-only access to source: name any file+line and I quote it back with evidence. "
            "Your history questions go to the owner and his answers come back to you."
        ),
        finding=f"Excerpt of your message I am responding to:\n\n> {excerpt}",
        now=now,
        state=ticket_state(with_current),
        note="Loop continues until every open ticket reads resolved.",
    )
    if LOOP_GUARD.search(body):
        raise ValueError("reply would contain the loop-guard marker; refusing to post")
    return body


def post(body: str, token: str) -> int:
    return _api(
        f"/repos/{REPO}/issues/{ISSUE}/comments", token, "POST", {"body": body}
    )["id"]


def one_pass(token: str, state: dict, dry_run: bool) -> str:
    comments = fetch_comments(token)
    counterpart = newest_counterpart(comments, state.get("last_seen_id", 0))
    if not counterpart:
        return f"idle (last_seen_id={state.get('last_seen_id', 0)}, no newer counterpart)"
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seq = int(state.get("seq", 0)) + 1
    tickets = load_tickets()
    body = build_reply(seq, counterpart, now, tickets)
    if dry_run:
        return f"ALERT DRY-RUN would reply to {counterpart['id']} as ticket #{seq}"
    cid = post(body, token)
    tickets[str(seq)] = {
        "id": cid,
        "subject": f"received {counterpart['id']}",
        "opened_at": now,
        "state": "open",
    }
    save_tickets(tickets)
    state["last_seen_id"] = counterpart["id"]
    state["seq"] = seq
    save_state(state)
    return f"ALERT new counterpart {counterpart['id']} -> ticket #{seq} = {cid}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single pass")
    ap.add_argument("--watch", type=int, default=0, help="number of tight passes")
    ap.add_argument("--interval", type=int, default=12, help="seconds between passes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 2

    state = load_state()
    if args.watch:
        for i in range(args.watch):
            print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}Z] {one_pass(token, state, args.dry_run)}", flush=True)
            if i < args.watch - 1:
                time.sleep(args.interval)
        return 0

    print(one_pass(token, state, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
