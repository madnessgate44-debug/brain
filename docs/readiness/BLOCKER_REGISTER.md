# BLOCKER_REGISTER — Phase 1 (2026-11-07)

One register: every blocker, dependency-ordered, with an owner and a safe verification. Tags:
`[V]` verified, `[U]` unproven, `[B]` blocked. Read-only; no secret value, merge, deploy, or spend.

## A. Instruction conflicts (resolve in the docs)

| ID | Conflict | Files | Proposed minimal reconciliation | Owner | Tag |
|---|---|---|---|---|---|
| C1 | ChatGPT's role | `docs/WORKFLOW.md:8-16` ("patient/second investigator") vs the directive (product architect) | amend the AGREEMENT line in `WORKFLOW.md §0` to the directive's wording | Owner | `[V]` |
| C2 | Merge authority | `docs/LOOP.md:6` (Shadow+Watcher merge) vs the directive (Shadow = reviewer; OpenHands = execution lead) | keep Shadow's merge right **or** move it; one line in `LOOP.md` | Owner | `[V]` |
| C3 | Execution posture | `ENGINEERING_EXECUTION_OS.md:118` (read-only default) vs bounded repairs | add a bounded PR-only grant paragraph, scoped to the 5 products | Owner | `[V]` |
| C4 | Key ownership | `WATCHER.md §14` (Shadow writes keys) vs PR #293 Shadow BLOCKED | add the pool, or accept Shadow-blocked for the Amina exercise | Owner | `[V]` |
| C5 | Hub identity | `watcher/bridge/hub.py:17` (#240) vs the live channel (#292) | point the hub helper at #292 | OpenHands (with approval) | `[V]` |

## B. Capability blockers

| ID | Blocker | Impact | Remediation | Owner | Tag |
|---|---|---|---|---|---|
| B1 | Shadow's model route absent (`OHGeminiAPI`, `GEMINI_POOL_1..7`); sweep `42421027202` = **0 WORKING, 8 NOT SET** | no independent audit → no merge under `LOOP.md` | custodian (see `CREDENTIAL_REQUIREMENTS.md §4`) loads the pool via the authorized path | **Custodian** (the correction names "Ghost", which does not exist in the repo — an undefined role to resolve), not the Owner | `[B]` |
| B7 | `shadow-keys.yml` GitHub probe reports `github: FAIL (http 403)` — probes `/user` with a workflow token that is not scoped for it | misclassified as a credential failure | point the probe at `GET /repos/{owner}/{repo}` | OpenHands | `[V]` |
| B2 | Repo-secret listing is 403 for this token | cannot prove presence for most secrets | token scope, or a human lists them | Owner | `[B]` |
| B3 | Agent wake/trigger not wired | no real-time multi-agent coordination | adopt SwarmChat `wait` or a GitHub dispatch bus | Owner | `[U]` |
| B4 | SwarmChat is sandbox-local | live room is not durable; a Cloud automation cannot reach it | treat #292 as the durable record; or host SwarmChat | Owner | `[V]` |
| B5 | Brain web-research capability unproven for the runtime | Phase-2 research must run via a workflow, not the document worker | test `brain-rd-discovery` on a live issue | OpenHands | `[U]` |
| B6 | Watcher's Phase-1 checks are not in its daily cycle | readiness ran manually this phase | add a readiness section to `watcher-daily.yml` | OpenHands | `[V]` |

## C. Archival blockers (Phase-1 §2 of the directive)

| ID | Blocker | Impact | Remediation | Owner | Tag |
|---|---|---|---|---|---|
| A1 | The archive is produced by `watcher-session-log.yml` (daily 00:30 UTC, auto-merge) — it **already exists** | not a blocker; the claim "no automatic archiving" was wrong | document it; harden it | OpenHands | `[V]` |
| A2 | No leak-scan gate in the exporter before this PR | a residual secret could be committed | added `check_leaks` + fail-closed scan (this PR) | OpenHands | `[V]` |
| A3 | Owner↔ChatGPT conversations are not reachable from this credential | the ChatGPT half of the record is missing | ChatGPT exports its own history and pastes it | Owner/ChatGPT | `[B]` |

## D. Dependency order (what unblocks what)

1. **C4 → B1** — decide Shadow's key route; if approved, add the pool; Shadow's audit then unblocks
   the merge rule for #293/#294 and for the Amina exercise's review step.
2. **C1, C2, C3** — one-line doc reconciliations; needed before any Phase-2 execution so the
   read-only boundary and the merge rule are unambiguous.
3. **B5** — prove Brain's research route before Phase 2 relies on it.
4. **A1/A2** — the archive is live; this PR adds the fail-closed gate. Verify on the next daily run.
5. **B6, C5** — small follow-ups, safe to batch.

## E. Owner decisions (one per item)

1. Add Shadow's pool (`OHGeminiAPI` + `GEMINI_POOL_1..7`) — yes / no?
2. Keep Shadow's merge right (`LOOP.md`) or move it to OpenHands — which?
3. Approve a bounded PR-only execution grant scoped to the 5 products — yes / no?
4. Merge the two docs/infra PRs #293 and #294 (non-behavioural) — yes / no?
5. Point the ticket hub helper at #292 (`C5`) — yes / no?

## F. ChatGPT-integration blockers (workstream `6713088768`)

See `CHATGPT_INTEGRATION.md` §13. Summary: G1 ChatGPT has no autonomous inbound invocation `[B]`;
G2 the Owner must mount the MCP connector + key in ChatGPT `[OWNER ACTION]`; G3 SwarmChat is not
durable `[B]`; G4 a ChatGPT scheduled task may need a paid tier `[OWNER ACTION]`. The supported path
that already exists: the live Brain MCP connector (`docs/CONNECTOR.md`) + GitHub #292.

## G. Automation inventory (ChatGPT ticket §E — prove or state NOT CREATED)

| Automation | Exists? | Evidence | Tag |
|---|---|---|---|
| Daily conversation archive | **yes** | `watcher-session-log.yml`, cron `30 0 * * *`, auto-merge; latest success 2026-11-07T06:23:25Z | `[V]` |
| Watcher daily cycle | **yes** | `watcher-daily.yml`, cron `0 4 * * *`, last 5 runs success | `[V]` |
| Brain R&D discovery (web research) | **yes** (workflow) | `brain-rd-discovery.yml`, `workflow_dispatch` | `[V]` workflow; `[U]` end-to-end run |
| Public web research (`/brain browse`) | **yes** (workflow) | `brain-browser-research-issue.yml` | `[V]` workflow; `[U]` run |
| **OpenHands daily production audit/fix automation** | **NOT CREATED** | only a form was prepared in this session (no `automation_form_update` submit; no automation id; no run) | `[V]` absent |
| Secret health checks (`ai-provider-secret-check`, `deepseek-api-key-check`, `brain-credential-preflight`) | exist but **skipped** | all recent runs `completed/skipped` (e.g. 2026-11-07T16:19:24Z) — their triggers did not fire | `[V]` skipped |
| ChatGPT's 3 read-only checkpoints (09:00/14:00/20:00 Cairo) | separate, not Brain's | ChatGPT-side; do not conflate with Brain's automation | `[U]` from here |

**Distinct things — do not conflate:** (1) ChatGPT's read-only coordination checkpoints; (2) Brain's
scheduled audit/fix automations; (3) the OpenHands daily production automation (not created).

_Phase 1 deliverable 4 of 4. Read-only._
