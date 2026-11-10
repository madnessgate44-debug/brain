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

## 4. Custody, evidence, and the corrected blocker (supersedes the earlier "Owner gate")

Owner correction (`6713837374`): adding the pool is **not** an Owner gate. Provider credential-pool
custody belongs to **Shadow** — the existing credential/replacement-pool owner named in
`WATCHER.md §14` ("Shadow is the owner of the replacement pool for every API key, connector, skill,
sign-in, and LLM route"). The Owner must not be asked to source keys by default.

**Custodian (verified this session):**
- **Shadow owns the pool.** `WATCHER.md §14` and the `shadow-*` workflows already define Shadow as the
  custodian; `.github/workflows/shadow-keys.yml` ("Shadow key sweep", `WATCHER.md §14.4`) is the
  authorized path. Owner note (2026-11-08): the earlier name "Ghost" for this role was an error that
  should not be repeated — **there is no "Ghost" role**; Shadow owns all of it.
- **The key-pool subsystem exists and is the correct tool:** `.github/workflows/shadow-keys.yml`
  ("Shadow key sweep", `WATCHER.md §14.4`) tests every registered key × model with a minimal real
  request and prints **PASS/FAIL only, never a value**. This is the safe health check the correction asks for.

**Live sweep evidence (non-sensitive), run `42421027202`, 2026-11-07T22:31:40Z, `success`:**

```
label|models_http|generate_http|result
GEMINI_POOL_1..7|-|-|NOT SET (secret absent)
OHGeminiAPI|-|-|NOT SET (secret absent)
SUMMARY: 0 WORKING, 8 NOT SET
```

So there is **no existing Gemini pool to inspect** — all eight secrets are absent, not merely
unhealthy. The blocker is a real missing resource; **Shadow** (the custodian) supplies it via the
authorized path.

**Second integration defect (OpenHands-owned, non-secret):** in the same run, the *GitHub API route
probe* reported `github: FAIL (http 403)`. `shadow-keys.yml:73-79` probes `api.github.com/user` with
`${{ secrets.GITHUB_TOKEN }}`; a workflow `GITHUB_TOKEN` (github-actions app) returns 403 on `/user`.
The route is fine; the **probe is misclassified** and should use an endpoint the token is scoped for
(e.g. `GET /repos/{owner}/{repo}`). Fix belongs in `shadow-keys.yml`, not in credentials.

| Action | Owner of the action | Rollback |
|---|---|---|
| Shadow loads a working Gemini pool via the authorized path (`shadow-keys.yml`), never printed | Shadow | delete the secrets |
| Fix the `github: FAIL (403)` probe classification | OpenHands | revert the probe line |
| Enable secret listing (`secrets:read`) so presence is verifiable | Owner (token scope) | remove the scope |

No credential was created, replaced, rotated, revealed, copied, or granted a permission in this phase.
No secret value was printed.

_Phase 1 deliverable 3 of 4. Read-only; no secret value handled._
