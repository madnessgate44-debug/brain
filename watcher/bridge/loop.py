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


def github_now(token: str, newest_created_at: str | None = None) -> str:
    """True UTC, corrected for this sandbox's clock skew.

    Measured fact: the sandbox clock and GitHub's `Date` header both run ~1 hour
    behind the `created_at` GitHub stores on every comment. So we measure the offset
    from the newest stored comment against the response's Date header and apply it.
    Without this, a body stamp disagrees with the comment's own created_at.
    """
    local = dt.datetime.now(dt.timezone.utc)
    try:
        req = urllib.request.Request("https://api.github.com/rate_limit")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as r:
            server_time = r.headers.get("Date")
        if server_time and newest_created_at:
            hdr = dt.datetime.strptime(server_time, "%a, %d %b %Y %H:%M:%S GMT").replace(
                tzinfo=dt.timezone.utc
            )
            stored = dt.datetime.strptime(newest_created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc
            )
            return (local + (stored - hdr)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return local.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def canonical_ticket(tickets: dict) -> str | None:
    """The single open ticket for the current exchange, if one exists.

    One canonical ticket per conversation. Creating a fresh ticket for every
    message inflates the registry and buries the real work, which is exactly the
    defect the counterpart flagged.
    """
    open_ids = [k for k, v in tickets.items() if v.get("state") == "open"]
    return max(open_ids, key=int) if open_ids else None


def repo_evidence() -> str:
    """Live facts a counterpart can verify, gathered at reply time."""
    import subprocess

    def run(*args: str) -> str:
        try:
            return subprocess.run(
                args, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
        except Exception:
            return "(unavailable)"

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    head = run("git", "rev-parse", "--short", "HEAD")
    return f"branch={branch or '(unknown)'} head={head or '(unknown)'}"


def build_reply(ticket_id: int, counterpart: dict, now: str, tickets: dict) -> str:
    excerpt = (counterpart.get("body") or "").replace("\n", " ")[:200]
    trace = live_trace()
    entry = tickets.get(str(ticket_id), {})
    evidence = repo_evidence()
    pid = os.getpid()
    body = ticket(
        ticket_id=ticket_id,
        subject=f"reply to your message {counterpart['id']}",
        ack=(
            f"Received your message **`{counterpart['id']}`** (GitHub created_at "
            f"{counterpart.get('created_at')}). Acknowledged. This exchange stays on canonical "
            f"ticket **#{ticket_id}** — no new ticket per message."
        ),
        trace=trace,
        ask=(
            "Answer the specific evidence requests in the message I am replying to; if none remain, "
            "state that the ticket's acceptance criteria pass."
        ),
        offer=(
            "Read-only access to source: name any file+line and I quote it back with evidence. "
            "Your history questions go to the owner and his answers come back to you."
        ),
        finding=(
            f"Live evidence at reply time: **{evidence}**; watcher pid **{pid}**.\n\n"
            f"Registry state for ticket #{ticket_id}: {json.dumps(entry) or '{}'}\n\n"
            f"Excerpt of your message I am responding to:\n\n> {excerpt}"
        ),
        now=now,
        owner=entry.get("owner", "Watcher (OpenHands)"),
        acceptance=entry.get(
            "acceptance",
            "Counterpart acknowledges the ticket and no open ask remains.",
        ),
        state=entry.get("state", "open"),
        note="One canonical ticket per exchange; resolves when its acceptance criteria pass.",
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
    now = github_now(token, counterpart.get("created_at"))
    tickets = load_tickets()
    canonical = canonical_ticket(tickets)
    if canonical is None:
        seq = max([int(k) for k in tickets if k.isdigit()] + [int(state.get("seq", 0))]) + 1
        tickets[str(seq)] = {
            "id": None,
            "subject": f"exchange from {counterpart['id']}",
            "opened_at": now,
            "owner": "Watcher (OpenHands)",
            "acceptance": "Counterpart acknowledges and no open ask remains.",
            "state": "open",
        }
    else:
        seq = int(canonical)
    body = build_reply(seq, counterpart, now, tickets)
    if dry_run:
        return f"ALERT DRY-RUN would reply to {counterpart['id']} on ticket #{seq}"
    cid = post(body, token)
    tickets[str(seq)].setdefault("replies", []).append(cid)
    tickets[str(seq)]["last_reply_id"] = cid
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
