# Weaknesses we keep repeating (Watcher + Shadow)

Written 2026-11-03, from the actual record — the commit history, both agents' own self-audits,
and the owner's corrections — not from memory. Each weakness has evidence, an owner, a closure,
and the check that proves it closed.

This file is the answer to "look at our history together, you see the weaknesses we have".
It is meant to be uncomfortable. A weakness stays here until its check passes.

## W1 — We report instead of build
- **Evidence:** of the last 29 commits that change files, **10 are `.md`-only** (report-only).
  Watcher's own self-audit (`watcher/self/audit-2026-11-01.md`): *"Eight point-fixes and one
  delivery... None of it is the loop... the loop that is supposed to improve Forge was never
  run."* The Section 7 reverse-engineering "Core job" produced a **30-byte placeholder README**.
- **Why it recurs:** a report is cheap and looks like progress; a working loop has no finish line.
- **Owner:** Watcher.
- **Closure:** every report must carry a code, test, or workflow change, or say plainly why not.
- **Check:** the report-only ratio; it must fall, and the reverse-engineering tool must produce a
  real finding (`watcher/knowledge/tools/reverse.py`, now built).

## W2 — We answer from memory, not from the code
- **Evidence:** "how close are we to Claude Code" was answered **without reading the code**
  (owner's correction, 2026-11-02). The first purpose audit said **12/12 OK** while every real
  defect stood — because it checked presence, not depth.
- **Why it recurs:** reading the code is slow; a remembered answer feels confident.
- **Owner:** both.
- **Closure:** every parity number cites `file:line`; the audit reports depth, not presence.
- **Check:** `watcher/knowledge/tools/purpose_audit.py` (depth section) +
  `docs/CLAUDE_CODE_PARITY_STATUS.md`. A claim with no file:line is rejected.

## W3 — We mistake presence for depth
- **Evidence:** the loop exists — but covers **1 of 9 roles**; the patch contract **forbids
  deletions** and unplanned files; the agent edits a **temp dir, not the repo**; no live run is
  committed. Shadow's gaps G1-G7 are the same shape: the parts exist, the wiring does not.
- **Why it recurs:** "the feature exists" is easy to prove and easy to accept.
- **Owner:** both.
- **Closure:** audits must answer "does it cover the whole app, and is it proven to run?".
- **Check:** the depth section of `purpose_audit.py` — it now derives these gaps from the code.

## W4 — The loop is never scheduled, so it does not run
- **Evidence:** Shadow G1 — *"Nothing invokes `shadow.py` on a schedule."* Watcher's daily cycle
  steps 4.2 (sources), 4.3 (research), 4.4 (transcribe) were all **MISSING**. Both agents are
  capable; neither was running.
- **Why it recurs:** capability is built, then left to a human to trigger.
- **Owner:** Shadow (for Shadow), Watcher (for Watcher).
- **Closure:** every capability has a scheduled workflow that runs it unattended.
- **Check:** `grep` `.github/workflows/` for the tool; none found is the failure.

## W5 — We self-diagnose accurately, then do not close
- **Evidence:** Shadow's `RESPONSIBILITIES_AND_GAPS.md` names G1-G7 precisely and lists "smallest
  path to close"; those items are still open. Watcher's self-audit is accurate; the loop it names
  was still not run at the time.
- **Why it recurs:** writing the diagnosis feels like the work; the closing is harder.
- **Owner:** both.
- **Closure:** each gap gets a check that fails until it is closed — not just a paragraph.
- **Check:** this file. A weakness is removed only when its check passes.

## W6 — We claim capability broader than what is wired
- **Evidence:** the watcher is said to read Shadow's conversations; he does not (G6 — no process
  watches PRs/comments/pushes across repos). The reverse-engineering "Core job" was claimed done
  with a placeholder file.
- **Why it recurs:** the intended design is described as the current state.
- **Owner:** both.
- **Closure:** describe only what a command proves; label the rest "planned".
- **Check:** every capability statement in a report must be reproducible by a named command.

## The single root cause
All six are one habit: **we optimise for what is easy to prove** — a green check, a written
report, a confident number — **and avoid the harder, open-ended work** (run the loop, read the
code, prove it end to end). The fix is structural, not motivational: make the hard thing the
thing that is checked.

## What we changed so far
- `purpose_audit.py` now reports **depth** (loop coverage, patch contract, temp-dir, live proof),
  so W2/W3 are checked, not asserted.
- `reverse.py` exists and produces real findings, so W1's reverse-engineering claim is real.
- This ledger makes W4/W5/W6 visible and checkable instead of forgotten.
