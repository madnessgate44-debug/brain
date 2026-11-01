"""The standard ticket envelope — the automatic part of every message.

Both sides attach this envelope to every message. It is the same shape every time,
so a reader can see at a glance: what was received, what I was thinking, what I am
asking, and whether the ticket is still open. The loop repeats while STATE is open
and stops when it is resolved.

Required fields (owner, 2026-11-01):
  ACK       I saw the ticket (name its id) — both sides.
  TRACE     my train of thought so far, as it flowed.
  ASK       one answerable question to the other side.
  REQUEST   ask the other side for their trace and their acknowledgement.
  STATE     open | resolved.
"""
from __future__ import annotations


def ticket(
    *,
    ticket_id: str | int,
    subject: str,
    ack: str,
    trace: str,
    ask: str,
    offer: str,
    finding: str,
    now: str,
    state: str = "open",
    note: str = "",
) -> str:
    """Render the standard envelope. Every message between us uses this."""
    return f"""## [TICKET {ticket_id}] {subject}

### ACK — I saw your ticket
{ack}

### TRACE — my train of thought so far (as it flowed)
```
{trace}
```

### ASK — what I need from you
{ask}

### REQUEST — the automatic part, both directions
1. **Acknowledge you saw this ticket** (name its id) so I know it landed.
2. **Send me your complete train of thought** for your last message — the steps and what you
   considered, not only the conclusion.
3. Then post your next finding or question.
Both of us do this on every ticket, so neither is a black box and the loop keeps moving.

### OFFER — what I can do for you
{offer}

### FINDING
{finding}

### STATE — {state}
{note or "Loop continues until this reads resolved."}

— Watcher (via OpenHands) | {now}

---
_This comment was created by an AI agent (OpenHands, acting as Watcher) on behalf of the repository owner._
"""
