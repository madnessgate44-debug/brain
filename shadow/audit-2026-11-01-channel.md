# Shadow audit — Watcher channel contract (branch `openhands/watcher-channel-240`)

Auditor: Shadow. Date: 2026-11-01. Scope: `scripts/watcher_channel.py`,
`tests/test_watcher_channel.py`, `watcher/channel.md`.

**Independence limitation:** this audit is agent-authored in the same session that wrote
the change. It is a structured self-review, not an independent second party. Treat it as
Observed-not-verified until a separate session or human re-checks it.

## Checklist

| item | result | evidence |
|---|---|---|
| Fail-closed: malformed event rejected | PASS | `test_malformed_event_is_rejected` |
| Fail-closed: wrong repository rejected | PASS | `test_skips_wrong_repository` |
| Fail-closed: wrong issue rejected | PASS | `test_skips_wrong_issue` |
| Fail-closed: bot sender rejected (case-insensitive) | PASS | `test_skips_bot_sender_case_insensitively` |
| Loop guard: our own `[TO-CHATGPT]` reply cannot re-trigger | PASS | `test_skips_own_reply_to_prevent_loop` |
| Marker required (`@watcher` or `[TO-WATCHER]`) | PASS | `test_accepts_marker_addressed_owner_comment`, `test_skips_comment_without_marker` |
| Dedup: one comment id → one HANDLE | PASS | `test_dedup_claims_each_comment_id_once` |
| Dedup: skipped comment does not consume an id | PASS | `test_skipped_comment_does_not_consume_id` |
| Reply carries source/run/conversation/automation ids | PASS | `test_reply_contains_required_evidence_fields` |
| Reply states receipt mode truthfully | PASS | `test_reply_reports_human_opened_session_truthfully` |
| Reply never contains the trigger marker | PASS | `test_loop_guard_rejects_marker_in_reply` |
| No secret value read, written, or printed | PASS | module has no network/secret access; `git grep` sweep clean |
| No merge, deploy, spend, or automation mutation | PASS | diff is scripts + tests + docs only |

## Findings

- The module is pure: no I/O, no secrets, no network. It is the contract any receiver
  (automation or Actions fallback) must satisfy, and it is unit-tested.
- The live receiver is **not** in this repo, so this audit covers the contract, not the
  deployed automation. The receiver investigation and its rejection verdict are in
  `watcher/channel/receiver-spec.md` and `shadow/channel-audit-2026-11-01.md`.
- The two-consecutive-handoff acceptance test is **NOT VERIFIED** and is not claimed.

## Verdict

Contract: VERIFIED (15 tests pass). Deployed loop: the event receiver works (run
`f30b6fcb…`, `trigger_source=event`, autonomous), but the strict two-consecutive-handoff
acceptance test is NOT VERIFIED, and zero-cost is NOT VERIFIED. See
`watcher/channel/receiver-spec.md` and `shadow/channel-audit-2026-11-01.md`.
