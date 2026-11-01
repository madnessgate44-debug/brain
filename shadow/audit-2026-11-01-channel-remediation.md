# Shadow audit — channel spend remediation and resulting evidence (issue #240)

Date: 2026-11-01. Auditor: Shadow. Independent of Watcher's `watcher/channel/status-2026-11-01.md`
and of the earlier `shadow/channel-audit-2026-11-01.md` (PR #244). Scope: (a) the two live
automations found ACTIVE this session, (b) the disable action taken, (c) the evidence now recorded.

Evidence tags: [V] verified in this session's runtime reads, [C] claimed by another party, [I]
inference, [U] unknown, [B] blocked.

## Verdict

**The remediation is correct and I approve it.** Two channel automations were live and able to spend
after the owner's order `6554275306` asserted none were. Disabling them is the safe, reversible
direction the owner mandated. The spend model remains **unverified**, so nothing may be re-enabled
without Ahmed's explicit approval. This is the standing recommendation.

## §1 What was live, and when

| automation | name | trigger | created | state at first read (06:11Z) |
|---|---|---|---|---|
| `017c4b55-8904-47b0-863e-a36ca4df406a` | Watcher channel - issue #240 | `issue_comment.created` | 06:00:18Z | **ACTIVE** [V] |
| `c2521706-7a97-4d64-b191-0b29ddc10682` | Watcher engagement heartbeat - issue #240 | cron `*/20 * * * *` | 06:07:35Z | **ACTIVE** [V] |

Finding: the owner's order `6554275306` (06:10:07Z) states "No automation is left enabled." The
heartbeat `c2521706` was created at **06:07:35Z** and was still ACTIVE at 06:11Z — so the statement
was already stale when written. This is a process failure, not a documentation point: a parallel
session created a new spending automation three minutes after the "nothing enabled" report. [V]

## §2 The remediation

| step | call | result |
|---|---|---|
| 1 | `PATCH /api/automation/v1/017c4b55-…` `{"enabled":false}` | **200**, `enabled=false`, `state=INACTIVE`, `disabled_reason=manual` [V] |
| 2 | `PATCH /api/automation/v1/c2521706-…` `{"enabled":false}` | **200**, `enabled=false`, `state=INACTIVE`, `disabled_reason=manual` [V] |
| 3 | `GET /api/automation/v1?limit=100` (after) | both INACTIVE; only `aa4ae120…` "Openhands loop" still ACTIVE [V] |

`aa4ae120…` was **left ACTIVE** deliberately: it predates this work (created 2026-10-29) and is the
owner's standing 2-hourly loop, not a channel receiver. Disabling it is out of scope for this task.
This audit records that decision so it is not mistaken for an oversight. [V]

## §3 Why disable, not delete

- The owner's order said do not recreate or enable; it did not order deletion. Disabling is the
  minimal reversible action and preserves the exact configuration for this audit. [V]
- Delete remains available (`DELETE` → 204, proven in PR #244) if Ahmed decides the receiver is not
  wanted at all. [C]
- Rollback is one call (`PATCH {"enabled":true}`), so the decision is fully reversible. [V]

## §4 Checklist (work order item 3)

| item | result | evidence |
|---|---|---|
| Detect live spending automations | PASS | two ACTIVE automations found by `GET` [V] |
| Stop the spend | PASS | both PATCHed to INACTIVE [V] |
| Reversible | PASS | one PATCH restores each [V] |
| Scope respected | PASS | `aa4ae120…` untouched; no other automation changed [V] |
| No secret disclosed | PASS | only `$OPENHANDS_API_KEY` used in place; no value printed [V] |
| No merge / deploy / paid action | PASS | none performed [V] |
| Evidence recorded | PASS | status note + this audit [V] |
| Spend model established | **FAIL (open)** | no card, credits `0.00`, observed non-zero run cost, docs silent [U] |
| Root cause of the process failure | **PARTIAL** | parallel sessions acting on shared automation state; no single-writer rule enforced [V] |

## §5 Findings

1. **HIGH — a new spending automation was created after the "nothing enabled" report.** Root cause:
   multiple OpenHands sessions act on the same account with no ownership lock; each can create or
   enable automations. Symptom (an enabled automation) is fixed; the cause (no single writer) is
   not, because it cannot be fixed from inside one session. **Prevention:** the owner's rule "do not
   run competing sessions that mutate the same automation" (`6554275306`) must be respected by every
   session; this audit recommends no session create or enable an automation on this issue. [V]/[I]

2. **HIGH — spend remains unverified.** The zero-cost gate is not satisfied: billing is undocumented
   and observed cost is non-zero. Both automations are now disabled, which is the correct fail-closed
   state. Re-enabling needs Ahmed. [U]

3. **MEDIUM — the "no automation is left enabled" claim was written from stale state.** Whoever
   reports channel status must re-read `GET /api/automation/v1` in the same minute as the claim.
   The status note does this. [V]

4. **LOW — the heartbeat automation's own guard was weak.** It posts a `[TO-CHATGPT]` comment every
   20 minutes whether or not ChatGPT replied (its prompt step 6: "do not go silent"). That is
   guaranteed chatter if ChatGPT is asleep, which the owner explicitly discouraged ("Do not post
   artificial periodic chatter", `6554163641`). Disabling it also removes that risk. [V]

## §6 What would make the channel PASS

- Ahmed accepts the per-run cost **or** a documented free quota for automation runs is found; **and**
- one controlled second-comment E2E proves dedup (no second reply) and no loop, read from the KV
  store or the run list, not from the run's own claim; **and**
- a single-writer rule is in force so no second session mutates the automation mid-test.

Until then: **REJECTED for activation**, disabled, human-mediated channel only.

— Shadow. This audit was created by an AI agent (OpenHands) on behalf of the repository owner.
