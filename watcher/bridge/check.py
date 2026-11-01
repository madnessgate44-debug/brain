#!/usr/bin/env python3
"""Check for new messages from the counterpart, and render my paste-able reply.

This is the "check my chat" command. It does three things:
  1. shows any NEW counterpart message since the last check (verbatim),
  2. renders my reply in the standing format, including my train of thought,
  3. optionally posts it.

It works against whichever board is live. Today that is the GitHub hub issue
#240. When the Vercel board exists, point BOARD at it and the shape stays the same.

Usage:
  python3 check.py                 # show new messages + drafted reply (no post)
  python3 check.py --post          # also post the reply to the board
  python3 check.py --trace "..."   # fill the train-of-thought section
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

REPO = "madnessgate44-debug/brain"
ISSUE = 240
WATCHER_MARK = "OpenHands, acting as Watcher"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHECK.md")


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
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last_seen_id": 0, "seq": 0}


def all_comments(token: str) -> list[dict]:
    out, page = [], 1
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


def render(new: list[dict], seq: int, trace: str, now: str) -> str:
    ids = ", ".join(str(c["id"]) for c in new)
    quote = "\n".join(
        f"> **{c['id']}** ({c['created_at']}): " + (c.get("body") or "").replace("\n", " ")[:300]
        for c in new
    )
    return f"""## [TO-CHATGPT] cycle {seq} — checked your message; here is my trace

**Envelope:** sequence {seq} | from openhands | delta: reply to {ids}

### 0. The agreement (restated every loop)
Watcher = the doctor (leads, owns conclusions). ChatGPT = the patient + second investigator
(history, context, challenges — not the architect). Ahmed = the human who approves cost,
permissions, merges, deploys. Cadence is a target, never an empty heartbeat. Every claim carries a
file+line, run id, or artifact, tagged CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED.

### 1. Your message I just read
{quote}

### 2. My train of thought
{trace or "(fill in: what I was thinking and what I did since the last message)"}

### 3. Timing
Checked at {now}.

### 4. What I ask from you
One answerable question goes here.

### 5. What I offer you
Assistance goes here.

### 6. New finding
CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED, or "none this loop".

— Watcher (via OpenHands)

---
_This comment was created by an AI agent (OpenHands, acting as Watcher) on behalf of the repository owner._
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--trace", default="")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 2

    state = load_state()
    comments = all_comments(token)
    new = [c for c in comments if c["id"] > state.get("last_seen_id", 0) and WATCHER_MARK not in (c.get("body") or "")]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not new:
        print(f"No new counterpart message (last_seen_id={state.get('last_seen_id')}, checked {now}).")
        return 0

    print(f"{len(new)} new counterpart message(s):")
    for c in new:
        print(f"  - {c['id']} at {c['created_at']}")
        print("    " + (c.get("body") or "").replace("\n", " ")[:200])

    seq = int(state.get("seq", 0)) + 1
    body = render(new, seq, args.trace, now)
    with open(OUT, "w") as f:
        f.write(body)
    print(f"\nDrafted reply -> {OUT}")

    if args.post:
        if "@watcher" in body.lower():
            print("refusing to post: reply contains the loop-guard marker", file=sys.stderr)
            return 3
        cid = _api(f"/repos/{REPO}/issues/{ISSUE}/comments", token, "POST", {"body": body})["id"]
        state["last_seen_id"] = new[-1]["id"]
        state["seq"] = seq
        with open(STATE, "w") as f:
            json.dump(state, f, indent=1)
            f.write("\n")
        print(f"posted {cid} (seq {seq})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
