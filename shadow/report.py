#!/usr/bin/env python3
"""Shadow's report and sweep jobs (WATCHER.md §3, §5).

Two duties the auditor alone did not cover:
  --report   : the 09:00 / 21:00 status report to Ahmed (open work, blockers, decisions).
  --sweep    : the hourly backstop — audit any open non-draft PR that has no Shadow verdict yet.

Values are never printed; only labels and status codes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

REPO = os.environ.get("SHADOW_REPO", "madnessgate44-debug/brain")
HUB_ISSUE = int(os.environ.get("SHADOW_HUB_ISSUE", "240"))
MARK = "Shadow (audit)"


def _gh(path: str, method: str = "GET", body: dict | None = None) -> object:
    token = os.environ.get("GITHUB_TOKEN", "")
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.code}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def _has_shadow_verdict(pr_number: int) -> bool:
    comments = _gh(f"/repos/{REPO}/issues/{pr_number}/comments?per_page=100")
    if not isinstance(comments, list):
        return False
    return any("Shadow audit" in (c.get("body") or "") for c in comments)


def _open_prs() -> list[dict]:
    prs = _gh(f"/repos/{REPO}/pulls?state=open&per_page=50")
    return prs if isinstance(prs, list) else []


def sweep() -> int:
    """Hourly backstop: audit open non-draft PRs with no Shadow verdict yet."""
    from shadow import audit  # local import; shadow.py is in this directory

    done = 0
    for pr in _open_prs():
        n = pr["number"]
        if pr.get("draft"):
            continue
        if _has_shadow_verdict(n):
            continue
        verdict = audit(f"PR #{n}: {pr['title']}", pr=n)
        _gh(f"/repos/{REPO}/issues/{n}/comments", "POST",
            {"body": f"## Shadow audit (hourly sweep)\n\n{verdict}\n\n_AI agent audit._"})
        done += 1
    print(f"sweep: audited {done} PR(s) with no prior verdict")
    return done


def _registry_summary() -> str:
    path = os.path.join(HERE, "registry.md")
    if not os.path.isfile(path):
        return "registry.md absent"
    rows = [l for l in open(path) if l.startswith("| ") and "---" not in l]
    working = sum(1 for r in rows if "WORKING" in r)
    return f"{len(rows)} registered rows, {working} WORKING"


def report() -> str:
    prs = _open_prs()
    lines = [f"## Shadow report — {os.environ.get('SHADOW_TS', '')}".rstrip()]
    lines.append("")
    lines.append(f"Pool: {_registry_summary()}")
    lines.append(f"Open PRs: {len(prs)}")
    for pr in prs:
        gate = "audited" if _has_shadow_verdict(pr["number"]) else "NO VERDICT"
        lines.append(f"- #{pr['number']} draft={pr.get('draft')} [{gate}] {pr['title']}")
    lines.append("")
    lines.append("Decisions needed: none automated. Irreversible actions still await Shadow audit.")
    body = "\n".join(lines)
    if os.environ.get("SHADOW_DRY_RUN"):
        return body
    _gh(f"/repos/{REPO}/issues/{HUB_ISSUE}/comments", "POST", {"body": body})
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description="Shadow report / sweep jobs")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()
    if a.sweep:
        sweep()
    elif a.report:
        print(report())
    else:
        ap.error("choose --report or --sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
