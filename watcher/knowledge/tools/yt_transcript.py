#!/usr/bin/env python3
"""YouTube -> timestamped transcript, via yt-dlp subtitles (no API key, no IP block).

The youtube-transcript-api route is blocked from this sandbox ("YouTube is
blocking requests from your IP"). yt-dlp's subtitle fetch works, so this wraps it.

  python3 yt_transcript.py <video-id-or-url> [--out DIR] [--lang en]

Writes <out>/<id>.vtt and <out>/<id>.txt (timestamped, de-duplicated).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

VID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def vid_of(s: str) -> str:
    m = VID_RE.search(s)
    return m.group(1) if m else s


def fetch(vid: str, out: str, lang: str) -> str:
    os.makedirs(out, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={vid}"
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-auto-sub",
         "--write-sub", "--sub-langs", lang, "--sub-format", "vtt",
         "-o", os.path.join(out, "%(id)s.%(ext)s"), url],
        check=True, capture_output=True, text=True, timeout=180,
    )
    vtt = os.path.join(out, f"{vid}.{lang}.vtt")
    if not os.path.exists(vtt):
        cands = [f for f in os.listdir(out) if f.startswith(vid) and f.endswith(".vtt")]
        if not cands:
            raise SystemExit(f"no subtitle written for {vid}")
        vtt = os.path.join(out, cands[0])
    return vtt


def _stamp(raw: str) -> str:
    """'00:01:02.500' -> '01:02'; '01:02.500' -> '01:02'."""
    hms = raw.split(".")[0].split(":")
    if len(hms) == 3:
        h, m, s = hms
        return f"{int(h) * 60 + int(m):02d}:{int(s):02d}"
    if len(hms) == 2:
        return f"{int(hms[0]):02d}:{int(hms[1]):02d}"
    return "00:00"


def vtt_to_text(vtt: str) -> str:
    """VTT -> '[mm:ss] text' lines, dropping the rolling duplicate lines YouTube emits."""
    lines, last = [], None
    for ln in open(vtt, encoding="utf-8", errors="replace"):
        ln = ln.rstrip("\n")
        if "-->" in ln:
            ts = _stamp(ln.split("-->")[0].strip())
            lines.append(("TS", ts))
            continue
        if not ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        txt = re.sub(r"<[^>]+>", "", ln).strip()
        if not txt or txt == last:
            continue
        last = txt
        ts = lines[-1][1] if lines and lines[-1][0] == "TS" else ""
        lines.append(("TX", ts, txt))
    out = []
    for item in lines:
        if item[0] == "TX":
            out.append(f"[{item[1]}] {item[2]}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="/tmp/yt")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    vid = vid_of(a.video)
    vtt = fetch(vid, a.out, a.lang)
    txt = vtt_to_text(vtt)
    tpath = os.path.join(a.out, f"{vid}.txt")
    open(tpath, "w").write(txt + "\n")
    print(f"{vid}: {len(txt)} chars -> {tpath}")
    print(txt[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
