# Watcher's first plan — ranked queue (issue #240)

Date: 2026-11-01. Author: Watcher (OpenHands session). Written in answer to the owner's order
`6554275306` item 4 and ChatGPT's request `6554196184` for "a ranked action plan: task, single owner,
dependency, acceptance evidence, and next checkpoint."

Reconciliation: this merges ChatGPT's cycle-0 priorities (`6554197715`) with the Firstborn
re-inspection (`watcher/reports/forge-parity-reinspection-2026-11-01.md`) and the channel state
(`watcher/channel/status-2026-11-01.md`). Where the two packets disagree, the row says so.

## Ranked queue

| # | task | single owner | dependency | acceptance evidence | next checkpoint |
|---|---|---|---|---|---|
| 1 | Keep the two channel automations **disabled**; do not re-enable or recreate without Ahmed | any session acting on #240 | owner spend decision | `GET /api/automation/v1` shows `017c4b55…` and `c2521706…` INACTIVE | every session start: re-read the list before claiming channel state. **Proven necessary:** a parallel session re-enabled `c2521706…` at ~06:21Z and it spent a cron run before this session re-disabled it (`06:24:13Z`) |
| 2 | Owner decision: may automation runs spend? (one yes/no) | **Ahmed** | none | a comment stating yes or no; if yes, a stated per-run ceiling | blocks rows 3 and 4 |
| 3 | One controlled second-comment E2E proving dedup + no loop (only if row 2 = yes) | Watcher | row 2; single-writer rule | run id + KV `watcher:seen:<id>` read directly + no second reply + no `[TO-CHATGPT]` re-trigger | after the test, re-disable |
| 4 | GitHub Actions `issue_comment` receiver (alternative to row 3) | Shadow | Actions-secrets write path (currently 403) | a real `issues` run that posts one reply, deduped | blocked until the token has Actions-secrets write |
| 5 | First real Forge E2E benchmark on Firstborn issue #130 | OpenHands/Forge | row 2 = no is fine (this is free); raise `FORGE_MAX_FILES`/`FORGE_MAX_EDITS` for the run | trigger → plan → edits → tests → branch → PR artifact, recorded in the 13-field table | smallest parity-advancing step |
| 6 | Widen the Forge terminal registry carefully toward Claude Code parity | Watcher proposes, Ahmed approves the change of authority | row 5's evidence that the narrow registry blocks a real task | a scoped diff adding named commands with tests; Shadow audit | after row 5 identifies the blocking command |
| 7 | Independent re-inspection of the cycle-0 scorecard | Watcher | Forge @ main read | **DONE** — `watcher/reports/forge-parity-reinspection-2026-11-01.md` (no row disproved; 2 refined, 1 narrowed) | complete |
| 8 | Build `/watcher/knowledge/` from Ahmed's history | Watcher | source access | **DONE** — `watcher/knowledge/index.md` (7 indexed sources) | complete; needs the ppt to extend |
| 9 | Shadow audit of the receiver and the remediation | Shadow | rows 1–3 | **DONE** — `shadow/audit-2026-11-01-channel-remediation.md` (REJECTED for activation; remediation approved) | complete |

## Overlaps, gaps, contradictions (owner order item 1, ChatGPT request item 3)

- **Overlap:** both packets rank the channel first and the Forge benchmark second. Agreed.
- **Gap ChatGPT named, now confirmed:** skills and lifecycle hooks are absent in the inspected
  Firstborn scope. Not a contradiction — ChatGPT marked them "NOT FOUND IN INSPECTED SCOPE". [V]
- **Contradiction, resolved:** ChatGPT's "Terminal / command execution — PARTIAL" understates how
  tight the registry is. It is exactly **11 commands**, not merely "strict". Narrowed in row 6. [V]
- **Contradiction, resolved:** the owner's order says "No automation is left enabled"; the runtime
  showed two ACTIVE. Runtime wins; both are now INACTIVE. Recorded in the channel status note. [V]
- **Gap:** the "ppt" is still missing. It blocks full completion of the knowledge base. [U]

## Explicit non-goals (this session)

- No merge to `main`, no deploy, no paid action, no secret disclosure. [V]
- No re-enable of any channel automation. [V]
- No E2E claim for Forge; source re-inspection only. [V]

— Watcher (via OpenHands). This plan was created by an AI agent on behalf of the repository owner.
