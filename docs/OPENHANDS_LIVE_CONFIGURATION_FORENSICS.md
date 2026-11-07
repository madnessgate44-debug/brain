# OpenHands live configuration forensics

Investigator: OpenHands session agent, read-only.
Date: 2026-11-04.
Scope: the owner's actual OpenHands Cloud account, not SDK defaults.

Tags used throughout:
- **[V] VERIFIED** — read directly from a live API response, a log, or the archive, with the source named.
- **[O] OBSERVED** — a test I actually ran, with its result.
- **[I] INFERRED** — a conclusion drawn from evidence; the evidence is cited.
- **[U] UNVERIFIED** — could not be read. Stated as such, never guessed.

No secret value appears in this document. Secret *names* and presence only.

---

## 1. Executive verdict

The owner's failures are **not** one bug and **not** an SDK-defaults problem. Three live
configuration facts explain most of them:

1. **There is no provider fallback.** One profile, one model, `provider_connection_id: null`.
   When the hosted proxy returned an HTML error page on 2026-10-30, nothing substituted a
   working provider and the run ended. The agent's own record says retries did not fire.
2. **The second profile is dead and its name is a lie.** `gemini_gemini-2.0-flash` is configured
   with `model: gemini/gemini-2.5-flash`; its provider connection does not resolve in the runtime;
   and all eight Gemini keys in this environment now return `429 RESOURCE_EXHAUSTED`. Two
   automation runs failed today with a 401 caused by an `AQ.`-prefixed Gemini key being sent to an
   endpoint that expects `sk-`.
3. **The critic is enabled but not independent.** `critic_model_name: null`, so the verification
   pass scores the agent using the same model that produced the work. It cannot separate a test
   result from an assertion, which is exactly the owner's "claims done without verification"
   complaint.

The previous audit (`docs/AUDIT_OPENHANDS_SETTINGS_2026-11-03.md`) is honest that it could not see
live values: *"the owner's live values on `app.all-hands.dev/settings`"* are marked `[U]`. This
report closes that gap. It replaces the audit's assumed defaults with measured values.

---

## 2. Actual live configuration inventory

Method and timestamp for every row below:

| item | method | retrieved |
|---|---|---|
| account settings | `GET https://app.all-hands.dev/api/v1/settings` with `Authorization: Bearer $OPENHANDS_API_KEY` | 2026-11-04, this session |
| runtime view | local agent-server `GET http://127.0.0.1:60000/api/settings`, header `X-Session-API-Key` | 2026-11-04 |
| profiles (runtime) | `GET /api/profiles` | 2026-11-04 |
| provider connections | `GET /api/organizations/{org}/provider-connections` | 2026-11-04 |
| automations | `GET /api/automation/v1` and `.../{id}/runs` | 2026-11-04 |
| conversation state | `GET /api/v1/app-conversations/search` | 2026-11-04 |

**Account [V]:** email `madnessgate44@gmail.com`; org id
`84dc7c65-8ba1-4896-90ce-f16084a9afb7`. `v1_enabled: true`. Conversations on the account:
**164** (`GET /api/v1/app-conversations/count`).

**Agent [V]** (`agent_settings`):
- `agent: CodeActAgent`, `agent_kind: openhands`, `schema_version: 9`
- `tool_concurrency_limit: 1`
- `enable_classify_and_switch_llm_tool: false`
- `tools: null` (default tool set)
- `agent_context.load_project_skills: false`, `skills: []`, `load_user_skills: false`,
  `load_public_skills: false`, `load_memory: false`
- `agent_context.current_datetime: "2026-10-23T02:16:09.850450Z"` — **stale by 12 days [V]**

