# SUPERSEDED — use SwarmChat instead

The hand-rolled bridge in this folder (`hub.py`, `envelope.py`, `loop.py`, the ticket format on
GitHub issue `madnessgate44-debug/brain#240`) is **superseded** as of 2026-11-06.

It was a bespoke agent-coordination layer: a GitHub issue as a "hub", a custom ticket envelope,
and a polling loop. `Pranjal2041/swarmchat` is the purpose-built, open-source version of the same
idea — a real chat server with channels, DMs, threads, files, notifications, a **blocking `wait`**
(idle agents cost no tokens), and a live phone-friendly viewer — in ~1,560 lines of
dependency-free Python.

- **New skill:** `watcher/skills/swarmchat-coordination/`
- **Research + SWOT:** `docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md`
- **Old skill (on its branch, never merged to main):** `watcher/skills/watcher-bridge/`

## What is kept

The **evidence discipline** survives: the handoff envelope (`ACK / TRACE / ASK / OFFER / FINDING /
STATE`), the single-ask rule, evidence-tagged findings, and the capability truth table. They now
travel over SwarmChat instead of GitHub-issue comments.

## What to do

- New coordination work uses `swarmchat-coordination`, not `loop.py`.
- `hub.py`/`envelope.py` stay in the tree only as history until the migration is confirmed; they
  are not the transport going forward.
- The `brain#240` issue may remain as a durable audit trail while SwarmChat carries the live chat
  (open question, see the research doc §8).

Nothing here is deleted; this note only marks the direction.
