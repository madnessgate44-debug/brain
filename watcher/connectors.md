# Connector status

Status report for Watcher (WATCHER.md v1.1 §6). Updated daily. Last check: 2026-11-01.
Legend: OK = verified working this session | PARTIAL = reachable but not fully exercised | UNKNOWN = not verifiable from the sandbox | GAP = known missing.

| Connector | Status | Last check | Evidence | Gap |
|---|---|---|---|---|
| GitHub API — read | OK | 2026-11-01 | `GET /user` 200; 18 repos listed under `madnessgate44-debug` | — |
| GitHub API — write (Issues/PRs) | PARTIAL | 2026-11-01 | token has `push`/`admin` on `brain`; PR #238 opened | Merge not exercised (owner retains) |
| GitHub Actions | UNKNOWN | 2026-11-01 | not probed | Cannot confirm run/trigger access |
| Web browsing (HTTP) | PARTIAL | 2026-11-01 | example.com, youtube.com, facebook.com all 200 | JS-rendered pages unverified |
| YouTube search + transcript | UNKNOWN | 2026-11-01 | youtube.com reachable (200) | Search/transcript API not exercised |
| Facebook Reels search + transcript | UNKNOWN | 2026-11-01 | facebook.com reachable (200) | Search/transcript not exercised |
| Transcription `vtx.py` | PARTIAL | 2026-11-01 | `Firstborn/tools/transcribe/vtx.py` exists (200) | Not executed; deps unknown |
| Screenshot / render | PARTIAL | 2026-11-01 | `/usr/bin/chromium` present | Playwright not installed |
| Design tool (phone-usable) | UNKNOWN | 2026-11-01 | excalidraw.com 200, tldraw.com 308 (reachable) | Free / no-card requirement NOT confirmed from an official pricing page; not listed as usable |
| Gemini API | OK | 2026-11-01 | `GET /v1beta/models` 200 with key | Free-tier rate limits not measured |
| OpenHands dispatch — in-session | OK | 2026-11-01 | `GET /app-conversations/count` with key 200 | — |
| OpenHands channel — from outside | UNKNOWN | 2026-11-01 | unauthenticated `GET /app-conversations/count` 401 | No verified inbound/receive path from outside |
| Communication channel to ChatGPT/Forge | UNKNOWN | 2026-11-01 | chatgpt.com returned 403 from sandbox | No verified send/receive path |

## Notes
- `madnessgate44-debug` is a **user** account, not an organization: `GET /orgs/madnessgate44-debug/repos` returns 404; `GET /users/madnessgate44-debug/repos` returns 18 repos.
- Repos visible: Amina, Blind-sniper-, brain, brain-chat-log, Brand-building-skills, Brand-manager, Firstborn, Foryra, Gah1, Meshmesh, Meshmesh-, Mission-runner, Mohsen, Money-slave, Mr-baleegh, Openhands, Revenue-hunter, smart-farm.
- Card rule (v1.1 §6): no connector is listed as usable unless it is free and needs no card. The design tool stays UNKNOWN until its pricing page is confirmed.
- UNKNOWN items require Watcher's first loop run to confirm; none are claimed as working.
