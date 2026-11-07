# Shadow audit — Claude-Code parity program (PR #272)

Auditor: OpenHands agent (Shadow role), on behalf of the owner.
Scope: PR #272, `goal/claude-code-parity` → `main`.
Rule applied: `docs/LOOP.md`. This is a **goal** change, normally owner-only; the owner
explicitly authorised it this session: *"merge all and push all that you did not merge yet."*

## What the PR adds

The "make Brain's agents Claude-Code-class" program, in four parts:

| Area | Files |
|---|---|
| Role skills | `brain/company/skills/{architect,code_reviewer,customer_advocate,developer,product_owner,qa_engineer,release_manager,security_auditor,ux_designer}.md` |
| Session/loop runtime | `brain/company/session.py`, `openhands_role.py`, `hooks.py`; edits to `agent_runner.py`, `engine.py`, `openhands_developer.py` |
| Tooling | `scripts/{skills,skill_check,sessions_index,agent_status,start_session_loop,install-pool-secrets}.sh|py`; `watcher/knowledge/tools/{discover,friction,learn,learning_report,purpose_audit,reverse}.py`; `shadow/report.py` |
| Workflows | `.github/workflows/{session-agent-loop,shadow-audit,shadow-report}.yml` |
| Docs + tests | `docs/GOAL_CLAUDE_CODE_PARITY.md`, `docs/CLAUDE_CODE_PARITY_STATUS.md`, `docs/SHARED_GPT_TOOL.md`, `docs/SESSION_LOOP_TASK.md`; 14 new `tests/test_*.py`; 20 session logs |

## Changes made during this merge (not in the original branch)

1. **Merged `main` (e1ae43b) into the branch.** 9 conflicts, all resolved by taking `main`'s
   side (main is newer and authoritative): `.openhands/memory/*`, `docs/sessions/*`,
   `tests/test_transcribe_helpers.py`, and `watcher/knowledge/tools/transcribe.py`. For
   `transcribe.py` main already carries the newer "skip an unfetchable source honestly"
   behaviour, which supersedes the branch's raise-on-probe-failure.
2. **Made `tests/test_skills_router.py::test_router_matches_a_migration` hermetic.** It passed
   only on a machine whose skill cache held a migration skill; in CI (repo-only skills, none
   named migration) it failed. The test now injects the skill instead of depending on the cache.
   This was the single red check on the branch's original head `5aac018`.

## Checks

- **CI on head `acd37ec`:** 8/8 success — `tests (3.12)`, `tests (3.13)`, `python-tests`,
  `chromium-smoke`, `audit`, `Check execution policy files` ×2, `Vercel Preview Comments`.
- **Full suite locally (with `openhands-sdk==1.54.0`):** `449 passed, 2 skipped`.
- **Additive:** the new workflows never push `main`; `session-agent-loop.yml` records a dry run
  instead of failing when `OPENHANDS_API_KEY` is absent, and `shadow-audit.yml` /
  `shadow-report.yml` post verdicts and open PRs. No secrets are printed or committed.
- **No spend:** no paid service is added; the work is skills, local scripts, tests and docs.

## Verdict

**Verified.** Merge as a merge commit (the repo's established style), on the owner's explicit
instruction. Flagged: this is a goal-level change, so if the owner wants it reverted, revert the
merge commit rather than the individual files.
