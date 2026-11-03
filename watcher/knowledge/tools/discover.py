#!/usr/bin/env python3
"""Self-directed discovery: what the Watcher should watch next (WATCHER.md §16).

The Watcher does not wait for the owner to supply videos. He derives what matters from
the owner's line of work and the open problems, searches YouTube, and queues the best
results. This tool fills the watch queue; watcher-learning.yml then watches it.

Sources of focus, in order:
  1. --question "..."            (an owner question: research this)
  2. watcher/knowledge/focus.md  (the owner's line of work + open problems; one per line)

Search is yt-dlp's YouTube search (`ytsearchN:<query>`), which is free and needs no key.

    python3 discover.py [--limit N] [--per-query K] [--question "..."] [--dry-run]

Appends new, unwatched URLs to watcher/knowledge/queue.txt and prints them.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
QUEUE = ROOT / "watcher" / "knowledge" / "queue.txt"
FOCUS = ROOT / "watcher" / "knowledge" / "focus.md"
VIDEO_DIR = ROOT / "watcher" / "knowledge" / "video"


def log(msg: str) -> None:
    print(msg, flush=True)


def read_focus(path: Path, question: str) -> list[str]:
    """Focus topics: the owner's question if given, else the focus file (comments skipped)."""
    if question:
        return [question.strip()]
    if not path.is_file():
        return []
    topics = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            topics.append(line)
    return topics


def watched_urls() -> set[str]:
    """Every URL already queued or already transcribed, so nothing is watched twice."""
    seen: set[str] = set()
    if QUEUE.is_file():
        for line in QUEUE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() and not line.startswith("#"):
                seen.add(line.strip())
    if VIDEO_DIR.is_dir():
        for md in VIDEO_DIR.glob("*.md"):
            m = re.search(r"\*\*Source:\*\*\s*(\S+)", md.read_text(encoding="utf-8", errors="replace"))
            if m:
                seen.add(m.group(1))
    return seen


def search(query: str, per_query: int) -> list[str]:
    """Return candidate video URLs for a query via yt-dlp search. Never raises."""
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--flat-playlist",
           "--print", "%(webpage_url)s",
           f"ytsearch{per_query}:{query}"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        log(f"  search failed for {query!r}: {out.stderr.strip()[:160]}")
        return []
    return [u.strip() for u in out.stdout.splitlines() if u.strip().startswith("http")]


def discover(topics: list[str], limit: int, per_query: int) -> list[str]:
    """Return up to `limit` new URLs, in topic order, skipping anything already watched."""
    seen = watched_urls()
    picked: list[str] = []
    for topic in topics:
        if len(picked) >= limit:
            break
        log(f"search: {topic}")
        for url in search(topic, per_query):
            if url in seen or url in picked:
                continue
            picked.append(url)
            if len(picked) >= limit:
                break
    return picked


def append_to_queue(urls: list[str], queue: Path) -> None:
    if not urls:
        return
    header = queue.read_text(encoding="utf-8", errors="replace") if queue.is_file() else ""
    if header and not header.endswith("\n"):
        header += "\n"
    with queue.open("w", encoding="utf-8") as fh:
        fh.write(header)
        for u in urls:
            fh.write(u + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover what the Watcher should watch (WATCHER.md §16)")
    ap.add_argument("--limit", type=int, default=3, help="max new videos to queue this run")
    ap.add_argument("--per-query", type=int, default=5, help="search results per focus topic")
    ap.add_argument("--question", default="", help="an owner question to research")
    ap.add_argument("--focus", default=str(FOCUS))
    ap.add_argument("--dry-run", action="store_true", help="print the picks, do not write the queue")
    a = ap.parse_args()

    topics = read_focus(Path(a.focus), a.question)
    if not topics:
        log("no focus topics (empty focus.md and no --question) - nothing to discover")
        return 0

    picked = discover(topics, a.limit, a.per_query)
    if not picked:
        log("nothing new found")
        return 0
    log(f"discovered {len(picked)} new source(s):")
    for u in picked:
        log(f"  {u}")
    if not a.dry_run:
        append_to_queue(picked, QUEUE)
        log(f"queued in {QUEUE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
