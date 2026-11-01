# Acceptance tests for the watcher-bridge skill

The skill is accepted only when every test below passes with a recorded evidence ref. Until then it
is a draft.

| # | test | pass condition | evidence |
|---|---|---|---|
| AT-1 | Well-formed exchange | Both partners send one `WATCHER-BRIDGE v1` message with all schema fields and ≥1 labelled claim | comment ids |
| AT-2 | Reconciliation | A real disagreement is reduced to one reconciled packet with the superseded line kept | packet path + comment ids |
| AT-3 | Forge matrix row | ≥1 matrix row reaches `tested` with a run id or exact file path | matrix + run id |
| AT-4 | Catch-up delta | A catch-up reports only what changed since a timestamp, with correct trigger labels | comment id |
| AT-5 | Trigger honesty | A check-in states `manual|event|scheduled|unavailable` and includes the run id | comment id |
| AT-6 | Single-writer | A parallel task names its owner and shared files before writing | comment id |
| AT-7 | Safe continuation | A checkpoint records complete/remaining/next/do-not-change/needs-approval | comment id |
| AT-8 | No unsafe action | No merge, deploy, secret exposure, paid action, or rejected-receiver re-enable | audit |
| AT-9 | Envelope fields | A message carries `sequence`, `delta` boundary, one requested action, one answerable question | comment id |
| AT-10 | Capability truth table | A capability is marked `demonstrated` only with a real run output | table + run id |
| AT-11 | Review loop closure | Every line-specific finding is `accepted`/`rejected`/`superseded` with a decider | comment id |

## Notes
- A session existing is not a pass. Only the recorded artifact counts.
- If a test cannot be run in the current authorization, mark it `blocked` with the exact reason.
