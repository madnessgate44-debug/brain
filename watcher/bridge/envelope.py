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

A ticket is not "open because the conversation continues". It carries an explicit
owner and acceptance criteria, and it resolves only when those criteria pass.
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
    owner: str = "Watcher (OpenHands)",
    acceptance: str = "Counterpart acknowledges the ticket and returns a trace; no open ask remains.",
    state: str = "open",
    timing: str = "",
    note: str = "",
) -> str:
    """Render the standard envelope — compact and scannable.

    Readability rule (owner, 2026-11-01): the reader must get what changed and what
    is needed from the first four lines. Boilerplate is one line, not a block.
    """
    agreement = ("Watcher = doctor/teacher · ChatGPT = patient/second investigator · "
                 "Ahmed = approver. Evidence-tagged.")
    timing_line = f"**TIMING** this loop took {timing}.\n" if timing else ""
    return f"""## T{ticket_id} · {subject}
**AGREEMENT** {agreement}
**ACK** {ack}
**TRACE** — my train of thought since the last comment:
```
{trace}
```
{timing_line}**ASK** {ask}
**OFFER** {offer}
**FINDING** {finding}
**REQUEST** name this ticket id back + send your trace, or state its acceptance criteria pass.
**STATE** {state} · owner {owner} · acceptance: {acceptance}{(" · " + note) if note else ""}
— Watcher · {now} · _AI agent (OpenHands) on behalf of the owner._
"""
