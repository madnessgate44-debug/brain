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
| Google | Gemini API — model list | free-key | `OHGeminiAPI` | fast chat, reasoning, long-context coding | WORKING | 2026-11-01 | not measured | UNKNOWN | brain |
| OpenHands | Cloud API — in-session dispatch | free-key | `OPENHANDS_API_KEY` | connector or API access | WORKING | 2026-11-01 | not measured | UNKNOWN | brain |
| OpenHands | Cloud API — inbound from outside | UNKNOWN | — | connector or API access | UNTESTED | 2026-11-01 | n/a | n/a | — |
| ChatGPT / Forge | command center channel | UNKNOWN | — | connector or API access | UNTESTED | 2026-11-01 | n/a | n/a | — |
| YouTube | search + transcript | UNKNOWN | — | search or browsing | UNTESTED | 2026-11-01 | n/a | n/a | — |
| Facebook | Reels search + transcript | UNKNOWN | — | search or browsing | UNTESTED | 2026-11-01 | n/a | n/a | — |
| Excalidraw / tldraw | design tool (phone-usable) | UNKNOWN | — | connector or API access | UNTESTED | 2026-11-01 | n/a | n/a | — |

## Notes
- The `GitHub Actions secrets API` row is DEAD: `GET /repos/.../actions/secrets` returns 403 "Resource not accessible by integration" with the current token. Shadow cannot write keys into Actions secrets until that permission exists. This blocks §14.2 storage and §14.4 step 2.
- Design tool stays UNTESTED until free + no-card is confirmed from the provider's own pricing page (§14.6).
- The Gemini key pasted into chat is exposed (§14.7); it is treated as needing replacement and is not listed as a long-term WORKING entry.
- No secret value appears in this file or its history.
