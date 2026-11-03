# Weaknesses we keep repeating — Shadow, Watcher, and the session agent

Written 2026-11-03 from the actual record — the commit history, all three agents' own
self-audits, and the owner's corrections. **Three agents, not two.** The first version of this
file covered Shadow and Watcher and left out the session agent (OpenHands, commits authored
`openhands`). That omission was itself W2 — answering from memory instead of the record.

Each weakness has evidence, the agent(s) it belongs to, a closure, and the check that proves it
closed. A weakness stays until its check passes.

## The three agents and their loops

| Agent | How it runs | Scheduled? | Evidence |
|---|---|---|---|
| **Watcher** | `watcher/knowledge/tools/*`, daily learning loop | **Yes** — `watcher-daily.yml`, `watcher-learning.yml`, `watcher-session-log.yml` | workflow inventory |
| **Shadow** | `shadow/shadow.py`, audits each PR + key sweep | **Yes** — `shadow-audit.yml`, `shadow-keys.yml`, `shadow-report.yml` | workflow inventory |
| **Session agent (me)** | the OpenHands session; commits authored `openhands` | **Yes** — `session-agent-loop.yml` (added 2026-11-03) starts a Cloud conversation on a schedule | 29 commits; `scripts/start_session_loop.py` |

All three now have a scheduled loop. The session agent's was added 2026-11-03 (`session-agent-loop.yml` +
`scripts/start_session_loop.py`); before that, two agents had a loop and the third did not. See W4.

## W1 — We report instead of build
- **Evidence:** of the last 29 file-changing commits, **10 are `.md`-only** (report-only).
  Watcher's self-audit: *"Eight point-fixes and one delivery... the loop... was never run."*
  The Section 7 reverse-engineering "Core job" shipped a **30-byte placeholder README**.
- **Belongs to:** all three. The session agent wrote most of the `.md`-only commits.
- **Closure:** every report carries a code, test, or workflow change, or says plainly why not.
- **Check:** the report-only ratio (`scripts/agent_status.py`), which must fall.

## W2 — We answer from memory, not from the code
- **Evidence:** "how close are we to Claude Code" was answered **without reading the code**
  (owner, 2026-11-02). The first purpose audit said **12/12 OK** while every defect stood. This
  very file's first version answered "two agents" from memory — there are three.
- **Belongs to:** all three.
- **Closure:** every claim cites `file:line` or a command; the audit reports depth, not presence.
- **Check:** `watcher/knowledge/tools/purpose_audit.py` depth section; a claim without evidence
  is rejected.

## W3 — We mistake presence for depth
- **Evidence:** the loop exists — but covers **1 of 9 roles**; the patch contract **forbids
  deletions** and unplanned files; the agent edits a **temp dir, not the repo**; no live run is
  committed. Shadow's gaps G1-G7 are the same shape.
- **Belongs to:** all three.
- **Closure:** audits answer "does it cover the whole app, and is it proven to run?".
- **Check:** the depth section of `purpose_audit.py`.

## W4 — The loop is never scheduled, so it does not run
- **Evidence:** Shadow G1 — *"Nothing invokes `shadow.py` on a schedule."* Watcher's cycle steps
  4.2-4.4 were **MISSING**. The session agent had no loop at all — no workflow ran it; the owner
  had to open a session by hand.
- **Belongs to:** Shadow, Watcher, and the session agent.
- **Closure:** every capability has a scheduled workflow that runs it unattended.
- **Check:** `scripts/agent_status.py` — it names any agent with zero scheduled workflows, and
  fails if an agent that should be scheduled loses its loop.
- **Status: CLOSED for all three (2026-11-03).** Watcher (`watcher-learning.yml`), Shadow
  (`shadow-audit.yml`), and the session agent (`session-agent-loop.yml`) all have a cron loop.
  `scripts/agent_status.py` reports `[x]` for all three and exits 0. Re-opens if any loses its
  schedule.

## W5 — We self-diagnose accurately, then do not close
- **Evidence:** Shadow's `RESPONSIBILITIES_AND_GAPS.md` names G1-G7 precisely; they are still
  open. Watcher's self-audit is accurate; the loop it named was still not run.
- **Belongs to:** all three.
- **Closure:** each gap gets a check that fails until it is closed — not a paragraph.
- **Check:** this file. A weakness is removed only when its check passes.

## W6 — We claim capability broader than what is wired
- **Evidence:** "the watcher reads Shadow's conversations" — he does not (G6). The
  reverse-engineering "Core job" was claimed done with a placeholder. This file first claimed to
  cover "Watcher + Shadow" while the third agent was the one doing the writing.
- **Belongs to:** all three.
- **Closure:** describe only what a command proves; label the rest "planned".
- **Check:** every capability statement must be reproducible by a named command.

## The single root cause
All six are one habit, shared by all three agents: **we optimise for what is easy to prove** —
a green check, a written report, a confident number — **and avoid the harder, open-ended work**
(run the loop, read the code, prove it end to end). The fix is structural: make the hard thing
the thing that is checked.

## What is already checked
- `purpose_audit.py` reports **depth** (loop coverage, patch contract, temp-dir, live proof, and
  unscheduled tools), so W2/W3 are measured, not asserted.
- `scripts/agent_status.py` reports the three agents, their loops, and the report-only ratio, so
  W1/W4 are measured. W4 is closed (all three scheduled) and the check now fails on regression.
- `session-agent-loop.yml` + `scripts/start_session_loop.py` give the session agent a loop, so
  its improvement no longer depends on the owner opening a session.
- This ledger makes W1-W6 checkable instead of forgotten.
