# Watcher focus — what to research and learn (WATCHER.md §16)

The Watcher does not wait for the owner to supply videos. He derives what to watch from
the owner's line of work and the open problems below, searches for it, and learns. One
topic per line; comments start with `#`. `watcher/knowledge/tools/discover.py` turns these
into searches; the learning loop watches the results.

## The owner's line of work
Building a coding agent ("Forge") and a mission orchestrator ("brain") that a person can
operate from a phone, aiming for a Claude-Code-like experience.
free and open-source coding agents and how they are built
how Claude Code is architected: agent loop, tools, permissions, context management
how to give a coding agent arbitrary shell safely: sandboxes, allowlists, approvals
context retrieval for coding agents: repository maps and symbol graphs
agent skills, hooks, and lifecycle events
session persistence, checkpointing, and resume for coding agents
running parallel subagents and multi-agent coding teams
long-horizon autonomous coding agents that do not drift

## The open problems (from the owner's repos and chats)
why automated pull requests pile up and never get closed
building a reaper that retires superseded agent work and escalates the rest
making a deterministic coding agent fully cloud-operable with no local machine
measuring agent parity against Claude Code with evidence, not vibes
keeping an agent's own backlog and issues under control
teaching and transferring knowledge between agents (memory, lessons, docs)
