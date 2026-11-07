# Channel state — verified live, 2026-11-01T06:05Z

Answers ranked-plan task #2 (receiver state) and corrects the central claim of the parallel PR
#244 branch `openhands/watcher-channel-240`. Author: Watcher (OpenHands session), 2026-11-01.

Tags: [V] verified live this session, [C] reported, [I] inference, [U] unknown, [B] blocker.

## Why this file exists

The parallel session's spec (`watcher/channel/receiver-spec.md`, PR #244) records "**Nothing
enabled. No event receiver is live.**" and "the draft was created, tested, and **deleted**". The
deleted draft it refers to is `7aea2400-61ef-42dd-8b6f-c4de5266bf9f`. That statement was true of
that one id at that moment, but it is **not** the current state. [V]

A second, identical receiver was created afterwards (`017c4b55-8904-47b0-863e-a36ca4df406a`), it
is **ACTIVE**, and it has fired. The channel is live and billing. The spec must not be merged as
the current-state description without this correction. [V]

## Verified live state (read from the automation API this session)

`GET /api/automation/v1?limit=50` with `Authorization: Bearer $OPENHANDS_API_KEY` → 200. [V]

| automation id | name | trigger | enabled | state |
|---|---|---|---|---|
| `017c4b55-8904-47b0-863e-a36ca4df406a` | Watcher channel - issue #240 | `issue_comment.created` (github) | **true** | **ACTIVE** |
| `c2521706-7a97-4d64-b191-0b29ddc10682` | Watcher engagement heartbeat - issue #240 | cron `*/20 * * * *` | **true** | **ACTIVE** |
| `aa4ae120-c4bd-4cf5-9762-ddf5638109c5` | Openhands loop | cron `0 */2 * * *` | true | ACTIVE |
| `216fd7ae-94a1-4779-a3cd-e95b6053166b` | Miss Noor - autonomous owner window (9h) | cron `0 */2 * * *` | false | INACTIVE |

Live filter on `017c4b55…` [V]:

```
icontains(comment.body, '@watcher')
  && !icontains(comment.body, '[TO-CHATGPT]')
  && repository.full_name == 'madnessgate44-debug/brain'
  && issue.number == `240`
  && !ends_with(sender.login, '[bot]')
```

This differs from the PR #244 spec filter: it adds `!icontains(comment.body,'[TO-CHATGPT]')` and
`!ends_with(sender.login,'[bot]')`. The bot guard the #244 audit asked for is present live. [V]

## Evidence the receiver actually fired (not just "enabled")

`GET /api/automation/v1/017c4b55-…/runs?limit=30` → 200, one run: [V]

| field | value |
|---|---|
| run id | `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e` |
| status | COMPLETED |
| trigger_source | **event** |
| created | 2026-11-01T06:02:33.865369Z |
| started | 2026-11-01T06:02:34.566391Z |
| cost | **0.0012309304** (non-zero) |

Source comment `6554206319` was created at `06:02:32Z`; the run was created at `06:02:33.865Z`
— about 1 second later, with `trigger_source=event` and no human. That is the autonomous
receipt the acceptance test asks for. [V]

## Spend is real and this receiver is not free

- The single observed event run carried `cost = 0.0012309304` — non-zero. [V]
- The parallel spec already recorded two non-zero cron runs (`0.00133`, `0.00266`) and a live
  `estimated_spend` counter, and concluded the zero-cost gate is **not satisfied**. [C]
- Adding the heartbeat `c2521706…` (`*/20 * * * *`, ACTIVE, one run so far at `cost 0.0`) means
  up to ~72 automated runs/day on top of per-comment runs. [V]/[I]

Per the zero-cost gate and WATCHER.md §14.6/§15, running a service that spends money is an
owner decision. This is currently running without a recorded owner spend decision. That is the
one thing that needs Ahmed — one yes/no. [V]

## What I did NOT do

No automation was created, enabled, disabled, or deleted by this session. No secret was read or
printed. Nothing was merged or deployed. [V]

## Recommended next step (no owner question needed for the technical call)

1. Treat PR #244's "nothing enabled" as superseded by this record; its cost/rollback analysis
   stands and its filter is a strict subset of what is live. [V]
2. Keep the two live automations only if Ahmed answers **yes** to the spend question. Otherwise
   disable `017c4b55…` and `c2521706…` (PATCH `{"enabled": false}`, then confirm the run list
   stops growing). [V]
3. Re-run the Shadow audit against the live filter above, not the spec filter. [I]
