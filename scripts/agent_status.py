#!/usr/bin/env python3
"""Status of the three agents — Watcher, Shadow, and the session agent.

This is the check behind W1 (report instead of build) and W4 (a loop that is never scheduled
does not run) in watcher/knowledge/WEAKNESSES.md. It reads the record, not memory:

  - which agent a workflow belongs to (by name and by what it runs),
  - whether each agent has at least one scheduled (cron) workflow,
  - the report-only ratio over recent commits (.md-only commits are report-only).

Exit code is 1 if any agent has zero scheduled workflows, so W4 fails loudly instead of being
forgotten. The session agent is expected to be unscheduled until its loop is wired.

    python3 scripts/agent_status.py [--repo .] [--commits 60] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

AGENTS = ("watcher", "shadow", "session")

# W1 gate: the share of recent commits that change only docs (report-only). It must fall, so this
# is a ratchet: CI fails if the ratio rises above this. Lower it as the ratio improves; never
# raise it. Set just above the level at the time the gate was added (2026-11-03: 37%).
MAX_REPORT_ONLY_PCT = 40.0


def _run(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def classify_workflows(repo: Path) -> dict[str, list[str]]:
    """Map each agent to the workflows that belong to it (by filename or by content).

    Precedence matters: a workflow that starts the session loop also touches watcher paths, so
    the session agent's explicit marker is checked first and the workflow is not double-counted.
    """
    wf_dir = repo / ".github" / "workflows"
    owned: dict[str, list[str]] = {a: [] for a in AGENTS}
    for path in sorted(wf_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = path.name.lower()
        if "session-agent" in name or "start_session_loop" in text:
            owned["session"].append(path.name)
        elif "shadow" in name or "shadow/" in text or "shadow.py" in text:
            owned["shadow"].append(path.name)
        elif "watcher" in name or "watcher/" in text:
            owned["watcher"].append(path.name)
    return owned


def scheduled_workflows(repo: Path) -> set[str]:
    """Workflow filenames that contain a cron schedule."""
    wf_dir = repo / ".github" / "workflows"
    scheduled = set()
    for path in sorted(wf_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "cron:" in text or "schedule:" in text:
            scheduled.add(path.name)
    return scheduled


def report_only_ratio(repo: Path, commits: int) -> tuple[int, int]:
    """Return (report_only, total) over the last N commits that change at least one file."""
    hashes = _run(["git", "log", "--format=%H", f"-{commits}"], repo).split()
    total = report_only = 0
    for h in hashes:
        files = [f for f in _run(["git", "show", "--stat", "--format=", "--name-only", h], repo).split("\n") if f]
        if not files:
            continue
        total += 1
        if all(f.endswith(".md") for f in files):
            report_only += 1
    return report_only, total


def build(repo: Path, commits: int) -> dict:
    owned = classify_workflows(repo)
    scheduled = scheduled_workflows(repo)
    report_only, total = report_only_ratio(repo, commits)
    agents = []
    for a in AGENTS:
        sched = [w for w in owned[a] if w in scheduled]
        # Every agent is expected to have a scheduled loop now that the session loop exists;
        # a missing one is a regression, not a known gap.
        expected = True
        agents.append({
            "agent": a, "workflows": owned[a], "scheduled": sched,
            "has_scheduled_loop": bool(sched),
            "expected_scheduled": expected,
        })
    pct = (100.0 * report_only / total) if total else 0.0
    over = pct > MAX_REPORT_ONLY_PCT
    return {
        "agents": agents,
        "report_only": report_only,
        "commits_with_files": total,
        "report_only_pct": pct,
        "max_report_only_pct": MAX_REPORT_ONLY_PCT,
        "report_only_over_limit": over,
        "missing_expected": [a["agent"] for a in agents if a["expected_scheduled"] and not a["has_scheduled_loop"]],
        "open_gaps": [a["agent"] for a in agents if not a["has_scheduled_loop"]],
    }


def render(report: dict) -> str:
    lines = ["# Agent status", ""]
    for a in report["agents"]:
        mark = "[x]" if a["has_scheduled_loop"] else "[ ]"
        loop = "scheduled loop" if a["has_scheduled_loop"] else "NO scheduled loop"
        lines.append(f"{mark} **{a['agent']}** — {loop} ({len(a['workflows'])} workflow(s))")
    total = report["commits_with_files"]
    pct = report.get("report_only_pct", (100 * report["report_only"] / total) if total else 0.0)
    limit = report.get("max_report_only_pct", MAX_REPORT_ONLY_PCT)
    lines += ["", f"Report-only commits: {report['report_only']}/{total} ({pct:.0f}%) — W1 (limit {limit:.0f}%)"]
    if report.get("report_only_over_limit"):
        lines.append(
            f"FAIL — report-only {pct:.0f}% is above the {limit:.0f}% ratchet. "
            "Ship code, tests, or workflows, not only docs."
        )
    if report["missing_expected"]:
        lines.append(f"REGRESSION — agents expected to be scheduled but are not: {', '.join(report['missing_expected'])}")
    if report["open_gaps"]:
        lines.append(f"Open W4 gap — agents with no scheduled loop: {', '.join(report['open_gaps'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Status of the three agents (W1/W4 checks)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--commits", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = build(Path(a.repo), a.commits)
    if a.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report), end="")
    # Fail on a regression (an agent that should be scheduled but is not), and on the W1 ratchet
    # (the report-only ratio must not rise). The ratchet is what makes W1 bite instead of print.
    failed = bool(report["missing_expected"]) or bool(report.get("report_only_over_limit"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
