# Work queue — issue #240 (checkpoint 2026-11-01)

Implements the queue format from the `[TO-OPENHANDS] Addendum` comment `6554077692`. One row per
work packet. Status: QUEUED / CLAIMED / IN_PROGRESS / BLOCKED / REVIEW / VERIFIED / CLOSED.
Author: Watcher (OpenHands session). Tags: [V] verified, [C] reported, [U] unknown, [B] blocked.

## Packets

| id | parent | objective | owner | deps | acceptance evidence | status |
|---|---|---|---|---|---|---|
| P1 | #240 | Independent re-inspection of ChatGPT cycle-0 scorecard | Watcher | Firstborn read | row-by-row confirm/correct with `path:Lx` | **VERIFIED** — `watcher/scorecard/forge-vs-claude-code-cycle-1.md` |
| P2 | #240 | Record verified live channel state; correct PR #244's "nothing enabled" | Watcher | automation API | automation + run ids, timestamps, cost | **VERIFIED** — `watcher/channel/live-state-2026-11-01.md` |
| P3 | #240 | Knowledge base from Ahmed's history + ppt | Watcher | ppt location | knowledge base committed | **PARTIAL** — history done; ppt **BLOCKED** (`watcher/knowledge/ahmed-operating-context.md`) |
| P4 | #240 | Shadow audit of P1+P2 | Shadow | P1, P2 | verdict in `/shadow/` | **VERIFIED** — `shadow/audit-240-cycle1-2026-11-01.md` |
| P5 | #240 | First real Forge E2E benchmark | OpenHands/Forge | issue #130 check | trigger → plan → edits → tests → branch → PR artifact | **QUEUED** — no live Forge run executed this session |
| P6 | #240 | Second consecutive handoff test | ChatGPT → Watcher | receiver live | fresh run, no human, reply with ids | **PARTIAL** — autonomous receipt observed (run `f30b6fcb…`, `trigger_source=event`, ~1s); a *second consecutive* handoff is not yet observed |
| P7 | #240 | Fix Firstborn failing `Verification and Build Checks` | Firstborn owner | P1 root cause | test passes on `main` | **QUEUED** — root cause found; cross-repo edit needs coordination |
| P8 | #240 | Owner decision: spend on the live automations | Ahmed | — | one yes/no | **BLOCKED** on owner |

## Resume point

Next eligible packet with no dependency is **P7** (Firstborn CI fix — apply option (b) from the
cycle-1 report) and **P5** (Forge E2E benchmark). Both are cross-repo or live-run work and are
outside this session's no-merge/no-deploy boundary; they are queued, not started.

## Owner question (one)

Ahmed: the two live automations (`017c4b55…` event receiver, `c2521706…` 20-minute heartbeat)
cost money per run and there is no recorded spend decision for them. Keep them running — yes or
no? See `watcher/channel/live-state-2026-11-01.md`. This is not covered by the technical merge
grant (WATCHER.md §15: money is an owner decision).
