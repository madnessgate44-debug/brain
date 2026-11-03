#!/usr/bin/env python3
"""The Watcher's learning report: every open issue, with how he intends to fix it.

The purpose audit finds gaps; this turns them into a plan. It is generated on its own by the
scheduled learning loop (watcher-learning.yml), not by hand, and it answers the owner's
question — "what will you do about each issue?" — for every open item at once.

Sources it reads (the record, never memory):
  - the depth findings from purpose_audit.py (loop coverage, patch contract, temp-dir, proof),
  - the agent status from scripts/agent_status.py (who has a scheduled loop, report-only ratio),
  - the open items in watcher/knowledge/WEAKNESSES.md (the shared weakness ledger),
  - the remedy table below (finding -> the intended fix, owner, first step, and the check).

    python3 watcher/knowledge/tools/learning_report.py [--out watcher/reports] [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO = _HERE.parents[3]
_BRAIN = REPO / "brain"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audit():
    return _load("watcher_purpose_audit", REPO / "watcher" / "knowledge" / "tools" / "purpose_audit.py")


def _status():
    return _load("agent_status", REPO / "scripts" / "agent_status.py")


# How the Watcher intends to fix each known gap. Keyed by a substring of the finding. The
# first step is concrete and the check is the command that proves it closed.
REMEDIES: dict[str, dict[str, str]] = {
    "Patch contract": {
        "impact": "The agent cannot refactor: renames, cleanups, and deletions are impossible, "
                  "so it is a patcher, not a coder.",
        "fix": "Allow deletions and unplanned new files inside the sandbox, guarded by the "
               "existing review + CI gates, and raise the file cap. Deletions stay safe because "
               "the patch is reviewed before merge.",
        "owner": "session agent (brain/company/openhands_developer.py)",
        "first_step": "Drop the deletion/planned-file rejection and add a test that a deletion "
                      "is collected and reviewed.",
        "check": "purpose_audit.py reports OK for 'Patch contract'.",
    },
    "temporary workspace": {
        "impact": "The loop edits a throwaway copy seeded from pasted files; it has no git and "
                  "no full checkout, so it cannot see the real repo.",
        "fix": "Give the loop a real git checkout of the target branch instead of a temp dir, "
               "with the patch still confined to the plan.",
        "owner": "session agent (brain/company/openhands_developer.py)",
        "first_step": "Replace TemporaryDirectory with a shallow clone of the mission branch.",
        "check": "purpose_audit.py reports OK for 'temporary workspace'.",
    },
    "live issue": {
        "impact": "There is no committed proof that the loop works end to end on a real issue.",
        "fix": "Run the loop on a real (small) issue and commit the PR link as evidence.",
        "owner": "session agent",
        "first_step": "Merge the session loop to main, then dispatch one run on a real issue.",
        "check": "watcher/knowledge/evidence/ contains a link to a merged issue -> PR run.",
    },
    "scheduled loop": {
        "impact": "An agent without a schedule does not run; its work waits for a human.",
        "fix": "Give the agent a cron workflow that runs its loop unattended.",
        "owner": "watcher",
        "first_step": "Add the workflow under .github/workflows/ with a schedule trigger.",
        "check": "scripts/agent_status.py reports [x] for every agent.",
    },
}

_FALLBACK = {
    "impact": "An open gap with no plan is a gap that will not close.",
    "fix": "Investigate the root cause in the code, then make the smallest change that closes it.",
    "owner": "watcher",
    "first_step": "Reproduce the gap with a command, then read the code it points at.",
    "check": "purpose_audit.py reports OK for this finding.",
}


def _remedy(issue: str) -> dict[str, str]:
    for key, plan in REMEDIES.items():
        if key in issue:
            return plan
    return _FALLBACK


def open_weaknesses(ledger: Path) -> list[dict[str, str]]:
    """Return the ledger items that are not CLOSED, with their owner and check."""
    if not ledger.is_file():
        return []
    text = ledger.read_text(encoding="utf-8")
    items: list[dict[str, str]] = []
    for block in re.split(r"(?m)^## ", text)[1:]:
        title = block.splitlines()[0].strip()
        if not title.startswith("W"):
            continue
        status = "CLOSED" if "CLOSED" in block else ("in progress" if "Progress" in block else "open")
        owner = (re.search(r"\*\*Belongs to:\*\*\s*([^\n]+)", block) or [None, "both"])[1].strip()
        check = (re.search(r"\*\*Check:\*\*\s*([^\n]+)", block) or [None, "see the ledger"])[1].strip()
        items.append({
            "issue": title,
            "status": status,
            "owner": owner,
            "check": check,
        })
    return [item for item in items if item["status"] != "CLOSED"]


def watched_sources(lessons_dir: Path, video_dir: Path) -> list[dict[str, str]]:
    """Every video the Watcher watched: its URL, transcript, what he learned, what he'll do."""
    if not lessons_dir.is_dir():
        return []
    watched: list[dict[str, str]] = []
    for lesson in sorted(lessons_dir.glob("*.lesson.md")):
        text = lesson.read_text(encoding="utf-8", errors="replace")

        def section(name: str) -> str:
            m = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
            return " ".join(m.group(1).split())[:400] if m else ""

        url = (re.search(r"\*\*Source:\*\*\s*(\S+)", text) or [None, "(url not recorded)"])[1]
        transcript = video_dir / (lesson.name.replace(".lesson.md", ".txt"))
        watched.append({
            "url": url,
            "lesson": lesson.name,
            "transcript": transcript.name if transcript.is_file() else "",
            "learned": section("What this teaches") or "(no summary written)",
            "action": section("Proposed action") or section("The fix") or "(no action written)",
        })
    return watched


