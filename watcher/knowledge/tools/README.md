# Transcription tool (WATCHER.md §4.4)

`transcribe.py` turns a video or reel into a timestamped transcript, and an AI
explanation when a key is present. Free, no card.

    python3 transcribe.py <URL> [--out DIR] [--model tiny|base|small] [--lang auto|en|ar] [--no-ai]

Two paths, chosen automatically:

| Source | Path | Why |
|---|---|---|
| YouTube (has captions) | yt-dlp subtitles | fast, no ASR |
| Facebook Reels / caption-less | yt-dlp audio -> ffmpeg -> faster-whisper | no captions exist |

Deps: `yt-dlp`, `faster-whisper`, `imageio-ffmpeg`, `numpy`.
The explanation step needs `OHGeminiAPI` or `GEMINI_API_KEY`; without it the tool
still writes the transcript.

Verified 2026-11-01: YouTube `lxgfhPQ1GSI` (captions) and Facebook reel
`10153231379946729` (ASR, 20 segments). Runs on main via `.github/workflows/watcher-learning.yml`.

`yt_transcript.py` is the YouTube-captions-only predecessor; prefer `transcribe.py`.
