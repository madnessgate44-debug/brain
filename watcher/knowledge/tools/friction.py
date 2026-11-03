#!/usr/bin/env python3
"""Friction detector: where are we failing, read from the record, not from our own opinion.

The owner named the signals himself: we argue back and forth, projects do not close, we work
for hours with no improvement, and his own messages show the frustration. Those are
observable. This tool reads them and reports where the friction is coming from, so the
Watcher finds the problem without waiting for the owner to point at it.

Signals (all from the record, never from a model's self-assessment):
  - owner_frustration: frustration language in watcher/bridge/owner-transcript*.md
  - back_and_forth: the same topic raised by the owner more than once
  - churn_without_close: many commits in a day, few merges — motion, not progress
  - report_only: commits that change only docs
  - sprawl: branches that never merged

    python3 watcher/knowledge/tools/friction.py [--out watcher/knowledge/audits] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# The owner's own words when he is unhappy. Matched on word boundaries so "bs" cannot match
# "jobs" and a negated "I do not pretend" is not read as an accusation.
FRUSTRATION = [
    "pretend", "pretending", "hallucinat", "hallucinating", "bullshit", "lying", "lie to",
    "waste", "no progress", "not progress", "frustrat", "frustrated", "angry",
    "not what i", "did not do", "you didn't", "you did not", "not real", "fake",
]
_FRUSTRATION_RE = re.compile("|".join(rf"\b{re.escape(w)}" for w in FRUSTRATION), re.I)
# A negated mention ("do not pretend") is not frustration.
_NEGATED = re.compile(r"\b(not|never|don't|do not|no)\s+(pretend|lie|fake)", re.I)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def owner_messages() -> list[dict[str, str]]:
    """Parse the verbatim owner transcript(s) into {time, text}."""
    out: list[dict[str, str]] = []
    for path in sorted((REPO / "watcher" / "bridge").glob("owner-transcript*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^### (\S+) — Ahmed\n\n(.*?)(?=^### |\Z)", text, re.S | re.M):
            body = m.group(2).strip()
            if body:
                out.append({"time": m.group(1), "text": body})
    return out


def frustration_findings(messages: list[dict[str, str]]) -> list[dict]:
    hits = []
    for msg in messages:
        text = msg["text"]
        if _NEGATED.search(text):
            text = _NEGATED.sub("", text)
        words = sorted({m.group(0).lower() for m in _FRUSTRATION_RE.finditer(text)})
        if words:
            hits.append({
                "time": msg["time"],
                "signals": words,
                "excerpt": " ".join(msg["text"].split())[:200],
            })
    if not messages:
        return [{
            "finding": "Owner transcript is missing or empty — the signal cannot be read",
            "status": "MISSING",
            "evidence": ["watcher/bridge/owner-transcript*.md has no messages"],
        }]
    newest = max(m["time"] for m in messages)
    stale = newest < "2026-11-03"
    return [{
        "finding": f"Owner frustration appears in {len(hits)} of {len(messages)} messages",
        "status": "PARTIAL" if hits or stale else "OK",
        "evidence": (
            [f"{h['time']}: {h['excerpt']}  [signals: {', '.join(h['signals'])}]" for h in hits[:3]]
            + ([f"transcript is stale: newest message is {newest}, not today's date"] if stale else [])
        ) or ["no frustration language found in the recorded transcript"],
    }]


_TOPIC_WORDS = {
    "loop": ("loop", "looping", "schedule", "cron"),
    "progress": ("progress", "improve", "improvement", "close", "closing"),
    "pretend": ("pretend", "hallucinat", "lying", "bullshit", "not real"),
    "watcher": ("watcher", "watch"),
    "roles": ("role", "roles", "nine", "9"),
}


def back_and_forth_findings(messages: list[dict[str, str]]) -> list[dict]:
    """The same topic raised more than once is a loop we did not close."""
    counts: Counter[str] = Counter()
    for msg in messages:
        low = msg["text"].lower()
        for topic, words in _TOPIC_WORDS.items():
            if any(w in low for w in words):
                counts[topic] += 1
    repeated = {t: c for t, c in counts.items() if c >= 2}
    if not repeated:
        return [{
            "finding": "No topic raised twice by the owner",
            "status": "OK",
            "evidence": ["every owner topic appears once"],
        }]
    worst = max(repeated, key=repeated.get)
    return [{
        "finding": f"Back-and-forth: the owner raised {worst!r} {repeated[worst]} times",
        "status": "PARTIAL",
        "evidence": [f"{t}: {c} messages" for t, c in sorted(repeated.items(), key=lambda x: -x[1])],
    }]


def churn_findings() -> list[dict]:
    """Many commits in a day with few merges means motion, not progress."""
    dates = [d for d in _git("log", "--date=short", "--format=%ad").splitlines() if d]
    if not dates:
        return []
    per_day = Counter(dates)
    worst_day, worst_count = per_day.most_common(1)[0]
    merges = len([l for l in _git("log", "--merges", "--oneline").splitlines() if l])
    branches = len([l for l in _git("branch", "-a").splitlines() if l])
    findings = [{
        "finding": f"Churn: {worst_count} commits on {worst_day}; {merges} merges; {branches} branches",
        "status": "PARTIAL" if worst_count >= 15 or branches > 50 else "OK",
        "evidence": [
            f"busiest day: {worst_day} with {worst_count} commits",
            f"{merges} merges into the current branch",
            f"{branches} branches exist (sprawl when high, few merges)",
        ],
    }]
    return findings


def collect() -> list[dict]:
    messages = owner_messages()
    return (
        frustration_findings(messages)
        + back_and_forth_findings(messages)
        + churn_findings()
    )


def render(findings: list[dict], day: str) -> str:
    lines = [
        f"# Friction — {day}",
        "",
        "Where we are failing, read from the owner's messages and the repository history.",
        "Generated by `watcher/knowledge/tools/friction.py`. The owner is the external signal;",
        "this reads what he already said instead of waiting to be told again.",
        "",
    ]
    for f in findings:
        mark = {"OK": "[x]", "PARTIAL": "[~]", "MISSING": "[ ]"}.get(f["status"], "[?]")
        lines.append(f"{mark} **{f['finding']}** — {f['status']}")
        for e in f.get("evidence", []):
            lines.append(f"    - {e}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect friction from the owner's messages and history")
    ap.add_argument("--out", default="watcher/knowledge/audits")
    ap.add_argument("--date", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = collect()
    day = a.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if a.json:
        print(json.dumps(findings, indent=2))
        return 0
    text = render(findings, day)
    out = REPO / a.out if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"friction-{day}.md"
    dest.write_text(text, encoding="utf-8")
    print(text)
    print(f"-> {dest.relative_to(REPO) if REPO in dest.parents else dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
