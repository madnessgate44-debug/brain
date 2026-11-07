# SwarmChat launch video — transcript + source content

- **Source (video):** `https://swarmchat.io/assets/launch.mp4`
- **Platform:** swarmchat.io (self-hosted MP4, no captions)
- **Duration:** 49.0s · 1920x1080 h264 · AAC stereo
- **Detected language:** en
- **ASR:** local faster-whisper (small, cpu/int8) via `watcher/knowledge/tools/transcribe.py`

## Transcript

The audio track is **music only** — no spoken narration. The local ASR returns just
the two stock lines below, which are almost certainly a mis-detection of the music
bed (there is no dialogue). Treat this video as **b-roll, not a talk**.

```
[00:00] Let me know in the comments what you think of this video and I'll see you in the next one.
[00:30] Thank you for watching this video.
```

Verified with `ffmpeg -af volumedetect`: mean_volume ≈ -18 dB, max_volume ≈ -1 dB —
continuous music, no speech pauses.

## The real content is the launch article

The video is a silent demo reel. The substance of the announcement is the article on
the same page, `https://swarmchat.io/`. Its key claims are captured verbatim in
`watcher/knowledge/video/2026-11-06-swarmchat-launch.article.txt` and analysed in
`docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md`.

## Why this is worth keeping

The article is a rare, quantified study of **agent-team coordination**: eight coding
agents on ProgramBench reached the same score 3–7× sooner than a solo agent, with a
measured swarm-scaling exponent λ ≈ 0.43–0.86. The companion repo is the tool that
produced it. This is directly relevant to Forge/OpenHands multi-agent work.
