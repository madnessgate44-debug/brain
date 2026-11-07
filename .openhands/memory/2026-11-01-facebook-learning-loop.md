# 2026-11-01 — Facebook + the "publish it, don't leave it in the sandbox" correction

## Owner correction
"what is Facebook left you there" then "but why there is something in a sandbox it
should be published on main and working". Two lessons: (1) verify the UNKNOWN
connectors, don't leave them UNKNOWN; (2) work that only runs inside a session is not
delivered — publish it to main and prove it runs there.

## Facebook (reel 10153231379946729 "How to Share With Just Friends")
- yt-dlp metadata: OK. Audio download: OK. **Captions: none. Search: not supported.**
- So the only transcript route is local ASR (faster-whisper). Proven: 20 segments.
- `Firstborn/tools/transcribe/vtx.py` (the constitution's §4.4 tool) also works: 18 seg + Gemini explanation.
- Sandbox gotcha: faster-whisper 1.2.1 needs `av>=14`; PyAV 19 lacks `metadata_errors`,
  so pass a numpy array (ffmpeg -> f32le) instead of a path. `imageio-ffmpeg` supplies ffmpeg.

## Published to main (owner's point)
- PR **#253** (merged `224fdfb`): `watcher/knowledge/tools/transcribe.py` (YouTube captions
  fast path + Facebook/ASR path + optional Gemini), `.github/workflows/watcher-learning.yml`
  (schedule + dispatch), `queue.txt`, loop-run-1 knowledge.
- PR **#255** (merged `6c94b8a`): `--skip-existing`; queue as backlog; Shadow evidence fix.
- PR **#256**: docs — Facebook Reels transcript OK, vtx.py OK.
- **Live proof on main**: dispatched `watcher-learning.yml` -> run **41322381979** success;
  it transcribed the reel and opened **PR #254** by itself (closed as the proof).

## Shadow auditor defects fixed (recurring theme)
`pr_evidence()` was blind to the artifacts it judged. Fixed in #255: read full content of
`watcher/**` and `shadow/**` `.py`/`.txt` (<=8 KB), not just workflows/JSON. Before the fix
Shadow flapped PARTIAL -> REJECTED -> ... on "file missing from evidence".
Verdict sequence for #255: REJECTED (push to main) -> fixed -> PARTIAL (model nit) -> fixed
-> REJECTED (txt unseen) -> fixed -> VERIFIED.

## Traps
- `workflow_dispatch` returns 404 for a workflow not yet on the default branch; merge first.
- Merge under the `docs/LOOP.md` grant: CI green **and** Shadow VERIFIED.
- Run the auditor in background with `< /dev/null` (nohup otherwise hits a Bad file descriptor
  on stdin), then poll the output file; a single run can take ~100 s.
- `pip install` lands in `~/.local`; yt-dlp is `python3 -m yt_dlp` (not on PATH).
