#!/usr/bin/env python3
"""Video/reel -> timestamped transcript + optional AI explanation.

Implements WATCHER.md §4.4. Works for any yt-dlp source:
  - YouTube: captions fast path (no ASR needed).
  - Facebook Reels / caption-less sources: local faster-whisper ASR.

  python3 transcribe.py <URL> [--out DIR] [--model tiny|base|small]
                        [--lang auto|en|ar|...] [--no-ai]

Writes <out>/<slug>.md (transcript + explanation when a key is present) and
<out>/<slug>.txt (timestamped transcript only).

Free, no card: yt-dlp, faster-whisper, imageio-ffmpeg, numpy.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GEMINI_FALLBACKS = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"

EXPLAIN_PROMPT = """Explain this video to someone who has not watched it, using the
timestamped transcript. Cover, in order: 1) What it is (one sentence). 2) Summary
(a paragraph). 3) Key points (bullets, reusing the exact [mm:ss] stamps). 4) Walkthrough.
5) Topics/keywords. 6) Takeaways. Be faithful; do not invent facts.

TRANSCRIPT:
---
{transcript}
---"""


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "video"


def stamp(sec: float) -> str:
    t = int(sec)
    return f"{t // 60:02d}:{t % 60:02d}"


def probe(url: str) -> dict:
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download",
           "--print", "%(title)s\t%(id)s\t%(duration)s\t%(extractor)s", url]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"probe failed: {out.stderr.strip()[:300]}")
    title, vid, dur, ex = (out.stdout.strip().split("\t") + ["", "", "", ""])[:4]
    return {"title": title or vid, "id": vid, "duration": dur, "extractor": ex, "url": url}


def youtube_captions(url: str, lang: str, workdir: Path) -> str | None:
    """Return timestamped transcript from captions, or None if none exist."""
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download",
         "--write-auto-sub", "--write-sub", "--sub-langs", lang, "--sub-format", "vtt",
         "-o", str(workdir / "%(id)s.%(ext)s"), url],
        capture_output=True, text=True, timeout=180,
    )
    vtts = list(workdir.glob("*.vtt"))
    if not vtts:
        return None
    lines, last = [], None
    for ln in vtts[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if "-->" in ln:
            lines.append(("TS", _stamp(ln.split("-->")[0].strip())))
            continue
        if not ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        txt = re.sub(r"<[^>]+>", "", ln).strip()
        if not txt or txt == last:
            continue
        last = txt
        ts = lines[-1][1] if lines and lines[-1][0] == "TS" else ""
        lines.append(("TX", ts, txt))
    body = "\n".join(f"[{t}] {x}" for k, t, x in (i for i in lines if i[0] == "TX"))
    return body or None


def _stamp(raw: str) -> str:
    hms = raw.split(".")[0].split(":")
    if len(hms) == 3:
        h, m, s = hms
        return f"{int(h) * 60 + int(m):02d}:{int(s):02d}"
    if len(hms) == 2:
        return f"{int(hms[0]):02d}:{int(hms[1]):02d}"
    return "00:00"


def fetch_audio(url: str, workdir: Path) -> Path:
    out = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist",
         "-f", "worstaudio/worst", "-o", str(workdir / "media.%(ext)s"), url],
        capture_output=True, text=True, timeout=600,
    )
    if out.returncode != 0:
        raise SystemExit(f"audio download failed: {out.stderr.strip()[:300]}")
    media = [p for p in workdir.iterdir() if p.stem == "media"]
    if not media:
        raise SystemExit("no media downloaded")
    return media[0]


def decode_float32(media: Path, ffmpeg: str) -> "object":
    import numpy as np
    res = subprocess.run(
        [ffmpeg, "-nostdin", "-i", str(media), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, timeout=600,
    )
    if res.returncode != 0:
        raise SystemExit(f"ffmpeg decode failed: {res.stderr.decode('utf-8', 'replace')[-300:]}")
    return np.frombuffer(res.stdout, dtype=np.float32)


def transcribe(audio, model_size: str, lang: str) -> tuple[str, str]:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, language=None if lang == "auto" else lang)
    rows = [f"[{stamp(s.start)}] {s.text.strip()}" for s in segments if s.text.strip()]
    return "\n".join(rows), info.language


def explain(transcript: str, key: str) -> str | None:
    for m in GEMINI_FALLBACKS:
        body = json.dumps({"contents": [{"parts": [{"text": EXPLAIN_PROMPT.format(transcript=transcript[:28000])}]}]}).encode()
        req = urllib.request.Request(f"{GEMINI_URL.format(m=m, k=key)}", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as x:
                d = json.load(x)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            log(f"  gemini {m}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            log(f"  gemini {m}: {type(e).__name__}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="watcher/knowledge/video")
    ap.add_argument("--model", default="tiny")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--skip-existing", action="store_true",
                    help="exit 0 without rewriting if the output transcript already exists")
    a = ap.parse_args()

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    log(f"[1/4] probing {a.url}")
    meta = probe(a.url)
    log(f"  {meta['title']}  ({meta['duration']}s, {meta['extractor']})")

    slug = slugify(meta["title"])
    out = Path(a.out)
    if a.skip_existing and (out / f"{slug}.md").exists():
        log(f"already have {out / (slug + '.md')} - nothing to do")
        return 0

    with tempfile.TemporaryDirectory(prefix="transcribe-") as td:
        workdir = Path(td)
        log("[2/4] captions first")
        body = youtube_captions(a.url, "en" if a.lang == "auto" else a.lang, workdir)
        lang = a.lang
        if body:
            log("  captions found (no ASR needed)")
        else:
            log("  no captions - downloading audio for local ASR")
            media = fetch_audio(a.url, workdir)
            log(f"[3/4] transcribing locally ({a.model}, cpu/int8)")
            body, lang = transcribe(decode_float32(media, ffmpeg), a.model, a.lang)
            log(f"  {len(body.splitlines())} segments, language={lang}")

    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.txt").write_text(body + "\n", encoding="utf-8")

    key = os.environ.get("OHGeminiAPI") or os.environ.get("GEMINI_API_KEY")
    note = None
    if key and not a.no_ai:
        log("[4/4] asking Gemini for the explanation")
        note = explain(body, key)
    else:
        log("[4/4] no key set - transcript only")

    md = [f"# {meta['title']}", "",
          f"- **Source:** {meta['url']}", f"- **Platform:** {meta['extractor']}",
          f"- **Duration:** {meta['duration']}s", f"- **Detected language:** {lang}", ""]
    if note:
        md += ["## Explanation", "", note, ""]
    md += ["## Transcript", "", body, ""]
    (out / f"{slug}.md").write_text("\n".join(md), encoding="utf-8")
    log(f"done -> {out / (slug + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
