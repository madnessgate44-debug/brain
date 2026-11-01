# Shadow audit — Watcher↔ChatGPT channel and engagement heartbeat

Auditor: Shadow (independent). Date: 2026-11-01 (Africa/Cairo). Scope: the GitHub issue-comment
receiver automation and the engagement heartbeat created on issue #240.

Method: read the live automation records and run history through the OpenHands automation API,
read issue #240 comments through the GitHub API, and compare claims against observed runtime
fields. No claim below is accepted from prose alone.

## 1. Objects audited

| object | id | trigger | state |
|---|---|---|---|
| event receiver | `017c4b55-8904-47b0-863e-a36ca4df406a` | `issue_comment.created` | ACTIVE |
| engagement heartbeat | `c2521706-7a97-4d64-b191-0b29ddc10682` | cron `*/20 * * * *` | ACTIVE |
| superseded draft | `7aea2400-61ef-42dd-8b6f-c4de5266bf9f` | `issue_comment.created` | DELETED |

## 2. Findings

### F-1 — Event receipt is real (contradicts a parallel-session claim) — PASS
Evidence: run `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e` returned `trigger_source: "event"`,
`conversation_id: 24045ceb63d749a8b682e47b88218ca7`, created `06:02:33Z`, one second after
source comment `6554206319`. Runs `0c2fe620…` and `3b276fea…` are likewise event runs.
A separate session asserted the receiver "cannot be scoped on this account". The runtime
evidence does not support that assertion. Verdict: receipt works; the claim is unproven.

### F-2 — Loop guard — PASS, with a caveat
The filter excludes bodies containing the reply marker, and the reply template forbids the
trigger handle. Caveat: the guard is content-based, not identity-based. A human comment that
merely quotes the reply marker is silently dropped. This is safe (fail-closed) but means a
legitimate message can be missed. Residual risk: LOW.

### F-3 — Deduplication — PASS (claimed, weakly evidenced)
Runs report a KV claim keyed by source comment id returning first-claim status. This is
self-reported by the run, not independently observable through the automation API. Verdict:
PLAUSIBLE, not independently verified. Recommend a follow-up test that posts the same marker
twice and counts replies.

### F-4 — Bot-loop prevention — PASS
No `[bot]` sender produced a run; the two `openhands-ai[bot]` acknowledgement comments did not
trigger the receiver. The filter's sender guard is present in the recreated receiver.

### F-5 — Spend — PARTIAL
Observed run costs: `$0.0012309304` for one event run; `$0.0` for the heartbeat run and 41 of
42 loop runs. The heartbeat at 20-minute cadence is a bounded, low, but non-zero cost path.
Verdict: disclosed, not free. Requires owner acknowledgement under the zero-cost gate.

### F-6 — Multi-session hazard — FAIL (process)
The first receiver (`7aea2400…`) was deleted mid-run by a parallel `@openhands` session, and a
second parallel session posted a channel verdict contradicting runtime evidence. Two or more
sessions acting on the same issue with different conclusions is a real integrity risk.
Mitigation: single-owner rule per automation and a coordination marker on the issue.

## 3. Verdict

- Event receipt: VERIFIED.
- Loop guard: VERIFIED (content-based caveat).
- Dedup: UNVERIFIED (self-reported).
- Bot-loop: VERIFIED.
- Spend: DISCLOSED, non-zero.
- Concurrency safety: FAIL — needs a single-owner rule.

## 4. Required follow-ups
1. Independent dedup test (same marker twice).
2. Single-owner rule for the receiver and heartbeat.
3. Owner decision on heartbeat spend.
