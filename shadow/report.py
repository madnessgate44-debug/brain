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
        try:
            verdict = audit(f"PR #{n}: {pr['title']}", pr=n)
        except Exception as exc:  # noqa: BLE001 - no model route must not crash the sweep
            verdict = (f"VERDICT: BLOCKED\nFINDINGS:\n- Shadow could not run — CONFIRMED — "
                       f"{type(exc).__name__}.\nWEAKEST POINT: no model route is configured.\n"
                       f"FIX: add the pool secrets (WATCHER.md §14.2).")
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


def _verdict_line(bodies: list[str]) -> str:
    """The most recent Shadow verdict line, e.g. 'VERDICT: VERIFIED'. Empty if none."""
    verdict = next((b for b in reversed(bodies) if "Shadow audit" in b), "")
    return next((l for l in verdict.splitlines() if l.startswith("VERDICT:")), "")


def _needs_fix(bodies: list[str]) -> bool:
    """True only when a PR has a REJECTED/PARTIAL verdict and no fix handed back yet.

    BLOCKED (no model route) and empty verdicts are not handed a fix.
    """
    if any("Shadow fix proposal" in b for b in bodies):
        return False
    verdict = _verdict_line(bodies)
    return "REJECTED" in verdict or "PARTIAL" in verdict


def fix() -> int:
    """Counter power, part (b): for each open PR whose Shadow verdict was not Verified,
    post the fix Shadow already produced, handed back to the author. Idempotent."""
    posted = 0
    for pr in _open_prs():
        n = pr["number"]
        if pr.get("draft"):
            continue
        comments = _gh(f"/repos/{REPO}/issues/{n}/comments?per_page=100")
        if not isinstance(comments, list):
            continue
        bodies = [c.get("body") or "" for c in comments]
        if not _needs_fix(bodies):
            continue
        verdict_comment = next((b for b in reversed(bodies) if "Shadow audit" in b), "")
        fix_line = next((l for l in verdict_comment.splitlines() if l.startswith("FIX:")), "FIX: (none recorded)")
        body = (f"## Shadow fix proposal (WATCHER.md §1)\n\n"
                f"The latest audit of this PR was not Verified. Handing the fix back:\n\n"
                f"{fix_line}\n\n_AI agent (OpenHands) on behalf of the owner._")
        _gh(f"/repos/{REPO}/issues/{n}/comments", "POST", {"body": body})
        posted += 1
    print(f"fix: handed back {posted} fix proposal(s)")
    return posted


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
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    if a.sweep:
        sweep()
    elif a.fix:
        fix()
    elif a.report:
        print(report())
    else:
        ap.error("choose --report, --sweep, or --fix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
