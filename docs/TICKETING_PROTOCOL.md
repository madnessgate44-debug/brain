# Ticketing protocol — every interaction, every participant

Owner directive (2026-11-07): "start each response by checking the chat room, leaving your
ticket about the current situation including the changes in the transcription of the
conversation, then you reply to a request … that ticketing system should be followed in each
and every interaction … make sure you and ChatGPT and the other agents are on the same [page]."

This file makes that mechanical. It is the standing protocol for every agent that works on this
repository: OpenHands, ChatGPT, Forge, Shadow, Watcher, and Brain's runtime.

## The rule (three steps, in this order)

1. **READ FIRST.** Before any reply or action, read the shared room:
   - the durable hub: GitHub issue `madnessgate44-debug/brain#292` (newest comments), and
   - the live room: SwarmChat `#general #audits #reports #alerts` when a server is up.
   Do not act on a stale view. Name the newest comment id you read.
2. **LEAVE A TICKET.** Post one ticket (the envelope below) that states: what you read, the
   current situation, the change in the conversation transcript since the last ticket, and
   exactly one ASK.
3. **THEN ACT AND REPLY.** Do the work, then reply on the same ticket (or open a new one) with
   the evidence and the STATE.

## The ticket envelope

The canonical shape is `docs/WORKFLOW.md` §2. Fields, all required:

```
## T<id> · <subject>
**AGREEMENT** <the current role line — see below>
**ACK** <the exact comment id + GitHub time this ticket answers>
**TRACE** — my train of thought since the last ticket:
```
[<github time>] <what I was thinking> -> <what I did>
```
**TIMING** this loop took <measured duration>.
**ASK** <exactly ONE answerable question>
**OFFER** <what I offer the other side>
**FINDING** <CONFIRMED|HYPOTHESIS|UNKNOWN|DISPROVED>: <the new fact, with its evidence ref>
**REQUEST** name this ticket id back + send your trace, or state its acceptance criteria pass.
**STATE** <open|resolved> · owner <owner> · acceptance: <criteria>
— <who> · <github_now> · _AI agent on behalf of the owner._
```

Rules: ACK names the exact comment id. ASK is one question. FINDING is tagged. STATE resolves
only when acceptance criteria pass — never because the chat continued. Timestamps come from the
GitHub clock (`github_now()` in `watcher/bridge/hub.py`), never the local clock.

## Current AGREEMENT line (supersedes the stale 2026-11-01 line)

The old line ("Watcher = doctor/teacher · ChatGPT = patient/second investigator") is superseded by
the Owner directive of 2026-11-07 (comment `6712932899`):

> **AGREEMENT** OpenHands = engineering execution lead · ChatGPT = Owner-facing product/requirements
> architect and context challenger · Watcher = readiness coordinator and service desk · Forge =
> bounded coding executor · Shadow = independent adversarial/security reviewer · Brain = the
> orchestration/control plane · Ahmed = approver. Claude is removed. Evidence-tagged.

`docs/WORKFLOW.md` and `docs/LOOP.md` still carry the old wording; the reconciliation is proposed
in the readiness phase, not applied unilaterally.

## Transcript discipline

- The full transcript of the originating conversation lives at
  `docs/transcripts/2026-11-07-daily-automation-conversation.md` (updated at the end of each chat).
- Every ticket carries the **transcript delta** — the new turns since the previous ticket — not the
  whole transcript.
- Rendering is scripted and secrets are redacted before writing; a leak sweep runs before any push.

## Who follows it

| Participant | Reads the room | Posts a ticket | Where |
|---|---|---|---|
| Owner | yes | comments | #292 |
| ChatGPT | via the owner | yes | #292 |
| OpenHands | yes | yes | #292 + SwarmChat |
| Forge | yes | yes | #292 (via its workflow) |
| Shadow | yes | yes | #292 (audit comment) |
| Watcher | yes | yes | #292 + SwarmChat |
| Brain runtime | yes | yes | #292 + SwarmChat (its daily run) |

## Tooling that already exists

- `watcher/bridge/hub.py read [N]` — newest N hub comments + the true GitHub time.
- `watcher/bridge/hub.py post FILE|-` — post a hub comment.
- `watcher/bridge/envelope.py` — render the envelope programmatically.
- `scripts/report_to_channels.py` — fan a report out to #292 + SwarmChat `#reports`/`#audits`.

Nothing here is new machinery; it is the existing hub + envelope, applied on every interaction.

_Established 2026-11-07 by the OpenHands agent on behalf of the owner._
