# Connector status

Status report for Watcher (WATCHER.md v1.1 §6). Updated daily. Last check: 2026-11-01.
Legend: OK = verified working this session | PARTIAL = reachable but not fully exercised | UNKNOWN = not verifiable from the sandbox | GAP = known missing.
UNKNOWN rows: 4 (counted 2026-11-01; the two channel rows were promoted from UNKNOWN to OK/PARTIAL after the live event-automation run).

| Connector | Status | Last check | Evidence | Gap |
|---|---|---|---|---|
| GitHub API — read | OK | 2026-11-01 | `GET /user` 200; 18 repos listed under `madnessgate44-debug` | — |
| GitHub API — write (Issues/PRs) | PARTIAL | 2026-11-01 | token has `push`/`admin` on `brain`; PR #238 opened | Merge not exercised (owner retains) |
| GitHub Actions | OK | 2026-11-01 | `workflow_dispatch` of `forge.yml` accepted (204); run completed success; logs read via API | — |
| Web browsing (HTTP) | PARTIAL | 2026-11-01 | example.com, youtube.com, facebook.com all 200 | JS-rendered pages unverified |
| YouTube search + transcript | OK | 2026-11-01 | `yt-dlp` `ytsearch` + subtitle fetch worked; transcript of `lxgfhPQ1GSI` (1,475 lines) stored | `youtube-transcript-api` is IP-blocked; use yt-dlp subtitles |
| Facebook Reels transcript (ASR) | OK | 2026-11-01 | reel 10153231379946729 -> 20 segments via local faster-whisper | no captions exist; search not supported |
| Transcription `vtx.py` | OK | 2026-11-01 | ran on reel 10153231379946729 -> 18 segments + Gemini explanation | slower than transcribe.py; superseded |
| Screenshot / render | PARTIAL | 2026-11-01 | `/usr/bin/chromium` present | Playwright not installed |
| Design tool (phone-usable) | UNKNOWN | 2026-11-01 | excalidraw.com 200, tldraw.com 308 (reachable) | Free / no-card requirement NOT confirmed from an official pricing page; not listed as usable |
| Gemini API | OK | 2026-11-01 | `GET /v1beta/models` 200 with key | Free-tier rate limits not measured |
| OpenHands dispatch — in-session | OK | 2026-11-01 | `GET /app-conversations/count` with key 200 | — |
| OpenHands channel — from outside | OK | 2026-11-01 | event automation `017c4b55…` received `issue_comment.created` and completed run `f30b6fcb…` (no human). Now DISABLED (spend unverified). See `watcher/channel/status-2026-11-01.md` | Re-enable needs Ahmed's spend approval |
| Communication channel to ChatGPT/Forge | PARTIAL | 2026-11-01 | ChatGPT posts via the GitHub integration; Watcher replies via REST; both proven on #240. Autonomous receiver DISABLED | No zero-cost autonomous loop confirmed |

## Notes
- `madnessgate44-debug` is a **user** account, not an organization: `GET /orgs/madnessgate44-debug/repos` returns 404; `GET /users/madnessgate44-debug/repos` returns 18 repos.
- Repos visible: Amina, Blind-sniper-, brain, brain-chat-log, Brand-building-skills, Brand-manager, Firstborn, Foryra, Gah1, Meshmesh, Meshmesh-, Mission-runner, Mohsen, Money-slave, Mr-baleegh, Openhands, Revenue-hunter, smart-farm.
- Card rule (v1.1 §6): no connector is listed as usable unless it is free and needs no card. The design tool stays UNKNOWN until its pricing page is confirmed.
- UNKNOWN items require Watcher's first loop run to confirm; none are claimed as working.
