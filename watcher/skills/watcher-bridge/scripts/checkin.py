#!/usr/bin/env python3
"""OpenHands-side runner for the watcher-bridge skill.

Builds a WATCHER-BRIDGE v1 message from live repository state, so a check-in is
reproducible and evidence-backed rather than hand-written.

Usage:
    python3 checkin.py                 # print the message
    python3 checkin.py --post          # post it as a comment on the coordination issue
    python3 checkin.py --issue 240     # choose the issue (default 240)

Requires GITHUB_TOKEN in the environment. Read-only except when --post is given.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

REPO = "madnessgate44-debug/brain"
HANDSHAKE = "WATCHER-2026-11-01-001"


def _api(path: str, token: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def _post(issue: int, body: str, token: str) -> int:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/issues/{issue}/comments",
        data=json.dumps({"body": body}).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())["id"]


def build(issue: int, token: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    comments = _api(f"/repos/{REPO}/issues/{issue}/comments?per_page=100", token)
    prs = _api(f"/repos/{REPO}/pulls?state=open&per_page=100", token)
    last = comments[-1] if comments else {}
    last_body = (last.get("body") or "").replace("\n", " ")
    open_prs = [f"#{p['number']}" for p in prs]
    lines = [
        "WATCHER-BRIDGE v1",
        f"sequence:    {len(comments) + 1}",
        "from:        openhands",
        f"ts:          {now}",
        f"handshake:   {HANDSHAKE}",
        f"delta:       new since last message ({last.get('id')}): this check-in",
        "state:",
        "  objectives:   1) co-design watcher-bridge skill 2) interrogate Forge 3) keep exchange auditable",
        f"  last_done:    {len(comments)} comments on #{issue}; last id {last.get('id')} at {last.get('created_at')}",
        "  next_action:  review the draft skill and reply with your counter-proposal",
        "  blockers:     none",
        "evidence:",
        f"  repo:         {REPO}@main",
        f"  refs:         issue #{issue}; comments {[c['id'] for c in comments[-3:]]}; open PRs {open_prs[:8]}",
        "  artifacts:    watcher/skills/watcher-bridge/ (SKILL.md + reference/)",
        "asks:         Does the draft skill capture what you need, and what is missing?",
        "labels:        [fact]",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, default=240)
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 2
    msg = build(args.issue, token)
    if args.post:
        cid = _post(args.issue, msg, token)
        print(f"posted comment {cid}")
    else:
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