**LLM (active) [V]:**
- `model: openhands/deepseek-v4.1-flash`
- `api_key: null`, `provider_connection_id: null`, `auth_type: api_key`
- `num_retries: 5`, `retry_multiplier: 8.0`, `retry_min_wait: 8`, `retry_max_wait: 64`
- `timeout: 300`, `stream_idle_timeout: 300.0`, `max_message_chars: 30000`
- `temperature: null`, `top_p: null`, `max_input_tokens: null`, `max_output_tokens: null`
- `reasoning_effort: "high"`, `extended_thinking_budget: 200000`
- `api_mode: auto`, `drop_params: true`, `stream: false`, `native_tool_calling: true`
- `disable_vision: null`, `caching_prompt: true`, `prompt_cache_retention: "24h"`

**Profiles [V]** — exactly two:

| profile | model | provider_connection_id | runtime status |
|---|---|---|---|
| `Default` | `openhands/deepseek-v4.1-flash` | `null` | `provider_connection_broken: false`, `api_key_set: true` |
| `gemini_gemini-2.0-flash` | `gemini/gemini-2.5-flash` | `8255cabbf0cf4a12b02ac6558fc796ef` | `provider_connection_broken: true`, `api_key_set: false` |

Note the mismatch: the profile **name** says 2.0-flash, the configured **model** is 2.5-flash.

**Provider connections (org) [V]:**
```json
{"connections":[{"id":"8255cabbf0cf4a12b02ac6558fc796ef","display_name":"Gemini",
 "provider":"gemini","base_url":null,"created_at":1793757824,"updated_at":1793788789,
 "api_key_set":true}]}
```
The connection exists at org level with a key set, but the runtime reports the profile referencing
it as broken (below). These two facts are both true and are the contradiction to resolve.

**Condenser [V]:** `condenser_kind: llm_summarizing`, `enabled: true`, `max_size: 240`,
`keep_first: 2`, `minimum_progress: 0.1`, `hard_context_reset_max_retries: 5`,
`hard_context_reset_context_scaling: 0.8`. `max_tokens: null`.

**Verification [V]:** `critic_enabled: true`, `critic_mode: "finish_and_message"`,
`enable_iterative_refinement: true`, `critic_threshold: 0.6`,
`max_refinement_iterations: 3`, `critic_server_url: null`, **`critic_model_name: null`**,
`critic_api_key: "**********"` (present).

**Conversation settings [V]:** `max_iterations: 500`, `confirmation_mode: false`,
`security_analyzer: "llm"`, `default_runtime: "local"`,
`worktree_base: "default_branch"`, `worktree_branch_prefix: "openhands/"`,
`container_browser: true`, `container_memory: null`, `container_cpus: null`.

**Account-level flags [V]:** `git_full_clone: false`, `max_budget_per_task: null`,
`sandbox_grouping_strategy: "NO_GROUPING"`, `llm_api_key_set: true`,
`provider_tokens_set: {"github": null}`, `enable_memory_context: true`,
`registered_marketplaces: [{name: "openhands-account", source:
"github:madnessgate44-debug/Openhands", repo_path: ".agents", auto_load: true, scope: "personal"}]`,
`inherited_marketplaces: []`, `active_agent_profile_id: null`.

**Automations [V]** — two, both `model: "Default"`:

| id | name | enabled | state | cron (UTC) | timeout |
|---|---|---|---|---|---|
| `aa4ae120-…09c5` | Openhands loop | true | ACTIVE | `0 */2 * * *` | 1800 s |
| `216fd7ae-…166b` | Miss Noor — autonomous owner window (9h) | false | INACTIVE | `0 */2 * * *` | 1800 s |

**Runtime view [V]** — the agent-server's own settings endpoint reports
`llm_api_key_is_set: false` and `active_profile: null`, while the cloud reports
`llm_api_key_set: true`. The runtime's local secret store is empty
(`GET /api/settings/secrets` → `{"secret names": []}`).

**Secret store [V]:** the runtime secret list is **empty**. Archive evidence confirms the same on
2026-10-28: *"two stored secrets, `CLAUDE_INBOX_ID` and `CLAUDE_INBOX_TOKEN`, are not in your
OpenHands secret store."* Names only; no values were read.

### Scope of each setting

