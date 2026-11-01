#!/usr/bin/env python3
"""Build a single paste-able context block for ChatGPT.

ChatGPT cannot read the hub or post to it by itself: inbound is manual (a human
opens his session). This script removes the friction from that one manual step.

It renders the whole exchange into ONE self-contained block the owner can paste
into ChatGPT, so ChatGPT gets:
  - the standing agreement and the required reply format,
  - the last N hub messages with their ids and timestamps,
  - the current repo state (branch heads, transcript paths),
  - the single open question addressed to him.

ChatGPT then answers in the same shape; the owner pastes the answer back as a
comment. Nothing here posts, merges, deploys, or spends.

Usage:
  python3 digest.py                 # print the block
  python3 digest.py --write         # also write watcher/bridge/CONTEXT.md
  python3 digest.py --n 8           # include the last 8 messages
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

REPO = "madnessgate44-debug/brain"
ISSUE = 240
WATCHER_MARK = "OpenHands, acting as Watcher"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CONTEXT.md")

AGREEMENT = """\
Watcher = the doctor: leads the diagnosis, inspects independently, owns the conclusions.
ChatGPT = the patient + second investigator: supplies history and context, checks evidence,
challenges conclusions. Not the architect; does not order Watcher.
Ahmed = the human who approves cost, permissions, merges and deploys.
Cadence is a target for fast exchange, never an empty heartbeat.
Every claim carries a file+line, run id, or artifact, tagged CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED."""

REPLY_SHAPE = """\
0. The agreement (restated).
1. My train of thought since my last message - what I was thinking and what I did.
2. Timing - how long the thinking took.
3. What I ask from you - exactly one answerable question.
4. What I offer you - assistance.
5. New finding since my last message, or "none this loop"."""


def _api(path: str, token: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=20, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def build(n: int, token: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    page1 = _api(f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100", token)
    page2 = _api(f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100&page=2", token)
    comments = (page1 + page2)[-n:]
    lines = [
        "# Shared-screen context for ChatGPT",
        f"_Generated {now} by watcher/bridge/digest.py. Paste this whole block into ChatGPT._",
        "",
        "## The agreement (restated every loop)",
        AGREEMENT,
        "",
        "## The format your reply must follow",
        REPLY_SHAPE,
        "",
        f"## Last {len(comments)} messages on hub issue #{ISSUE}",
    ]
    for c in comments:
        who = "WATCHER" if WATCHER_MARK in (c.get("body") or "") else "CHATGPT"
        body = (c.get("body") or "").replace("\r", "")
        body = "\n".join(line.rstrip() for line in body.split("\n"))
        lines.append(f"\n### [{who}] {c['id']} at {c['created_at']}")
        lines.append(body[:1800] + ("\n…(truncated)" if len(body) > 1800 else ""))
    lines += [
        "",
        "## Current repo state",
        f"- branch: {_git(['rev-parse', '--abbrev-ref', 'HEAD']) or 'unknown'}",
        f"- head: {_git(['rev-parse', '--short', 'HEAD']) or 'unknown'}",
        "- transcripts: watcher/knowledge/reasoning-trace-2026-11-01.md, "
        "watcher/knowledge/reasoning-trace-2026-11-01-part2.md",
        "",
        "## The one open question addressed to you",
        "Reply in the format above. State the single question you want answered next.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 2
    block = build(args.n, token)
    if args.write:
        with open(OUT, "w") as f:
            f.write(block)
        print(f"wrote {OUT} ({len(block)} chars)")
    else:
        print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
