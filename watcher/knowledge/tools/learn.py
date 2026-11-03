#!/usr/bin/env python3
"""Transcript -> a lesson the Watcher can teach (WATCHER.md §4.3/§4.4, §9).

The Watcher is not only an auditor. Auditing says pass/fail. This turns a watched
video into the three things auditing does not produce:

  1. What this teaches — the transferable principle.
  2. Diagnosis — the recurring problem it speaks to, and why that problem keeps
     happening (symptom -> root cause -> evidence).
  3. The fix and how to teach it — the smallest change, and how to explain it to
     another agent or to a person.

Free route: the same Gemini pool Shadow uses. With no key set it writes an honest
scaffold (transcript + the sections left as TODO) — it never invents findings.

    python3 learn.py <transcript.txt | video URL> [--title T] [--source S]
                     [--ask "..."] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GEMINI_FALLBACKS = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"

SECTIONS = ("What this teaches", "Diagnosis", "The fix", "How to teach it",
            "Which job it serves", "Proposed action")

LESSON_PROMPT = """You are the Watcher: an auditor for an AI coding company, a learner, and a teacher.
A video transcript is below. Turn it into a teachable lesson for the team that builds
two agents: "Forge" (a deterministic coding agent) and "brain" (a mission orchestrator).

NORTH STAR: the owner wants a Claude-Code-like experience — a coding agent that can run
arbitrary shell, use skills, hooks, session resume, parallel subagents, and long-horizon
loops. Every lesson must say how it moves the agents toward that experience.

Be concrete and honest. Distinguish what the transcript actually says from your inference.
Do not invent facts, quotes, numbers, or file paths. If the transcript does not speak to a
section, write "not addressed by this source" for that section.

Output EXACTLY these sections, in this order, with these headings:

## What this teaches
The transferable engineering principle, in two or three sentences. Why it matters.

## Diagnosis
The recurring problem this speaks to. Give it as: SYMPTOM (what people keep seeing),
ROOT CAUSE (why it keeps happening), EVIDENCE (what in the transcript supports this).
This is the part beyond a pass/fail audit: name why the problem returns.

## The fix
The smallest change that addresses the root cause. One concrete action.

## How to teach it
Explain the lesson to another agent or to a person in five lines or fewer, as a short
lesson they can repeat.

## Which job it serves
Name whose job this is (auditor / developer / qa / security / release / watcher / self),
and one line on how it closes the gap to a Claude-Code-like experience.

## Proposed action
One line naming which agent this is for (forge / brain / watcher / self) and the next step.

TRANSCRIPT:
---
{transcript}
---"""


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "lesson"


def _gemini(prompt: str, key: str, timeout: int = 120) -> str | None:
    """Walk the model fallbacks; return the text or None."""
    for m in GEMINI_FALLBACKS:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(
            GEMINI_URL.format(m=m, k=key), data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                d = json.load(x)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            log(f"  gemini {m}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            log(f"  gemini {m}: {type(e).__name__}")
    return None


def extract_sections(md: str) -> dict[str, str]:
    """Split a model reply into its '## <heading>' sections."""
    found: dict[str, str] = {}
    current = None
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            found[current] = ""
        elif current is not None:
            found[current] += line + "\n"
    return {k: v.strip() for k, v in found.items()}


def build_lesson(transcript: str, title: str, source: str, ask: str, key: str | None) -> str:
    """Return the lesson markdown. Honest scaffold when there is no model route."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    head = [f"# Lesson — {title}", "",
            f"- **Source:** {source}",
            f"- **Learned:** {ts}",
            f"- **Watched by:** Watcher (WATCHER.md §4.3/§4.4, §9)", ""]
    if ask:
        head += [f"- **Question for this source:** {ask}", ""]

    if not key:
        body = []
        for s in SECTIONS:
            body += [f"## {s}", "_TODO: no model route (OHGeminiAPI not set) — the lesson is not written yet._", ""]
        body += ["## Transcript", "", transcript.strip(), ""]
        return "\n".join(head + body)

    prompt = LESSON_PROMPT.format(transcript=transcript[:28000])
    if ask:
        prompt = f"Focus question from the owner: {ask}\n\n" + prompt
    reply = _gemini(prompt, key)
    if not reply:
        body = []
        for s in SECTIONS:
            body += [f"## {s}", "_TODO: model route failed — lesson not written._", ""]
        body += ["## Transcript", "", transcript.strip(), ""]
        return "\n".join(head + body)

    sections = extract_sections(reply)
    body = []
    for s in SECTIONS:
        body += [f"## {s}", sections.get(s, "_not addressed by this source_"), ""]
    # Keep anything extra the model produced that we did not name.
    for k, v in sections.items():
        if k not in SECTIONS and v:
            body += [f"## {k}", v, ""]
    body += ["## Transcript", "", transcript.strip(), ""]
    return "\n".join(head + body)


def _transcript_from_url(url: str) -> tuple[str, str]:
    """Fetch a video's transcript via the sibling transcribe tool. Returns (title, body)."""
    here = Path(__file__).resolve().parent
    out = Path(os.environ.get("WATCHER_TRANSCRIBE_OUT", "/tmp/watcher-lesson"))
    subprocess.run([sys.executable, str(here / "transcribe.py"), url, "--out", str(out), "--no-ai"],
                   check=False, timeout=900)
    txts = sorted(out.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txts:
        raise SystemExit(f"no transcript produced for {url}")
    return txts[0].stem.replace("-", " "), txts[0].read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcript -> teachable lesson (WATCHER.md §4.3/§9)")
    ap.add_argument("source", help="a transcript .txt/.md file, or a video URL")
    ap.add_argument("--title", default="")
    ap.add_argument("--source-label", dest="source_label", default="",
                    help="recorded source label (e.g. the video URL)")
    ap.add_argument("--ask", default="", help="an owner focus question for this source")
    ap.add_argument("--no-ai", action="store_true", help="write the honest scaffold, never call a model")
    ap.add_argument("--out", default="watcher/knowledge/lessons")
    a = ap.parse_args()

    if re.match(r"^https?://", a.source):
        log(f"fetching transcript for {a.source}")
        auto_title, transcript = _transcript_from_url(a.source)
        title = a.title or auto_title
        src = a.source
    else:
        p = Path(a.source)
        if not p.is_file():
            raise SystemExit(f"no such transcript: {p}")
        transcript = p.read_text(encoding="utf-8", errors="replace")
        title = a.title or p.stem.replace("-", " ")
        src = a.source_label or p.as_posix()

    key = os.environ.get("OHGeminiAPI") or os.environ.get("GEMINI_API_KEY")
    if a.no_ai:
        key = None
    if not key:
        log("no key set - writing an honest scaffold (no findings invented)")

    md = build_lesson(transcript, title, src, a.ask, key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{slugify(title)}.lesson.md"
    dest.write_text(md, encoding="utf-8")
    log(f"done -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