| scope | settings |
|---|---|
| account-wide | `git_full_clone`, `max_budget_per_task`, `enable_memory_context`, marketplaces, secrets store |
| profile-specific | `model`, `provider_connection_id`, `reasoning_effort`, retries, timeouts, `temperature` |
| conversation-specific | `max_iterations`, `confirmation_mode`, `security_analyzer`, `default_runtime`, worktree fields |
| automation-specific | cron schedule, `enabled`, `timeout`, `model` (points at a profile name) |
| agent-class | `agent: CodeActAgent`, `tool_concurrency_limit`, condenser, verification |

---

## 3. Historical failure register

Archive: `docs/sessions/` on `goal/claude-code-parity`, 19 days, 142 conversations,
577 owner messages [V]. Account total is 164 conversations, so **22 conversations are not in the
archive** [V] — the register below covers the archived set only.

Frequency counts across the archive [V] (`git grep -c`):

| signal | count | reading |
|---|---:|---|
| `404` | 70 | endpoint/model not found, and unrelated app 404s (mixed) |
| `429` | 49 | rate limit / quota |
| `401` | 29 | auth failure |
| `503` | 22 | upstream unavailable |
| `502` | 21 | upstream bad gateway |
| `truncat*` | 46 | output/context cut off |
| `Service Temporarily Unavailable` | 1 | the 10-30 proxy outage |
| `LiteLLM` | 0 | not present in the archive (only in live automation errors) |
| `expected to start with` | 0 | not in archive; only in live errors |

Distinction: the 404/429/401/503 counts mix *genuine provider incidents* with *the app being
built* (the brain/Amina apps return their own 404s and fall back on 429s). They are a smoke
signal, not a per-incident count. The dated entries below are the distinct incidents.

| # | date | conversation | exact failure | provider/model | live setting at the time | retries | recovered | cause class | evidence |
|---|---|---|---|---|---|---|---|---|---|
| F1 | 2026-10-28 | inbox setup session | two required secrets absent; automation not created | n/a | secret store empty | n/a | no (correctly blocked) | configuration | archive quote, §1 |
| F2 | 2026-10-30 | Amina 9 h run | proxy returned HTML `Service Temporarily Unavailable`; `execution_status=error`; nothing restarted it for 14 h | hosted proxy | `num_retries: 5`, no fallback provider | **did not fire** | no | provider availability + no fallback | archive quote, §4 |
| F3 | 2026-10-27→10-30 | Miss Noor automation | 19 runs: **18 FAILED, 1 COMPLETED**; 15 `timeout`, 3 `execution_error` (HTML error body), 1 clean | `Default` | `timeout: 300`, automation `timeout: 1800` | none effective | no | automation + provider | `GET /api/automation/v1/216fd7ae…/runs` |
| F4 | 2026-11-04 00:00 | automation run `9bd78904` | `OpenAIError: 401 — LiteLLM Virtual Key expected. Received=AQ.A****uSdQ, expected to start with 'sk-'` | `Default` path, Gemini key | profile connection broken | n/a | no | configuration | run `status_detail` |
| F5 | 2026-11-04 02:00 | automation run `aae15cae` | same 401, `Received=AQ.A****rNkg` | as above | as above | n/a | no | configuration | run `status_detail` |
| F6 | 2026-11-01 14:00→22:00 | automation runs ×5 | `SKIPPED — Daily sandbox limit of 20 reached` | n/a | 2 automations × 12 runs/day | n/a | no | quota / platform limit | `status_detail.kind = daily_sandbox_limit` |
| F7 | 2026-10-28 | image task | *"the currently selected model (openhands/deepseek-v4.1-flash) does not support image understanding"* | `Default` | `disable_vision: null` | n/a | no | model capability | archive quote, §4 |
| F8 | 2026-11-02 | self-audit | *"we optimise for what is easy to prove … a preference for cheap proof"* | n/a | critic not independent | n/a | no | agent behaviour | archive quote, §4 |

