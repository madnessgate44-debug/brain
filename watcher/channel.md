# Watcher ↔ ChatGPT channel (issue #240) — contract

The deterministic, unit-tested contract for the issue #240 conversation channel, plus
the current, evidence-based status. The receiver investigation lives in
`watcher/channel/receiver-spec.md`; the audit in `shadow/channel-audit-2026-11-01.md`.
Last updated: 2026-11-01.

## Why this file exists

Several sessions worked issue #240 concurrently and produced two contradictory verdicts on
the receiver (comment `6554242105` rejected it; `6554293217` retracted that). The tested
module below is the one part every version agrees on: whatever receiver is used, it must
fail closed, dedup by comment id, and never let its own reply re-trigger the loop. This
file records that contract and the live status without overclaiming either way.

## Contract (`scripts/watcher_channel.py`)

- Trigger marker: `@watcher` or the `[TO-WATCHER]` prefix.
- Reply marker: `[TO-CHATGPT]`, which must never contain `@watcher` (loop guard).
- Fail-closed order: malformed payload → wrong repository → wrong issue → bot sender →
  our own reply → missing marker → dedup. Dedup is claimed last, so a skipped comment
  never consumes an id.
- One source comment id yields at most one run and one reply.
- A reply may claim RECEIVED only when the receiver run exists and names the source id.

15 unit tests cover this: `tests/test_watcher_channel.py`.

## Status — event receiver works; spend is the blocker

| state | result | evidence |
|---|---|---|
| (a) event automation enabled | Yes | `017c4b55-8904-47b0-863e-a36ca4df406a`, ACTIVE |
| (b) event received automatically | Yes | run `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e`, `trigger_source=event`, 1 s after source comment `6554206319`, no human |
| (c) Watcher reply delivered | Yes | reply `6554244797` names the source comment |
| (d) second consecutive unattended handoff | NOT VERIFIED | one clean automatic receipt is evidenced; a second consecutive cycle is not |
| (e) zero-cost | NOT VERIFIED | no card, credits `0.00`, yet runs carry real cost (~`$0.00123`/run); billing undocumented |

The loop guard is itself proven by a real event: test comment `6554186898` did not fire
because its body contained `[TO-CHATGPT]`, which the filter excludes.

## Open problems

- **Spend.** Two receivers are ACTIVE (`017c4b55`, plus heartbeat `c2521706`). The
  zero-cost gate is not satisfied. This is an owner decision, per WATCHER.md §15.
- **Multi-session collisions.** Sessions enabled, deleted, and recreated receivers
  concurrently; one earlier receiver (`7aea2400`) was deleted mid-run by a parallel
  session. Coordinate before mutating the channel.
- **`enabled:false` is not inert for manual dispatch**; delete a draft rather than park it.

## Rules

- Never claim RECEIVED unless the receiver run exists and names the exact source comment id.
- State truthfully whether receipt was an automatic event or a human-opened session.
- No secret value is read, written, or printed. No merge, deploy, or spend.
