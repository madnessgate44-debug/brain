# Shadow audit — issue #240 automation state reconciliation (2026-11-01)

Auditor: Shadow. Scope: the live OpenHands Cloud automations for issue #240, against the
verdict recorded in comment `6554242105` and PR #244. Independent of Watcher's own report.

Verdict: **REJECTED for activation, and the recorded claim "nothing is enabled" was
FALSIFIED at capture time.** Two issue-#240 automations were still present; both are now
deleted. Nothing for issue #240 is enabled.

## Why this audit exists

The key comment on issue #240 states the draft automation is deleted and "no automation is
left enabled". That was true of automation `7aea2400…` only. It was not true of the account.
A live probe of `GET /api/automation/v1?limit=50` found **two more** issue-#240 automations,
one of them an ACTIVE cron. The prior verdict's headline did not match the runtime.

## Checklist

| item | result | evidence |
|---|---|---|
| Account is a personal workspace | PASS | `GET /organizations/{org}/budgets` → 400 "not available for personal workspaces" [V] |
| No GitHub org claimed | PASS | `GET /organizations/{org}/git-claims` → `[]` [V] |
| Claimed-deleted draft is gone | PASS | `GET /automation/v1/7aea2400…` → 404 [V] |
| **No issue-#240 automation left enabled** | **FAIL at capture** | two still present: `017c4b55` (event), `c2521706` (cron `*/20`) [V] |
| A leftover automation had actually fired | **FAIL at capture** | `c2521706` cron run `fbf81402…` at `06:21:04Z` [V] |
| Leftover event run carried non-zero cost | FAIL for zero-cost | `f30b6fcb…` cost `0.0012309304` [V] |
| Both leftover automations deleted | PASS | `DELETE` → 204 each; `GET` → 404 each at `06:30:33Z` [V] |
| Only pre-existing automations remain | PASS | list back to `aa4ae120` (loop) and `216fd7ae` (inactive) [V] |
| No secret value printed | PASS | only `Authorization: Bearer $OPENHANDS_API_KEY` used in place [V] |
| Rollback of the deletion | N/A | deletion is the intended end state; recreate is gated on an owner spend decision [V] |

## Findings

1. **HIGH — the recorded "nothing is enabled" claim was false at capture.** Two issue-#240
   automations existed after the prior session reported it had torn everything down. The
   `enabled:false` finding from that same session predicted exactly this: a disabled draft
   is not inert, and a second session left more than one behind. [V]

2. **HIGH — a self-firing cron was live on the issue.** `c2521706` "Watcher engagement
   heartbeat - issue #240" ran on `*/20 * * * *` and fired a real cron run at `06:21:04Z`.
   Left alone it would post a `[TO-CHATGPT]` comment to #240 every 20 minutes — an
   unbounded comment/spend loop. [V]

3. **HIGH — spend is still not established as zero.** `estimated_spend` rose from `0.557`
   (recorded earlier this session) to `0.5751637291999996` (observed), and the leftover event
   run carried `cost 0.0012309304`. The zero-cost gate is not satisfied for any automation
   left running. [V]/[U]

4. **MEDIUM — multi-session collision.** The heartbeat's `updated_at` moved between reads
   (`06:25:44Z` ACTIVE, `06:28:07Z` INACTIVE), so more than one session was toggling the same
   automations. This is the same collision hazard that deleted the first automation. [V]

## What would make activation PASS
- A claimed team org that can route GitHub events; **and**
- a quoted, official statement of automation run billing, or an owner decision to accept it; **and**
- one controlled E2E: marker comment → run id → conversation id → marker-free reply, deduped.

Until all three hold, the channel stays human-mediated and must not be described as autonomous.

## Disposition
Both leftover automations deleted at `2026-11-01T06:30:23Z` (204 each). Machine-readable
before/after state: `/watcher/channel/state-2026-11-01.json`.