Repeated mentions vs repeated incidents: F4 and F5 are **two distinct incidents** of the same
configuration fault. F6 is **one quota condition** seen five times in one evening. F3 is **18
distinct failures** of one automation.

**Live test results [O] (Phase 4):**

| test | command | result |
|---|---|---|
| Gemini key validity | `GET /v1beta/models?key=$GEMINI_POOL_1` | **HTTP 200, 50 models** — key valid |
| `gemini-2.0-flash` still offered? | same list | **absent** — retired |
| image input on 2.5-flash | `POST :generateContent` with an 8×8 PNG | **HTTP 429 RESOURCE_EXHAUSTED** on `GEMINI_POOL_1` |
| other 7 keys | same POST | **all HTTP 429 RESOURCE_EXHAUSTED** |
| profile `Default` preflight | `POST /api/profiles/Default/validate` | **HTTP 200, `valid:false`** — `LLMAuthenticationError: Litellm_proxyException - The api_key client option must be set` |
| profile `gemini_gemini-2.0-flash` preflight | `POST /api/profiles/gemini_gemini-2.0-flash/validate` | **HTTP 422** — `LLM config references provider connection '8255cab…', which does not exist` |

No quota was deliberately exhausted; the 429s are the provider's own reported state.

---

## 4. Evidence linking configuration to failures

**F2 — retries do not cover a proxy HTML error.** Archive, verbatim [V]:
> "on Oct 30 my 9-hour Amina run died after 46 min. The model proxy returned an HTML 'Service
> Temporarily Unavailable' page, OpenHands set execution_status=error, and nothing restarted it.
> Nothing ran for 14 hours. The retries (num_retries=5) did not fire. Everything we built (hooks,
> loop, backlog gate) runs inside the conversation, so it died with it."

This matches the live setting: `num_retries: 5` with no `provider_connection_id` and no fallback
profile. Retries re-attempt the *same* endpoint; they cannot route around it. **[I]** the missing
fallback is the direct cause of the 14-hour gap.

**F4/F5 — the 401 is a key-type mismatch, not a paste error.** Live run detail, verbatim [V]:
> `401 - LiteLLM Virtual Key expected. Received=AQ.A****rNkg, expected to start with 'sk-'.`

`AQ.` is the Gemini key prefix; `sk-` is what the OpenAI-compatible proxy expects. So a Gemini key
is reaching an endpoint that is not the Gemini endpoint. **[I]** the `Default` profile's
`provider_connection_id: null` means the `openhands/*` model should be served by the hosted proxy
with the account key — and the runtime reports `llm_api_key_is_set: false`, so the key it actually
picked up was the Gemini one. The archive names the same symptom independently: *"your raw `curl`
with `x-goog-api-key` hits the known Google `AQ.` 401 bug"* [V].

**F3 — the automation is not viable at its own timeout.** 15 of 19 runs ended in `timeout` with
`detail: "command timed out or was killed"`; the 3 `execution_error` runs returned an HTML body
(not JSON) as the error [V]. The automation's `timeout` is 1800 s and the LLM `timeout` is 300 s
[V]. **[I]** a run that must survive 30 minutes cannot do so on a single 300 s-timeout model with
no fallback.

**F6 — the schedule exceeds the platform limit.** Two automations on `0 */2 * * *` = 24 runs/day
against a stated **daily sandbox limit of 20** [V]. The provider says so itself:
`"Daily sandbox limit of 20 reached. Request a quota increase at /settings/quota"`. **[I]** the
schedule, not the code, causes the skips.

**F7 — the model cannot see images.** Archive, verbatim [V]:
> "I received your image, but the currently selected model (openhands/deepseek-v4.1-flash) does
> not support image understanding. Please switch to a multimodal model to analyze the image."

The active model is `openhands/deepseek-v4.1-flash` and `disable_vision: null` [V]. **[I]** any
image task routed to `Default` will fail by design. Note the archive's other finding: the image
*generation* models also returned `429 RESOURCE_EXHAUSTED, limit: 0` [V].

