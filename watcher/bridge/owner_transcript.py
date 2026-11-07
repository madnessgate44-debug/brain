#!/usr/bin/env python3
"""Owner transcript — Ahmed's train of thought, verbatim, appended live.

Standing rule (Ahmed, 2026-11-01): every reply must carry his train of thought exactly
as it flows, and the same ask goes to ChatGPT in return. This records his words
verbatim — never paraphrased — so the transcript is the source of truth, not a summary.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TRANSCRIPT = os.path.join(HERE, "owner-transcript.md")


def append(text: str, stamp: str | None = None) -> str:
    ts = stamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not os.path.exists(TRANSCRIPT):
        with open(TRANSCRIPT, "w") as f:
            f.write("# Owner transcript — Ahmed, verbatim\n\n"
                    "Standing rule: his words exactly as they flow. No paraphrase, no summary.\n")
    with open(TRANSCRIPT, "a") as f:
        f.write(f"\n### {ts} — Ahmed\n\n{text.strip()}\n")
    return TRANSCRIPT


def tail(n: int = 1) -> str:
    if not os.path.exists(TRANSCRIPT):
        return "(no transcript yet)"
    blocks = open(TRANSCRIPT).read().split("\n### ")
    return "\n### ".join(blocks[-n:]).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Record Ahmed's words verbatim")
    ap.add_argument("--text", help="the words to record")
    ap.add_argument("--stamp", help="override the timestamp")
    ap.add_argument("--tail", type=int, help="print the last N entries instead")
    a = ap.parse_args()
    if a.tail:
        print(tail(a.tail))
    else:
        print("recorded in", append(a.text or "", a.stamp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
