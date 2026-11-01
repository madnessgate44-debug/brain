# Knowledge packet and decision log — templates

Two living documents. Keep them short; every line carries provenance.

## Knowledge packet

```
# Knowledge packet — <handshake id>
Updated: <ISO-8601 UTC> by <chatgpt|openhands>

## Facts (verified this session)
- <claim> — source: <repo@commit | issue/comment/PR/run id> — label: fact

## Proposals (not yet agreed)
- <proposal> — owner: <chatgpt|openhands> — label: proposal

## Assumptions
- <assumption> — why: <reason> — label: assumption

## Superseded
- <old decision> — superseded by: <new> on <date> — label: superseded

## Unresolved disagreements
- <topic> — chatgpt says: <x> — openhands says: <y> — label: unresolved

## Open questions
- <question> — needs: <evidence|decision> — owner: <...>
```

## Decision log (append-only)

```
| date (UTC) | decision | decider | evidence ref | status |
|---|---|---|---|---|
| 2026-11-01 | <decision> | ahmed|chatgpt|openhands | <id/path> | open|done|superseded |
```

## Rules
- Never blend a proposal into a fact. Label every line.
- A conflict is surfaced, never silently resolved by one partner.
- When something is superseded, keep the old line and point to the new one.
