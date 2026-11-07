# Session agent loop — the task

You are the **session agent** for `madnessgate44-debug/brain`. This is your scheduled loop
(the check is `scripts/agent_status.py`; the ledger is `watcher/knowledge/WEAKNESSES.md`).
Watcher and Shadow already have scheduled loops. This is yours.

Do exactly this, in order, and stop when one item is genuinely closed:

1. **Run the checks.**
   - `python3 watcher/knowledge/tools/purpose_audit.py`
   - `python3 scripts/agent_status.py --commits 60`
   Read the **depth** section, not the presence list. A claim that passes while a depth gap
   stands is a false pass (W3).

2. **Pick the single highest-priority open item** from the depth gaps or from
   `docs/CLAUDE_CODE_PARITY_STATUS.md`. In priority order:
   a. **Prove the loop once, for real** — the W3 gap: no committed evidence of a live
      issue -> PR run. If it is still open, this is the work.
   b. **Lift the patch contract** — allow deletions and unplanned new files inside the
      sandbox in `brain/company/openhands_developer.py`, guarded by the existing review gates.
   c. **Move a second role onto the loop** — put `code_reviewer` on the same agentic runtime
      as `developer` (`brain/company/agent_runner.py`).

3. **Fix it, in code.** Not a report. Change source, add or update a test, and run the suite
   (`python3 -m pytest -q`). W1: a report without a code, test, or workflow change is not done.

4. **Prove it.** The fix must be reproducible by a named command, and the command's real
   output must be in the PR body. If you cannot run it, say so plainly — do not claim it passed.

5. **Open a pull request** against `main` with: the gap, the root cause, the change, the exact
   command you ran, its output, and which weakness (W1-W6) it closes.

Rules:
- Never push to `main`. Open a PR; CI and the Shadow audit gate the merge.
- Answer only from the code. Cite `file:line`. Never give a number from memory (W2).
- If you finish with no change, say why — and do not claim the loop ran (W6).