def collect(root: Path = _BRAIN) -> dict:
    """Gather every open item from the record, with an action plan for each."""
    audit = _audit()
    status = _status()
    items: list[dict] = []

    for finding in audit.depth_findings(root):
        if finding["status"] == "OK":
            continue
        plan = _remedy(finding["finding"])
        items.append({
            "issue": finding["finding"],
            "status": finding["status"],
            "evidence": "; ".join(finding.get("evidence", [])[:2]),
            **plan,
        })

    report = status.build(root.parent, 60)
    for agent in report["agents"]:
        if agent["has_scheduled_loop"]:
            continue
        plan = _remedy("scheduled loop")
        items.append({
            "issue": f"{agent['agent']} has no scheduled loop",
            "status": "MISSING",
            "evidence": f"{len(agent['workflows'])} workflow(s), none scheduled",
            **plan,
        })

    total = report["commits_with_files"]
    if total and report["report_only"] / total > 0.25:
        items.append({
            "issue": f"Report-only commits are {report['report_only']}/{total} "
                     f"({100 * report['report_only'] // total}%)",
            "status": "PARTIAL",
            "evidence": "commits that change only .md files",
            "impact": "We look busy and ship nothing.",
            "fix": "Every report must carry a code, test, or workflow change, or say why not.",
            "owner": "all three agents",
            "first_step": "Before writing a report, check whether a change is the real answer.",
            "check": "the report-only ratio falls below 25%.",
        })

    for weakness in open_weaknesses(REPO / "watcher" / "knowledge" / "WEAKNESSES.md"):
        if weakness["status"] == "CLOSED":
            continue
        items.append({
            "issue": weakness["issue"],
            "status": weakness["status"],
            "evidence": "watcher/knowledge/WEAKNESSES.md",
            "impact": "A weakness we keep repeating.",
            "fix": "Close it by its own check in the ledger.",
            "owner": weakness["owner"],
            "first_step": "Do the first step recorded in the ledger item.",
            "check": weakness["check"],
        })

    return {
        "items": items,
        "agents": report["agents"],
        "watched": watched_sources(
            REPO / "watcher" / "knowledge" / "lessons",
            REPO / "watcher" / "knowledge" / "video",
        ),
    }


def render(data: dict, day: str) -> str:
    items = data["items"]
    watched = data.get("watched", [])
    lines = [
        f"# Watcher learning report — {day}",
        "",
        "Generated automatically by `watcher/knowledge/tools/learning_report.py` in the scheduled",
        "learning loop. It shows what the Watcher watched, what he learned, and how he intends to",
        "fix each open issue. Nothing here is written by hand.",
        "",
        "## Videos the Watcher watched",
        "",
    ]
    if not watched:
        lines += [
            "**None yet.** No lesson has been produced, so there is nothing to show. This is a",
            "gap, not a pass: the learning loop has not run.",
            "",
        ]
    for w in watched:
        lines += [
            f"### {w['url']}",
            f"- **Transcript:** `watcher/knowledge/video/{w['transcript']}`"
            if w["transcript"] else "- **Transcript:** (missing)",
            f"- **Lesson:** `watcher/knowledge/lessons/{w['lesson']}`",
            f"- **What he learned:** {w['learned']}",
            f"- **What he will do about it:** {w['action']}",
            "",
        ]
    lines += [f"## Open issues — {len(items)}", ""]
    if not items:
        lines.append("No open issues. Every depth check passed.")
        return "\n".join(lines) + "\n"
    for i, item in enumerate(items, 1):
        lines += [
            f"## {i}. {item['issue']}  [{item['status']}]",
            f"- **Evidence:** {item['evidence']}",
            f"- **Impact:** {item['impact']}",
            f"- **How I intend to fix it:** {item['fix']}",
            f"- **Owner:** {item['owner']}",
            f"- **First step:** {item['first_step']}",
            f"- **Done when:** {item['check']}",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Write the Watcher learning report with action plans")
    ap.add_argument("--out", default="watcher/reports")
    ap.add_argument("--date", default="")
    a = ap.parse_args()
    day = a.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = collect()
    text = render(data, day)
    out_dir = REPO / a.out if not Path(a.out).is_absolute() else Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"learning-{day}.md"
    dest.write_text(text, encoding="utf-8")
    print(text)
    print(f"-> {dest.relative_to(REPO) if REPO in dest.parents else dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
