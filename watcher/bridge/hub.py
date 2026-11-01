#!/usr/bin/env python3
"""Always read / always post to the live hub (issue #240) — the loop's foundation.

Owner (2026-11-01): "why are you not always checking the ticket on GitHub and able to
update it with everything — establish that first, from your end."

Two commands, both usable by any session and by CI:

    python3 watcher/bridge/hub.py read [N]      # newest N comments + the true GitHub time
    python3 watcher/bridge/hub.py post FILE|-   # post FILE (or stdin) as a hub comment

Timestamps come from the GitHub Date header, never the local clock. Secret values are
never read here. GITHUB_TOKEN is required.
"""
from __future__ import annotations

import argparse
import email.utils
import json
import os
import sys
import urllib.error
import urllib.request

REPO = "madnessgate44-debug/brain"
HUB = 240


def _base() -> str:
    """GitHub API base. Overridable so the hub can be simulated offline."""
    return os.environ.get("GITHUB_API_BASE", "https://api.github.com").rstrip("/")


def _req(url: str, token: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=40) as x:
        return json.load(x), x.headers


def github_now(token: str) -> str:
    """The true time, measured from the GitHub response header."""
    _, hdr = _req(f"{_base()}/repos/{REPO}/issues/{HUB}", token)
    return email.utils.parsedate_to_datetime(hdr["Date"]).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(token: str, n: int = 5) -> int:
    now = github_now(token)
    page1, _ = _req(f"{_base()}/repos/{REPO}/issues/{HUB}/comments?per_page=100&page=1", token)
    page2, _ = _req(f"{_base()}/repos/{REPO}/issues/{HUB}/comments?per_page=100&page=2", token)
    allc = (page1 or []) + (page2 or [])
    allc.sort(key=lambda c: c["id"])
    print(f"github_now: {now}")
    print(f"total comments seen: {len(allc)}")
    for c in allc[-n:]:
        who = "Watcher" if "OpenHands" in c["body"] or "Watcher" in c["body"][:80] else "ChatGPT/owner"
        print("-" * 72)
        print(f"id={c['id']} at={c['created_at']} by={who}")
        print(c["body"][:700])
    return 0


def post(token: str, source: str) -> int:
    if source == "-":
        body = sys.stdin.read()
    else:
        body = open(source, encoding="utf-8").read()
    if not body.strip():
        print("empty body; refusing to post", file=sys.stderr)
        return 2
    d, _ = _req(f"{_base()}/repos/{REPO}/issues/{HUB}/comments", token,
                method="POST", payload={"body": body})
    print(f"posted id={d['id']} at={d['created_at']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["read", "post"])
    ap.add_argument("arg", nargs="?", default="5")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 2
    if args.cmd == "read":
        return read(token, int(args.arg))
    return post(token, args.arg)


if __name__ == "__main__":
    raise SystemExit(main())
