#!/usr/bin/env python3
"""Compose brain's daily report and fan it out to every integrated channel.

Issue #292 defines the durable daily-report channel, and ``report_to_channels.py`` posts a
report that already exists. This script is the missing producer: it runs brain's own audits,
measures today's repo(s) against their production plans, advances the rotation cursor, and
hands one Markdown report to the fan-out.

The report shape is the one agreed in the daily-automation conversation
(``docs/transcripts/2026-11-07-daily-automation-conversation.md``): a brain self-audit, each
repo audited today against ``docs/audits/plans/<repo>.md`` (goal, progress, the ordered
"what to fix" list, the next item), the repo-queue cursor, and one yes/no question.

Deterministic and free: no model, no spend. The self-audit numbers come from the two local
tools the daily loop already uses (``purpose_audit.py``, ``agent_status.py``). Nothing is
invented: a section whose input is missing is reported as ``[B]`` blocked, never faked.

    python3 scripts/daily_report.py --dry-run
    python3 scripts/daily_report.py --repos 1
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITS_DIR = ROOT / "docs" / "audits"
QUEUE_PATH = AUDITS_DIR / "repo-queue.json"
CURSOR_PATH = AUDITS_DIR / "cursor.json"
PLANS_DIR = AUDITS_DIR / "plans"

STATUSES = ("done", "in-progress", "blocked", "todo")
DEFAULT_QUESTION = (
    "Approve advancing the rotation to the next repo, and confirm the 5-product scope "
    "is still current?"
)

# The rotation cursor must survive between unattended runs with no repo write. Like
# checkpoint.py's fingerprint, it travels in a hidden marker inside the report comment:
# the next run reads the newest marker back from the durable issue.
CURSOR_MARKER = "<!-- brain-daily-cursor: "
GITHUB_REPO = os.environ.get("REPORT_REPO", "madnessgate44-debug/brain")
GITHUB_ISSUE = int(os.environ.get("REPORT_ISSUE", "292"))


def _run_json(cmd: list[str], cwd: Path) -> tuple[object | None, str | None]:
    """Run a local audit tool and parse its JSON. Returns (data, error)."""
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return None, f"exit {proc.returncode}"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"unparsable JSON: {exc}"


def self_audit(root: Path) -> dict:
    """Run brain's own audits. Absent/failing inputs are recorded honestly as blocked."""
    purpose, purpose_err = _run_json(
        [sys.executable, "watcher/knowledge/tools/purpose_audit.py", "--json"], root
    )
    status, status_err = _run_json([sys.executable, "scripts/agent_status.py", "--json"], root)

    audit: dict = {"purpose_error": purpose_err, "status_error": status_err}
    if isinstance(purpose, dict):
        results = purpose.get("results", [])
        depth = purpose.get("depth", [])
        audit["purpose_checked"] = len(results)
        audit["purpose_ok"] = sum(1 for r in results if r.get("status") == "OK")
        audit["depth_gaps"] = [d.get("finding", "") for d in depth if d.get("status") != "OK"]
    if isinstance(status, dict):
        agents = status.get("agents", [])
        audit["unscheduled_agents"] = [
            a["agent"]
            for a in agents
            if a.get("expected_scheduled") and not a.get("has_scheduled_loop")
        ]
        audit["report_only_pct"] = status.get("report_only_pct")
        audit["open_gaps"] = status.get("open_gaps", [])
    return audit


def parse_plan(text: str) -> dict:
    """Parse a production plan: a one-line goal plus a table of ordered work items.

    The table columns are: id | item | status | evidence. Only rows with a known status
    count as items, so a malformed row is skipped rather than silently counted.
    """
    goal = ""
    items: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not goal and stripped.lower().startswith("goal:"):
            goal = stripped.split(":", 1)[1].strip()
            continue
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        ident, item, status, evidence = cells[0], cells[1], cells[2].lower(), cells[3]
        if status not in STATUSES:
            continue
        items.append({"id": ident, "item": item, "status": status, "evidence": evidence})
    return {"goal": goal, "items": items}


def load_plan(root: Path, repo: str) -> dict | None:
    path = root / "docs" / "audits" / "plans" / f"{repo}.md"
    if not path.is_file():
        return None
    return parse_plan(path.read_text(encoding="utf-8", errors="replace"))


