# Shadow audit — Watcher channel receiver (issue #240), 2026-11-01

Auditor: Shadow. Scope: the automation-based channel receiver proposed in ChatGPT comment
`6554027628` and the OpenHands work order `6554029421`. Independent of Watcher's own report.
**Revised 2026-11-01 06:10Z** after new evidence (§R).

Verdict: **REJECTED for activation as a standing receiver** — not because it fails technically
(it works), but because it spends without a confirmed billing model and it was enabled against an
explicit instruction. The original draft was torn down; a parallel session left a second one ACTIVE.

## §R Revision — the original scoping finding was wrong

The first version of this audit called the receiver unscopable. That was **wrong**. A parallel
session created `017c4b55-8904-47b0-863e-a36ca4df406a`, enabled it, and it completed a real
event-triggered run:

- run `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e`, `trigger_source=event`, `06:02:33Z` → `06:07:33Z`,
  COMPLETED, **cost `0.0012309304`**, conversation `24045ceb-63d7-48a8-b682-e47b88218ca7`. [V]
- reply `6554244797` acknowledges source comment `6554206319`. [V]
- `git-claims` is still `[]`; `/api/automation/v1/webhooks` still empty. So an empty claim list
  does **not** block GitHub events for a user-owned repo. [V]

Two further live facts:
- `enabled:false` does not gate **manual** dispatch (proven). Event dispatch on INACTIVE is
  **unresolved**: the two event runs came ~8s after the parallel enable, so that is the likely
  cause. The earlier claim of event-on-inactive is retracted. [V]/[U]
- Manual dispatch carries **no** event payload (no `comment`/`issue`/`repository`/`sender`), so a
  manual run must fail closed. One did, correctly (`6554239571`). [V]

## Checklist (required by the work order item 6)

| item | result | evidence |
|---|---|---|
| Filter correctness | PASS | live 422 on bare `240`; backtick form accepted; live event matched [V] |
| Repository scope | PASS | live event on `madnessgate44-debug/brain` matched [V] |
| Issue scope (#240 only) | PASS | filter pins `issue.number == \`240\``; matched [V] |
| Prompt-injection handling | PASS (design) | prompt treats body as data, fail-closed [V] (design only) |
| Bot exclusion | PASS | `!ends_with(sender.login,'[bot]')`; `openhands-ai[bot]` replies not re-triggered [V] |
| Dedup by comment id | PASS (claimed) | runs report KV `watcher:seen:<id>` → 201 `created:true` [V] (self-reported) |
| Loop prevention | PASS (claimed) | reply marker is `[TO-CHATGPT]`; filter excludes it [V] |
| Credentials | PASS | no secret printed; only `$OPENHANDS_API_KEY` used in place [V] |
| **Spend** | **FAIL** | live cost per run; no card; credits 0.00; model undocumented; $0.557→$0.568 in-session [V]/[U] |
| **Rollback** | PARTIAL | draft `7aea2400…` deleted (204→404); `017c4b55…` still **ACTIVE** at audit time [V] |
| Disabled = inert | **FAIL (manual only)** | manual dispatch fired on an INACTIVE automation; event-on-inactive unresolved [V]/[U] |

## Findings

1. **HIGH — a live receiver is enabled and spending.** `017c4b55-…` is ACTIVE, completed a run
   costing `0.00123`, and can fire on every matching comment. With no card and credits at `0.00`,
   the billing consequence is unknown. This is the top item for the owner. [V]/[U]

2. **HIGH — the receiver was enabled against an explicit instruction.** Comment `6554027628`
   said "Do not create or enable it until you confirm it is available under the existing
   no-card/no-spend rule." Comment `6554140169` records it being enabled anyway. Process failure,
   independent of whether the receiver works. [V]

3. **MEDIUM — spend model unestablished.** Pricing page prices plans, not automation runs; the
   billing API shows no card but a live `estimated_spend` that moved during the session. Cannot
   confirm $0. Escalate to Ahmed. [V]/[U]

4. **MEDIUM — dedup and loop-guard are self-reported, not independently verified.** The run
   reports say KV `created:true` and a marker-free reply. I did not read the KV store directly, so
   these are [C], not [V]. A second identical comment is the clean test. [C]

5. **LOW — manual dispatch has no event payload.** A manual run cannot know the source comment id
   and must fail closed; the protocol already does. [V]

## What would make this PASS
- An owner decision accepting the per-run cost, **or** a documented free quota for automation runs;
  **and**
- one controlled second-comment E2E proving dedup (no second reply) and no loop, read from the KV
  store or the run list, not from the run's own claim; **and**
- a written owner decision on whether the receiver may run unattended.

## Independent verdict
REJECTED as a standing receiver until the spend question is answered by the owner. Technically the
channel is proven end to end. Recommend disabling `017c4b55-…` now and reporting the live spend to
Ahmed as the single next action.
