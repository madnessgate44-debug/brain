# Shadow registry

Replacement pool for every API key, connector, skill, sign-in, and LLM route (WATCHER.md §14.3).
Values are never written here — labels only. Last updated: 2026-11-01.

Columns: provider | model or connector | auth tier | key label | task categories | status | last tested | rate-limit state | expiry | repos using it

Status: WORKING, RATE-LIMITED, DEAD, UNTESTED.
Categories: long-context coding, fast chat, reasoning, vision, search or browsing, embeddings, connector or API access.

| provider | model or connector | auth tier | key label | task categories | status | last tested | rate-limit state | expiry | repos using it |
|---|---|---|---|---|---|---|---|---|---|
| GitHub | REST API — read | free-key | `GITHUB_TOKEN` | connector or API access | WORKING | 2026-11-01 | not measured | UNKNOWN | brain |
| GitHub | REST API — write (Issues/PRs) | free-key | `GITHUB_TOKEN` | connector or API access | WORKING | 2026-11-01 | not measured | UNKNOWN | brain |
| GitHub | Actions secrets API | free-key | `GITHUB_TOKEN` | connector or API access | DEAD | 2026-11-01 | n/a | UNKNOWN | brain |
| Google | Gemini API — model list | free-key | `OHGeminiAPI` | fast chat, reasoning, long-context coding | WORKING | 2026-11-01 | free tier | UNKNOWN | brain |
| Google | `gemini-2.5-flash` — generateContent | free-key | `OHGeminiAPI` | fast chat, reasoning, audit | WORKING | 2026-11-01 | OK (3 rapid calls) | UNKNOWN | brain |
| Google | `gemini-3-flash-preview` — generateContent | free-key | `OHGeminiAPI` | fast chat, reasoning, audit | WORKING | 2026-11-01 | OK | UNKNOWN | brain |
| Google | `gemini-flash-lite-latest` — generateContent | free-key | `OHGeminiAPI` | fast chat | WORKING | 2026-11-01 | OK | UNKNOWN | brain |
| Google | `gemini-3.1-flash-lite-preview` — generateContent | free-key | `OHGeminiAPI` | fast chat | WORKING | 2026-11-01 | OK | UNKNOWN | brain |
| Google | `gemini-2.5-pro` | free-key | `OHGeminiAPI` | long-context coding | DEAD | 2026-11-01 | n/a | UNKNOWN | brain |
| Google | `gemini-3.1-pro-preview` | free-key | `OHGeminiAPI` | long-context coding | RATE-LIMITED | 2026-11-01 | HTTP 429 on free tier | UNKNOWN | brain |
| Google | `gemini-flash-latest` | free-key | `OHGeminiAPI` | fast chat | RATE-LIMITED | 2026-11-01 | timed out under probe | UNKNOWN | brain |
| Google | `gemma-4-31b-it` | free-key | `OHGeminiAPI` | fast chat | DEAD | 2026-11-01 | HTTP 500 | UNKNOWN | brain |
| OpenHands | Cloud API — in-session dispatch | free-key | `OPENHANDS_API_KEY` | connector or API access | WORKING | 2026-11-01 | not measured | UNKNOWN | brain |
| OpenHands | Cloud API — inbound from outside | free-key | `OPENHANDS_API_KEY` | connector or API access | WORKING | 2026-11-01 | event run `f30b6fcb…` completed; automation now DISABLED (spend unverified) | UNKNOWN | brain |
| OpenHands | Automation run billing model | UNKNOWN | — | connector or API access | UNTESTED | 2026-11-01 | no card, credits 0.00, observed non-zero run cost | n/a | — |
| ChatGPT / Forge | command center channel | free-key | `GITHUB_TOKEN` (comment API) | connector or API access | WORKING | 2026-11-01 | ChatGPT posts via GitHub integration; Watcher replies via REST on #240 | UNKNOWN | brain |
| YouTube | search + transcript | UNKNOWN | — | search or browsing | UNTESTED | 2026-11-01 | n/a | n/a | — |
| Facebook | Reels transcript (ASR) | OK | — | yt-dlp + faster-whisper | VERIFIED | 2026-11-01 | reel 10153231379946729 (20 seg) | no captions; no search | — |
| Excalidraw / tldraw | design tool (phone-usable) | UNKNOWN | — | connector or API access | UNTESTED | 2026-11-01 | n/a | n/a | — |

## Consumers — secret names each repo references (names only, no values)

| repo | secret names referenced by its workflows |
|---|---|
| brain | `BRAIN_AI_API_KEY`, `BRAIN_AI_BASE_URL`, `BRAIN_GITHUB_TOKEN`, `BRAIN_RD_GITHUB_TOKEN` |
| Firstborn | `FORGE_CROSS_REPO_TOKEN`, `FORGE_DELIVER_TOKEN`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `GROQ_API_KEY` |
| Mohsen | `FORGE_DELIVER_TOKEN`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `GROQ_API_KEY` |
| Mission-runner | `ARM_GITHUB_TOKEN`, `GITHUB_TOKEN` |
| Openhands, Amina, Brand-building-skills, Foryra, Revenue-hunter, Blind-sniper-, Money-slave, Gah1, Brand-manager, Meshmesh-, Meshmesh, brain-chat-log, Mr-baleegh, smart-farm | none referenced |

## Notes
- **Gemini key decision (Ahmed, 2026-11-01):** the key exposed in chat stays in use until the build is complete. It is free tier. Rotation is deferred to Shadow after the build, so this is not a blocker now. It is not written to any file.
- The `GitHub Actions secrets API` row is DEAD: `GET /repos/.../actions/secrets` returns 403 "Resource not accessible by integration". Shadow cannot write keys into Actions secrets until that permission exists. This blocks §14.2 storage and §14.4 step 2.
- Design tool stays UNTESTED until free + no-card is confirmed from the provider's own pricing page (§14.6).
- No secret value appears in this file or its history.