**F8 — verification is self-referential.** `critic_enabled: true` but
`critic_model_name: null` [V], so the critic has no model of its own. The archive's own
self-audit states the behaviour plainly [V]:
> "we optimise for what is **easy to prove** — a green check, a written report, a confident
> number — and avoid the open-ended work: run the loop, read the code, prove it end to end …
> It's not a knowledge gap; it's a preference for cheap proof."

**[I]** a critic sharing the producer's model inherits the same bias and cannot be the independent
check the owner expects.

**Sandbox lifecycle [V]:** conversation `37847d24…` ("Openhands loop — 2026-11-04 12:04:18 UTC")
ran 12:04:17→12:07:50, ended `execution_status: finished`, `accumulated_cost: 0.0`, and its
sandbox then read `MISSING`. A 3.5-minute run against a 30-minute timeout that ends cleanly is
**normal teardown**, not a crash. Automation sandboxes are ephemeral.

**Unpushed work [V]:** `git_full_clone: false`. **[I]** a shallow clone plus ephemeral sandboxes
means work that is committed but not pushed does not survive; this is the mechanism behind the
owner's repeated "nothing changed" experience.

**Watchdog [V]:** the only schedulers are the two cron automations. There is no component outside
a conversation that detects a stalled run and starts a replacement — consistent with F2's
"nothing restarted it". Automation failures *are* observable: `status_detail.kind` carries
`daily_sandbox_limit`, `timeout`, and `execution_error`.

