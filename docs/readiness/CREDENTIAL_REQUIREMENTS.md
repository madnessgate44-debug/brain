# CREDENTIAL_REQUIREMENTS — Phase 1 (2026-11-07)

Names, consumers, and status only. **No secret value appears in this file, and none was read.**
Status tags: `[V]` name verified in workflow YAML, `[B]` blocked/absent, `[U]` presence unproven.

## 1. Required by each consumer

| Secret name | Consumer (workflow / agent) | Provider | Where configured | Status | Rotate / expiry owner |
|---|---|---|---|---|---|
| `GITHUB_TOKEN` | every workflow (built-in) | GitHub | Actions | `[V]` present | GitHub |
| `BRAIN_GITHUB_TOKEN` | `brain-build`, `brain-task-runner`, `brain-credential-preflight` | GitHub (PAT) | repo secrets | `[V]` name; `[U]` value | Owner |
| `BRAIN_RD_GITHUB_TOKEN` | `brain-rd-discovery` | GitHub (PAT) | repo secrets | `[V]` name; `[U]` value | Owner |
| `BRAIN_AI_API_KEY` | `brain-build`, `brain-chat-*`, `brain-rd-discovery`, `independent-coding-agent` | OpenAI-compatible | repo secrets | `[V]` name; `[U]` value | Owner |
| `BRAIN_AI_BASE_URL` | same as above | provider URL | repo secrets | `[V]` name; `[U]` value | Owner |
| `OHGeminiAPI` | `shadow-audit`, `shadow-keys`, `shadow-report`, `watcher-learning` | Google Gemini | repo secrets | `[B]` — Shadow reports it absent (`6709749058`) | Shadow (`WATCHER.md §14`) |
| `GEMINI_POOL_1..7` | `shadow-audit`, `shadow-keys`, `shadow-report` | Google Gemini | repo secrets | `[B]` — Shadow reports them absent | Shadow (`WATCHER.md §14`) |
| `OPENHANDS_API_KEY` | `session-agent-loop`, `watcher-session-log` | OpenHands Cloud | repo secrets | `[V]` name; `[U]` value | Owner |

## 2. What could not be verified

`GET /repos/madnessgate44-debug/brain/actions/secrets` → **403** (`Resource not accessible by
integration`) `[V]`. This token cannot enumerate repository secrets. Presence for every row except
Shadow's is therefore `[U]`. Do **not** claim a key works because its name appears in YAML.

## 3. Non-sensitive health checks (the safe way to prove a route)

- Shadow: `shadow-audit.yml` — its last run posts a VERDICT comment (`6709749058` = BLOCKED).
- Brain AI: `ai-provider-secret-check.yml`, `deepseek-api-key-check.yml`, `brain-credential-preflight.yml`.
- A **presence** probe needs no secret value: the workflow either runs or fails closed.

## 4. Remediation (needs Owner approval — do not perform)

| Action | Exact scope | Rollback |
|---|---|---|
| Add Shadow's pool | set `OHGeminiAPI` + `GEMINI_POOL_1..7` as repo Actions secrets | delete the 8 secrets |
| Enable secret listing | give the automation token `secrets:read` (or a human lists them) | remove the scope |

No credential was created, replaced, rotated, revealed, copied, or granted a permission in this phase.

_Phase 1 deliverable 3 of 4. Read-only; no secret value handled._
