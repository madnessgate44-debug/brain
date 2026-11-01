# Connector status

Status report for Watcher (WATCHER.md v1.1 §6). Updated daily. Last check: 2026-11-01.
Legend: OK = verified working this session | PARTIAL = reachable but not fully exercised | UNKNOWN = not verifiable from the sandbox | GAP = known missing.
UNKNOWN rows: 5 (2026-11-01 06:10Z; the OpenHands automation row moved UNKNOWN → PARTIAL and the
GitHub→OpenHands receiver row to PARTIAL after a live event-triggered run was observed; the
chat-channel row stays UNKNOWN. See `/watcher/channel/receiver-spec.md`).

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
| OpenHands automation API (create/list/get/disable/delete/dispatch) | PARTIAL | 2026-11-01 | create 201, list 200, patch 200, delete 204, dispatch 201 (draft deleted) | Not usable as an event receiver here; spend unverified — see `/watcher/channel/receiver-spec.md` |
| OpenHands channel — from outside | UNKNOWN | 2026-11-01 | unauthenticated `GET /app-conversations/count` 401 | No verified inbound/receive path from outside |
| GitHub → OpenHands receiver (automation) | PARTIAL | 2026-11-01 | live `issue_comment.created` event matched and a run COMPLETED (run `f30b6fcb`, cost 0.00123); `git-claims` still `[]` | Works, but spend unverified and an automation is left ACTIVE; see `/shadow/channel-audit-2026-11-01.md` |
| Communication channel to ChatGPT/Forge | UNKNOWN | 2026-11-01 | chatgpt.com returned 403 from sandbox; issue #240 comments read via GitHub API only | No verified send/receive path; the `@openhands` bot reply is a different integration |

## Notes
- `madnessgate44-debug` is a **user** account, not an organization: `GET /orgs/madnessgate44-debug/repos` returns 404; `GET /users/madnessgate44-debug/repos` returns 18 repos.
- Repos visible: Amina, Blind-sniper-, brain, brain-chat-log, Brand-building-skills, Brand-manager, Firstborn, Foryra, Gah1, Meshmesh, Meshmesh-, Mission-runner, Mohsen, Money-slave, Mr-baleegh, Openhands, Revenue-hunter, smart-farm.
- Card rule (v1.1 §6): no connector is listed as usable unless it is free and needs no card. The design tool stays UNKNOWN until its pricing page is confirmed.
- UNKNOWN items require Watcher's first loop run to confirm; none are claimed as working.
- 2026-11-01 channel investigation (`/watcher/channel/receiver-spec.md`): the OpenHands automation
  API works for create/list/get/disable/delete/dispatch. A live `issue_comment.created` event
  reached an enabled automation and completed a run (cost 0.00123), so the receiver is proven.
  `enabled:false` does **not** gate manual dispatch, so a "disabled draft" is not inert. Automation
  run billing is undocumented and non-zero, and a receiver is currently left ACTIVE, so the spend
  question is open with the owner.