**GitHub integration [V]:** workflow files on `main` declare `permissions: {}` (least privilege),
e.g. `.github/workflows/ai-provider-secret-check.yml:7`. `provider_tokens_set: {"github": null}` —
the GitHub provider token is **not** stored at account level. PR creation works in practice
(PRs #269–#279 exist) [V].

---

## 5. Settings that should change

Ranked. "Current" is the measured live value, not a default.

| # | setting | current (verified) | recommended | reason | historical evidence | risk | cost |
|---|---|---|---|---|---|---|---|
| 1 | provider fallback | none (`provider_connection_id: null`, 1 model) | add ≥1 independent working profile and a fallback path | retries cannot route around a dead endpoint | F2 (14 h outage) | medium | $0 if free-tier |
| 2 | `gemini_gemini-2.0-flash` profile | broken; model `gemini/gemini-2.5-flash`; all 8 keys 429 | **delete or disable**; do not rely on Gemini quota | dead profile + misleading name; causes 401s | F4, F5 | low | $0 |
| 3 | `critic_model_name` | `null` (critic = same model) | set a different, independent model | self-referential critic cannot verify | F8 | low | $0 if free model |
| 4 | automation cron | `0 */2 * * *` ×2 = 24/day vs limit 20 | reduce to ≤ 20/day total (e.g. one automation at `0 */3 * * *`) | platform skips the excess | F6 | low | $0 |
| 5 | `git_full_clone` | `false` | `true` | shallow clone + ephemeral sandbox loses unpushed work | "nothing changed" reports | low | $0 |
| 6 | `reasoning_effort` / `extended_thinking_budget` | `high` / `200000` | **TEST FIRST** — try `medium` | high effort raises latency and quota burn on a 429-prone setup | F6, all 429s | medium | $0 |
| 7 | `timeout` | `300` | **TEST FIRST** — raise only if runs still die at the wall | long runs need headroom, but this is not the root cause | F3 | low | $0 |
| 8 | `temperature`, `max_input_tokens`, `max_output_tokens` | `null` | **KEEP** | unset means the model's own defaults; no evidence of harm | — | — | $0 |
| 9 | condenser | `llm_summarizing`, 240, `keep_first: 2` | **KEEP** | no context-overflow incident found in the archive (`context.*too long` → 0 hits) | — | — | $0 |
| 10 | `tool_concurrency_limit` | `1` | **KEEP** | serial tool use is correct for a 429-prone provider | — | — | $0 |
| 11 | `max_iterations` | `500` | **KEEP** | not implicated in any recorded failure | — | — | $0 |
| 12 | `security_analyzer` | `llm` | **KEEP** | no incident attributed to it | — | — | $0 |
| 13 | Gemini quota | free tier, exhausted | **NOT ACCESSIBLE** without a card | all 8 keys 429; buying quota needs payment | F4, F5 | — | **paid** |
| 14 | 22 unarchived conversations | not exported | **NOT ACCESSIBLE** from the archive alone | export must be re-run with a working key | §3 | — | $0 |
| 15 | `agent_context.current_datetime` | `2026-10-23…` (stale) | refresh | a stale clock feeds wrong dates to the agent | [V] §2 | low | $0 |

### 5.1 The three most consequential problems

1. **No fallback provider** — explains F2 and contributes to F3. Free fix (add a second profile).
2. **The dead Gemini profile** — explains F4 and F5. Free fix (delete/disable it).
3. **The non-independent critic** — explains F8, the "claims done without proof" class.
   Free fix (name a critic model).

### 5.2 Failures settings cannot solve

- **F3 timeout pattern** is partly automation design (a 30-minute run on a 300 s model), not a knob.
- **F6** is a platform quota limit; only a schedule change or a quota increase helps.
- **F1** needs a secret to exist; no setting creates it.
- **F8's** deeper cause is agent behaviour. A critic model reduces it; it does not remove it.
- The **stale clock** and **shallow clone** are correctness bugs in how sessions start, not tuning.

### 5.3 Free vs paid

- **Free:** items 1–5, 7–12, 15.
- **Needs a paid plan or a card:** item 13 (Gemini quota). The owner has stated no card, so the
  correct action is to stop depending on Gemini rather than to buy it.
- **Needs an API key only:** item 3 (a critic model with its own key).

### 5.4 Safe to change without disrupting current work

Items 2, 4, 5, 15 — they do not touch the active `Default` profile. Item 1 and item 3 should be
added *alongside* the current profile, not in place of it.

---

## 6. Settings that should remain unchanged

`temperature`, `top_p`, `max_input_tokens`, `max_output_tokens` (unset is fine), the condenser
block, `tool_concurrency_limit: 1`, `max_iterations: 500`, `security_analyzer: llm`,
`confirmation_mode: false`, `caching_prompt: true`, `drop_params: true`,
`native_tool_calling: true`, `api_mode: auto`, the worktree settings. Reason in each case: no
archived incident is attributable to them, and each is either a safe default or load-bearing for
long runs. Changing them would be tuning without evidence.

---

## 7. Non-settings root causes

1. **Ephemeral automation sandboxes with a shallow clone.** `git_full_clone: false` plus one
   sandbox per run means committed-but-unpushed work vanishes. This is the mechanism behind
   "the agent says done and nothing changed".
2. **A watchdog that lives inside the thing it watches.** F2 says it: *"Everything we built …
   runs inside the conversation, so it died with it."* No external detector exists.
3. **Two automations competing for one daily sandbox budget** (24 runs/day vs 20) [V].
4. **A stale `current_datetime`** in the agent context (12 days) [V].
5. **22 conversations absent from the archive** — any correlation drawn from `docs/sessions/`
   alone is incomplete [V].
6. **Least-privilege workflows** (`permissions: {}`) are correct but mean a workflow that needs to
   write must declare it; a silent no-op looks like "nothing happened".

---

## 8. Exact change instructions

UI paths are phone-friendly. **None of these were applied.** No merge, no settings change, no
new secret was made during this investigation.

**A. Delete or disable the dead Gemini profile** (item 2)
- Path: Settings → LLM → Available Profiles → `gemini_gemini-2.0-flash`
- Existing: model `gemini/gemini-2.5-flash`, provider connection `8255cabb…`, status broken
- Proposed: delete the profile, or clear its provider connection so it is not selected
- Why: it is the source of the 401s and it cannot work — all 8 keys return 429
- Verify: `GET /api/profiles` shows `provider_connection_broken: false`, or the profile is gone
- Revert: re-create the profile with the same model and connection id
- UI: yes.

**B. Add an independent fallback profile** (item 1)
- Path: Settings → LLM → Available Profiles → New
- Existing: one usable profile
- Proposed: add a second profile on a *different* provider that is known-good, and keep `Default`
- Why: the 10-30 outage shows one provider is a single point of failure
- Verify: `POST /api/profiles/<name>/validate` returns `valid:true`
- Revert: delete the added profile
- UI: yes. **Do not** point fallback at Gemini — it is exhausted.

**C. Give the critic its own model** (item 3)
- Path: Settings → Verification → Critic model
- Existing: `critic_model_name: null`
- Proposed: a model that is not `openhands/deepseek-v4.1-flash`
- Why: the critic currently scores work using the model that produced it
- Verify: `GET /api/v1/settings` → `agent_settings.verification.critic_model_name` is non-null
- Revert: set it back to null
- UI: yes, if the field is exposed; otherwise API-only.

**D. Bring the schedule under the sandbox limit** (item 4)
- Path: Settings → Automations → "Openhands loop" → Schedule
- Existing: `0 */2 * * *` (12/day), plus a second automation (another 12/day)
- Proposed: total ≤ 20/day — e.g. `0 */3 * * *` (8/day) and leave the second disabled
- Why: runs are being skipped with "Daily sandbox limit of 20 reached"
- Verify: `GET /api/automation/v1` shows the new cron; the next runs are not `SKIPPED`
- Revert: restore `0 */2 * * *`
- UI: yes.

**E. Enable full clone** (item 5)
- Path: Settings → (Advanced/Git) → Full clone
- Existing: `git_full_clone: false`
- Proposed: `true`
- Why: unpushed work is lost when a sandbox is reaped
- Verify: `GET /api/v1/settings` → `git_full_clone: true`
- Revert: set back to false
- UI: yes; may be API-only depending on the build.

**F. Refresh the stale clock** (item 15) — API/administrator, not a user-facing field.

---

## 9. Unverified items and access limitations

| item | status | why |
|---|---|---|
| `critic_api_key` value | **[U]** | present but masked; never read by design |
| `secrets_store` value, `search_api_key`, `sandbox_api_key` | **[U]** | masked; not read |
| the 22 conversations not in the archive | **[U]** | not exported; needs a working export key |
| account-level retry knobs beyond the profile | **[U]** | only profile-scoped values are exposed |
| behaviour on 502/503/504 | **[U]** | no controlled transient test was run — doing so would mean abusing a live provider |
| condenser summarisation fidelity | **[U]** | no context-overflow incident exists to test against |
| whether the UI exposes `critic_model_name` | **[U]** | not confirmed in this session |
| `provider_connection_broken: true` vs org connection present | **[U]** | both observed; the resolution step is not visible from outside |
| the Miss Noor automation's full run set | **[O]** partial | 19 runs returned; a 50-limit window may truncate older runs |

**Access limitation:** the runtime agent-server and the cloud account disagree on whether an LLM
API key is set (`llm_api_key_is_set: false` locally vs `llm_api_key_set: true` in the cloud). Both
were read directly [V]. This is reported, not resolved.

---

## 10. Method note

Every value in §2 was read from a live endpoint in this session; the endpoint is named in the
table at the top of §2. No SDK default was substituted for a live value anywhere. Where a value
could not be read, it is in §9 as `[U]`. The prior audit's assumption — that live settings were
invisible — is now replaced by measurement, and two of its assumed defaults (`num_retries`,
condenser size) happen to match the live values, while the ones that matter (fallback, critic
model, automation schedule) do not appear in it at all.

_This report was created by an AI agent (OpenHands) on behalf of the repository owner. Read-only:
no setting was changed, no merge was made, no secret was read._
