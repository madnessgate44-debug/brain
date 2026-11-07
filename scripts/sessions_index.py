#!/usr/bin/env python3
"""Build a compact index over the exported session logs, so reading the archive is cheap.

The day logs are large (a full day can be ~150 KB). An agent that opens them whole burns its
context. This index is the context pointer: a small file naming every day and every conversation,
with the size, so a reader can grep or open just the one file it needs instead of all of them.

    python3 scripts/sessions_index.py [--dir docs/sessions]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Index the session logs")
    ap.add_argument("--dir", default="docs/sessions")
    a = ap.parse_args()
    d = Path(a.dir)
    manifests = sorted(d.glob("*.manifest.json"))
    if not manifests:
        print("no manifests found", file=__import__("sys").stderr)
        return 1

    days = []
    total_convs = total_owner = total_bytes = 0
    for m in manifests:
        data = json.loads(m.read_text(encoding="utf-8"))
        day = data["date"]
        md = d / f"{day}.md"
        size = md.stat().st_size if md.is_file() else 0
        convs = data.get("conversations", [])
        owner = sum(c.get("owner_messages", 0) for c in convs)
        days.append({
            "day": day, "convs": len(convs), "owner": owner,
            "kb": size // 1024, "file": f"{day}.md",
            "interactive": [c for c in convs if not c.get("automation")],
        })
        total_convs += len(convs)
        total_owner += owner
        total_bytes += size

    lines = [
        "# Session archive — index",
        "",
        "Read this file first. The day logs are large; open a day file only when you need it,",
        "and grep it rather than reading it whole. Owner words are marked `OWNER (verbatim)`.",
        "Raw gzip events live in `.openhands/export/raw/` (gitignored, complete).",
        "",
        f"**{len(days)} days · {total_convs} conversations · {total_owner} owner messages · "
        f"{total_bytes // 1024 // 1024} MB readable.**",
        "",
        "## Days",
        "",
        "| day | conversations | owner msgs | size | file |",
        "|---|---|---|---|---|",
    ]
    for x in sorted(days, key=lambda r: r["day"]):
        lines.append(f"| {x['day']} | {x['convs']} | {x['owner']} | {x['kb']} KB | [{x['file']}]({x['file']}) |")

    lines += ["", "## Interactive sessions (owner in the room)", ""]
    for x in sorted(days, key=lambda r: r["day"]):
        for c in x["interactive"]:
            title = (c.get("title") or "(untitled)").replace("|", "/")
            lines.append(f"- {x['day']} · `{c['id'][:12]}` · {title} · events {c.get('events')}")

    lines += [
        "",
        "## Analyses of this archive",
        "",
        "- [External audit: why OpenHands keeps failing, and what to change in Settings]"
        "(../AUDIT_OPENHANDS_SETTINGS_2026-11-03.md) — reads these conversations as an outside",
        "  reviewer; maps each failure class to a real Settings option.",
    ]

    (d / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {d / 'README.md'} ({len(days)} days, {total_convs} conversations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
