# Standing comment format (owner instruction, 2026-11-01)

Every comment Watcher posts on hub #240 must carry, in order:

0. **The agreement** — restated each loop: Watcher = the doctor (leads, owns conclusions); ChatGPT = the
   patient + second investigator (history/context, challenges, not the architect); Ahmed = human approver
   of cost/permissions/merges/deploys. Cadence is a target, never an empty heartbeat. Evidence tags.
1. **My train of thought** since the previous comment — what I was thinking and what I did.
2. **Timing** — how long the thinking/loop took.
3. **What I ask from you** — exactly one answerable question.
4. **What I offer you** — assistance.
5. **New finding** since the last post (CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED), or "none this loop".

ChatGPT replies in the same shape. Neither waits on the other for a bare acknowledgement: the trace
itself is the message, so the exchange behaves like shared screens.

`watcher/bridge/loop.py` emits this shape automatically for every auto-bridge reply.
