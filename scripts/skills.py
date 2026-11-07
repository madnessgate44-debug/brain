#!/usr/bin/env python3
"""Skill router: find the relevant skill for the work, before starting it.

The owner's requirement: use the relevant tool or skill whenever it is needed — check the
skills first, every time. This makes that mechanical. It discovers every skill the session
can see, parses each one's name, description, and triggers, and ranks them against the task.

    python3 scripts/skills.py list                      # every skill found, by source
    python3 scripts/skills.py suggest "review this PR"  # the best matches for a task
    python3 scripts/skills.py declaration "review this PR"  # the TOOL DECLARATION line

Exit 0 always on success; exit 1 only when no skills are found at all (nothing to route).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Where skills live. Repo skills are ours; the cache holds the platform's public and plugin skills.
def _roots() -> list[tuple[str, Path]]:
    home = Path(os.environ.get("HOME", str(Path.home())))
    cache = home / ".openhands" / "cache"
    roots: list[tuple[str, Path]] = [
        ("repo-role", REPO / "brain" / "company" / "skills"),
        ("repo-watcher", REPO / "watcher" / "knowledge" / "skills"),
        ("repo-agents", REPO / ".agents" / "skills"),
        ("public", cache / "skills" / "public-skills" / "skills"),
    ]
    for base, label in (
        (cache / "skills" / "public-skills" / "plugins", "plugin"),
        (cache / "plugins", "plugin"),
    ):
        if base.is_dir():
            for pack in sorted(base.glob("*/")):
                for sub in ("skills", ".agents/skills"):
                    p = pack / sub
                    if p.is_dir():
                        roots.append((label, p))
    return roots


def _parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    name = path.parent.name if path.name == "SKILL.md" else path.stem
    description = ""
    triggers: list[str] = []
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if m:
        front = m.group(1)
        n = re.search(r"^name:\s*(.+)$", front, re.M)
        if n:
            name = n.group(1).strip().strip('"')
        d = re.search(r"^description:\s*(.+)$", front, re.M)
        if d:
            description = d.group(1).strip().strip('"')
        tr = re.search(r"^triggers:\n((?:\s*-\s*.+\n?)+)", front, re.M)
        if tr:
            triggers = [t.strip().lstrip("/") for t in re.findall(r"-\s*(.+)", tr.group(1))]
    if not description:
        # Fall back to the first prose line after the first heading.
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith("---"):
                description = s
                break
    return {"name": name, "description": description, "triggers": triggers,
            "path": str(path.relative_to(REPO) if REPO in path.parents else path)}


def all_skills() -> list[dict]:
    seen: dict[str, dict] = {}
    for source, root in _roots():
        if not root.is_dir():
            continue
        for f in sorted(root.glob("*/SKILL.md")) + sorted(root.glob("*.md")):
            if f.name == "README.md":
                continue
            try:
                skill = _parse(f)
            except OSError:
                continue
            skill["source"] = source
            seen.setdefault(skill["name"], skill)
    return list(seen.values())


_WORDS = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "with", "this",
            "that", "it", "is", "be", "we", "you", "i", "my", "our", "use", "when"}
    return {w for w in _WORDS.findall(text.lower()) if w not in stop and len(w) > 2}


def score(skill: dict, task: str) -> int:
    low = task.lower()
    total = 0
    for trig in skill["triggers"]:
        if trig.lower() in low:
            total += 5
    name_words = _tokens(skill["name"].replace("-", " "))
    desc_words = _tokens(skill["description"])
    task_words = _tokens(task)
    total += 3 * len(name_words & task_words)
    total += len(desc_words & task_words)
    return total


def suggest(task: str, k: int = 5) -> list[dict]:
    ranked = []
    for skill in all_skills():
        s = score(skill, task)
        if s > 0:
            ranked.append((s, skill))
    ranked.sort(key=lambda x: -x[0])
    return [dict(skill, score=s) for s, skill in ranked[:k]]


def _line(task: str) -> str:
    hits = suggest(task)
    if not hits:
        return "- Skills considered: none matched this task (no skill trigger fired)"
    parts = [f"{h['name']} (score {h['score']})" for h in hits]
    return "- Skills considered: " + "; ".join(parts) + " -> invoke the relevant ones"


def main() -> int:
    ap = argparse.ArgumentParser(description="Find the relevant skill for the work")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p_s = sub.add_parser("suggest")
    p_s.add_argument("task")
    p_s.add_argument("-k", type=int, default=5)
    p_d = sub.add_parser("declaration")
    p_d.add_argument("task")
    a = ap.parse_args()

    skills = all_skills()
    if not skills:
        print("FAIL - no skills found; nothing to route", file=sys.stderr)
        return 1

    if a.cmd == "list":
        by_source: dict[str, list[str]] = {}
        for s in skills:
            by_source.setdefault(s["source"], []).append(s["name"])
        for source, names in sorted(by_source.items()):
            print(f"{source}: {len(names)}")
            for n in sorted(names):
                print(f"  - {n}")
        print(f"total: {len(skills)}")
        return 0

    if a.cmd == "suggest":
        hits = suggest(a.task, a.k)
        if not hits:
            print("(no skill matched — say why in the declaration)")
            return 0
        for h in hits:
            print(f"[{h['score']:>3}] {h['name']} ({h['source']})")
            print(f"      {h['description'][:140]}")
        return 0

    print(_line(a.task))
    return 0


if __name__ == "__main__":
    sys.exit(main())
