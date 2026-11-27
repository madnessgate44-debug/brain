BLOCKER: B1 — Shadow has no model route in Actions (`OHGeminiAPI`, `GEMINI_POOL_1..7` absent;
sweep 45568543873 = 0 WORKING, 8 NOT SET), so the Shadow gate fails closed and no pull request
can merge. Only the owner/custodian can load the pool.
B8 — `BRAIN_GITHUB_TOKEN` is `401 Bad credentials`, so the engine path cannot write even with a
model. B9 — the engine's model route answered `HTTP 503` through three attempts. Both were
measured on live run 46020431346 (2026-11-27); see `docs/readiness/BLOCKER_REGISTER.md §B`.
last_seq: 3
ack seq 3

**Owner brief**
- BLOCKER: B1 — Shadow cannot audit (no model key in Actions), so no pull request can merge.
  Verified: sweep run 45568543873 printed `SUMMARY: 0 WORKING, 8 NOT SET`.
- Changed: added this loop ledger. Brain already ships `docs/LOOP.md` (the owner grant), but the
  companion `docs/STATUS.md` was missing, so the account-level backlog Stop hook (from the OpenHands
  account library, auto-loaded into every conversation) read `last_seq` as 0 and re-flagged the
  already-handled Claude inbox message `seq 3` on every stop. Docs only.
- Evidence: the inbox store returns `seq: 3`, equal to `last_seq: 3` here, so it is already handled.
  The seq-3 task (BL-4, guard heredoc false positive) was done on the account-library repository
  `madnessgate44-debug/Openhands` and needs no work in brain. No `status=ready` item exists.
- Costs / irreversible steps: none.
- Next action for the owner: none from this file. The real work queue is the Brain hub issue #292
  and the owner's stated priorities (Amina first, after the Blind Sniper browsing work).
- Run 2026-11-08: created the ledger; no new inbox seq, no ready backlog item.

Last 5 actions:
- 2026-11-27: ran the engine path live (issue #375 -> run 46020431346). It failed: the planner
  called a plainly mutating objective `read_only`, the model route returned `HTTP 503`, and
  `BRAIN_GITHUB_TOKEN` returned `401`. Fixed the planner
  (`brain/company/mission_capabilities.py:24` + `tests/test_mission_capabilities.py`); logged the
  two credentials as B8/B9 in `docs/readiness/BLOCKER_REGISTER.md`.
- 2026-11-25: the live-run trace is now verified against GitHub, not matched as text
  (`verify_trace` in `watcher/knowledge/tools/purpose_audit.py`); the gate job exports
  `GITHUB_TOKEN` so it verifies. Evidence: issue #358 -> PR #359.
- 2026-11-24: the loop's writer now records the issue -> PR trace itself
  (`record_trace` in `scripts/start_session_loop.py`, validated by the audit's own
  `evidence_trace`); evidence: issue #363 -> PR #359.
- 2026-11-23: closed the W3 live-run gap — issue #358 -> PR #359; the audit now requires an
  issue + PR trace, not a conversation link (`watcher/knowledge/tools/purpose_audit.py`).

Next: none queued here.
