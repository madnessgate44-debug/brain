"""Post a concise daily checkpoint to Brain issue #292.

Deterministic and free: no model, no spend. Reads the issue, open PRs and recent
workflow runs through the GitHub API, diffs a fingerprint against the previous
checkpoint comment, and posts an evidence-based update (or a "no material
change" note). The fingerprint lives in a hidden marker inside the comment, so
no repo state needs to be committed.

Usage:
    GH_TOKEN=<token> python3 scripts/checkpoint.py --label 06:00
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
ISSUE = 292
MARKER = "<!-- brain-checkpoint -->"
API = "https://api.github.com"
CAIRO = timezone(timedelta(hours=2))  # EET (no DST in November)


def api(path: str) -> object:
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "brain-checkpoint")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def post_comment(body: str) -> dict:
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(f"{API}/repos/{REPO}/issues/{ISSUE}/comments", data=data)
    req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "brain-checkpoint")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def previous_checkpoint() -> tuple[dict, dict]:
    """Return (previous fingerprint, metadata) from the last checkpoint comment."""
    comments = api(f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100")
    for c in reversed(comments):
        if MARKER in c["body"]:
            m = re.search(r"fingerprint:([0-9a-f]{12})", c["body"])
            return ({"id": m.group(1)} if m else {}, {"id": c["id"], "at": c["created_at"]})
    return {}, {}


def current_state() -> dict:
    comments = api(f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100")
    last_comment = comments[-1]["id"] if comments else 0
    commit = api(f"/repos/{REPO}/commits?per_page=1")[0]
    prs = api(f"/repos/{REPO}/pulls?state=open&per_page=100")
    runs = api(f"/repos/{REPO}/actions/runs?per_page=5")["workflow_runs"]
    return {
        "last_comment": last_comment,
        "main_sha": commit["sha"][:12],
        "main_msg": commit["commit"]["message"].splitlines()[0][:80],
        "open_prs": sorted((p["number"], p["head"]["sha"][:12]) for p in prs),
        "runs": sorted((r["id"], r["conclusion"] or r["status"]) for r in runs),
    }


def fingerprint(state: dict) -> str:
    blob = json.dumps(state, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="checkpoint label, e.g. 06:00")
    ap.add_argument("--dry-run", action="store_true", help="print the checkpoint, do not post")
    a = ap.parse_args()

    now_utc = datetime.now(timezone.utc)
    now_cairo = now_utc.astimezone(CAIRO)
    state = current_state()
    fp = fingerprint(state)
    prev_fp, prev_meta = previous_checkpoint()

    same = prev_fp.get("id") == fp
    head = "no material change since the last checkpoint" if same else "material change detected"

    runs = state["runs"][:3]
    run_lines = "\n".join(f"- run `{rid}` — {concl}" for rid, concl in runs)
    pr_lines = "\n".join(f"- PR #{n} @ `{sha}`" for n, sha in state["open_prs"]) or "- none open"

    body = f"""{MARKER}
## CHECKPOINT · {a.label} Cairo ({now_cairo:%Y-%m-%d %H:%M}) — {head}

**UTC** {now_utc:%Y-%m-%dT%H:%M:%SZ} · **Cairo** {now_cairo:%Y-%m-%d %H:%M} · label `{a.label}` · fingerprint:{fp}

### Evidence
- issue #292 latest comment: `{state['last_comment']}`
- `main` @ `{state['main_sha']}` — {state['main_msg']}
- open PRs:
{pr_lines}
- recent workflow runs:
{run_lines}

### Status (tags)
- Brain control plane, Watcher coordination, GitHub #292 durable channel — `[V]`
- Shadow independent audit — `[B]` (Gemini pool: run the `shadow-keys` sweep for live PASS/FAIL)
- ChatGPT↔Brain MCP round trip — `[B: connector not mounted in ChatGPT session]` (parked)
- Amina first priority, one-week deadline — protected `[V]` (see `BRAIN_CONTEXT.md`)

### Owner / next action
- accountable: OpenHands · coordinator: Watcher
- next action: {('none — no material change' if same else 'inspect the changed PR/commit above and act')}

_Posted by the `brain-checkpoints` workflow (deterministic, no model). This checkpoint was created by an AI agent (OpenHands) on behalf of the owner._
"""

    if a.dry_run:
        print(body)
        print(f"[dry-run] would post checkpoint {a.label} ({head})")
        return 0

    posted = post_comment(body)
    print(f"posted checkpoint {a.label}: {posted['html_url']} ({head})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