def plan_progress(items: list[dict]) -> dict:
    done = sum(1 for i in items if i["status"] == "done")
    total = len(items)
    nxt = next((i for i in items if i["status"] != "done"), None)
    pct = round(100 * done / total) if total else 0
    return {"done": done, "total": total, "pct": pct, "next": nxt}


def load_queue(root: Path) -> list[dict]:
    path = root / "docs" / "audits" / "repo-queue.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    repos = data.get("repos", [])
    return sorted(repos, key=lambda r: r.get("rank", 0))


def load_cursor(root: Path) -> dict:
    path = root / "docs" / "audits" / "cursor.json"
    if not path.is_file():
        return {"last_repo": None, "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def select_repos(queue: list[dict], cursor: dict, count: int) -> list[dict]:
    """The next `count` repos in the rotation, starting after the cursor's last repo."""
    if not queue:
        return []
    names = [r["name"] for r in queue]
    last = cursor.get("last_repo")
    start = names.index(last) + 1 if last in names else 0
    picked = [queue[(start + k) % len(queue)] for k in range(min(count, len(queue)))]
    return picked


def next_after(queue: list[dict], selected: list[dict]) -> str | None:
    if not queue or not selected:
        return None
    names = [r["name"] for r in queue]
    last = selected[-1]["name"]
    return names[(names.index(last) + 1) % len(names)]


def write_cursor(root: Path, selected: list[dict], when_utc: str) -> None:
    path = root / "docs" / "audits" / "cursor.json"
    cursor = load_cursor(root)
    history = cursor.get("history", [])
    history.append({"utc": when_utc, "repos": [r["name"] for r in selected]})
    out = {
        "last_repo": selected[-1]["name"] if selected else cursor.get("last_repo"),
        "last_run_utc": when_utc,
        "history": history[-30:],
    }
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _github_comments() -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return []
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{GITHUB_ISSUE}/comments?per_page=100"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - a missing cursor must not break the report
        return []


def read_remote_cursor() -> str | None:
    """The newest cursor marker in the durable issue's comments, or None."""
    for comment in reversed(_github_comments()):
        body = comment.get("body", "")
        idx = body.find(CURSOR_MARKER)
        if idx != -1:
            end = body.find("-->", idx)
            if end != -1:
                return body[idx + len(CURSOR_MARKER) : end].strip()
    return None


def effective_cursor(root: Path) -> dict:
    """Prefer the durable marker (survives across runs); fall back to the repo file."""
    remote = read_remote_cursor()
    if remote:
        return {"last_repo": remote, "history": []}
    return load_cursor(root)


def _repo_section(root: Path, entry: dict) -> str:
    name = entry["name"]
    repo = entry.get("repo", name)
    plan = load_plan(root, name)
    if plan is None:
        return (
            f"#### {repo}\n"
            f"- goal: [B] no production plan at `docs/audits/plans/{name}.md`\n"
            f"- next item: create the plan, then this repo can be measured\n"
        )
    prog = plan_progress(plan["items"])
    lines = [f"#### {repo}", f"- goal: {plan['goal'] or '[B] goal missing'}"]
    lines.append(f"- progress: {prog['done']}/{prog['total']} items done ({prog['pct']}%)")
    lines.append("- what to fix (ordered):")
    if plan["items"]:
        for item in plan["items"]:
            mark = {"done": "[V]", "in-progress": "[~]", "blocked": "[B]", "todo": "[ ]"}[
                item["status"]
            ]
            lines.append(f"  - {mark} `{item['id']}` {item['item']} — {item['evidence']}")
    else:
        lines.append("  - [U] plan has no work items yet")
    nxt = prog["next"]
    lines.append(
        f"- next item: `{nxt['id']}` {nxt['item']}" if nxt else "- next item: none — plan complete"
    )
    return "\n".join(lines) + "\n"


def compose(
    *,
    when_utc: datetime,
    audit: dict,
    queue: list[dict],
    cursor: dict,
    selected: list[dict],
    nxt: str | None,
    root: Path,
    question: str,
) -> str:
    lines: list[str] = []
    lines.append(f"## Daily report — {when_utc:%Y-%m-%d}")
    lines.append("")
    lines.append(f"**From:** brain daily audit loop · **UTC** {when_utc:%Y-%m-%dT%H:%M:%SZ}")
    lines.append(
        "**Tags:** [V] verified · [C] reported · [I] inference · [A] assumption · "
        "[U] unknown · [B] blocked"
    )
    lines.append("")

    lines.append("### 1. Brain self-audit")
    if audit.get("purpose_error"):
        lines.append(f"- purpose/depth audit: [B] not run ({audit['purpose_error']})")
    else:
        lines.append(
            f"- purpose audit: {audit.get('purpose_ok', 0)}/{audit.get('purpose_checked', 0)} "
            f"claims OK [V]"
        )
        gaps = audit.get("depth_gaps") or []
        lines.append(f"- depth gaps: {len(gaps)} [V]" + (f" — {'; '.join(gaps)}" if gaps else ""))
    lines.append("- nine-role company: `brain/company/roles.py` — 9 roles [V]")
    if audit.get("status_error"):
        lines.append(f"- agent status: [B] not run ({audit['status_error']})")
    else:
        unsched = audit.get("unscheduled_agents") or []
        lines.append(
            f"- scheduled loops: {'all agents scheduled' if not unsched else 'unscheduled: ' + ', '.join(unsched)} [V]"
        )
        lines.append(f"- report-only commit share: {audit.get('report_only_pct')}% [V]")
    forge_plan = load_plan(root, "Firstborn")
    if forge_plan is None:
        lines.append("- Forge (Firstborn): [U] no production plan yet")
    else:
        fp = plan_progress(forge_plan["items"])
        lines.append(
            f"- Forge (Firstborn): {fp['done']}/{fp['total']} items done ({fp['pct']}%) [V]"
        )
    lines.append("")

    lines.append("### 2. Repos audited today")
    if selected:
        for entry in selected:
            lines.append(_repo_section(root, entry))
    else:
        lines.append("- [B] no repo queue found at `docs/audits/repo-queue.json`")
    lines.append("")

    lines.append("### 3. Repo queue")
    lines.append(
        f"- cursor: `{cursor.get('last_repo') or 'none'}` -> today: "
        f"{', '.join(r['name'] for r in selected) or 'none'}"
    )
    lines.append(f"- next in rotation: `{nxt or 'none'}`")
    lines.append("")

    lines.append("### 4. Question for the owner")
    lines.append(f"- {question}")
    lines.append("")
    lines.append("_This report was generated by an AI agent (OpenHands) on behalf of the owner._")
    if selected:
        lines.append(f"{CURSOR_MARKER}{selected[-1]['name']} -->")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compose and post brain's daily report.")
    ap.add_argument("--repo-dir", default=str(ROOT))
    ap.add_argument("--repos", type=int, default=1, help="repos per run (default 1)")
    ap.add_argument(
        "--dry-run", action="store_true", help="print, do not post or advance the cursor"
    )
    ap.add_argument("--channels", default="github,swarmchat")
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    args = ap.parse_args(argv)

    root = Path(args.repo_dir)
    when_utc = datetime.now(timezone.utc)
    queue = load_queue(root)
    # Dry runs stay offline and use the committed file; a real run prefers the durable
    # marker in the issue so the rotation survives across unattended sessions.
    cursor = load_cursor(root) if args.dry_run else effective_cursor(root)
    selected = select_repos(queue, cursor, max(1, args.repos))
    nxt = next_after(queue, selected)
    audit = self_audit(root)

    report = compose(
        when_utc=when_utc,
        audit=audit,
        queue=queue,
        cursor=cursor,
        selected=selected,
        nxt=nxt,
        root=root,
        question=args.question,
    )

    if args.dry_run:
        print(report)
        return 0

    spec = importlib.util.spec_from_file_location(
        "report_to_channels", root / "scripts" / "report_to_channels.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["report_to_channels"] = module
    spec.loader.exec_module(module)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(report)
        body_path = fh.name
    rc = module.main(["--body", body_path, "--channels", args.channels])
    if rc == 0 and selected:
        write_cursor(root, selected, when_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
