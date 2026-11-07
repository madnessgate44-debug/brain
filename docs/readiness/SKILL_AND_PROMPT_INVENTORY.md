# SKILL_AND_PROMPT_INVENTORY — Phase 1 (2026-11-07)

Exact paths, the skill-router output, gaps, and conflicts. Base commit
`1a9cffb7d3834159aeedea2a202ec4fb13b9f02a`. Read-only.

## 1. Skill-router output (verbatim)

`python3 scripts/skills.py declaration "<task>"` → a "Skills considered" list with scores.

```
audit and research and engineering and QA and security and browser work for the readiness phase
  -> security (9); security_auditor (4); improve-agent-readiness (4); accessibility-audit (4);
     security-threat-model (4)

independent adversarial security audit of a pull request
  -> security (9); code-review-rubric (8); multi-session-pr-coordination (5); security_auditor (4);
     accessibility-audit (4)

product development research and revenue planning
  -> multi-session-pr-coordination (5); product_owner (4); research-brief (3); mainframe-planning (3);
     prd (2)
```

The router scores *keywords*, not installed files. `security`, `code-review-rubric`,
`accessibility-audit`, `security-threat-model`, `research-brief`, `prd` are OpenHands-platform skills,
not files in this repo.

## 2. Skills actually installed in the repo

| Path | Count | Kind |
|---|---|---|
| `.agents/skills/writing-for-agents/` | 1 | repo skill |
| `brain/company/skills/*.md` | 9 | company role skills |
| `watcher/skills/*` | 3 | watcher skills |

`brain/company/skills/`: architect.md, code_reviewer.md, customer_advocate.md, developer.md,
product_owner.md, qa_engineer.md, release_manager.md, security_auditor.md, ux_designer.md.
`watcher/skills/`: swarmchat-coordination, watcher-learning, watcher-reverse-engineering.

## 3. Prompts / operating instructions (exact files)

| File | Role | Lines of interest |
|---|---|---|
| `AGENTS.md` | entry point; mandates the Execution OS | 1-40 |
| `ENGINEERING_EXECUTION_OS.md` | controlling procedure; lifecycle; authority §9 | 116-131 |
| `WATCHER.md` | Watcher + Shadow charter; schedule §3; audit rules §5; credentials §14 | §0-§16 |
| `docs/WORKFLOW.md` | canonical ticket shape §2; agreement §0 | 8-16, 32-58 |
| `docs/LOOP.md` | owner merge grant §Owner grant; audit rule; keys; stop conditions | 5-20 |
| `docs/TICKETING_PROTOCOL.md` | the read-room → ticket → reply protocol (new, PR #294) | all |
| `docs/SESSION_LOOP_TASK.md` | the session loop task | all |
| `brain/company/roles.py` | ROLE_CATALOG (the nine company roles) | all |
| `shadow/RESPONSIBILITIES_AND_GAPS.md` | Shadow's self-declared gaps | all |

## 4. Gaps

| Gap | Evidence | Tag |
|---|---|---|
| No `browser-qa` skill file in brain | `find` over `brain/` and `.agents/` | `[V]` |
| `accessibility-audit` named by the router but not installed as a file | router output vs `ls .agents/skills` | `[V]` |
| No `revenue` / `product-development` skill file; only the `product_owner` role skill | `ls brain/company/skills` | `[V]` |
| No skill-router invocation recorded in any workflow (the router is manual) | grep for `skills.py` in `.github/workflows/` → none | `[V]` |
| Brain's deterministic document worker has no web-research skill | Owner directive; re-verify in Phase 2 | `[U]` |

## 5. Conflicts (see BLOCKER_REGISTER.md)

C1 — `docs/WORKFLOW.md:8-16` calls ChatGPT the "patient/second investigator"; the directive makes it
the product architect.
C2 — `docs/LOOP.md:6` grants Shadow the merge right; the directive makes Shadow the reviewer.
C3 — `ENGINEERING_EXECUTION_OS.md:118` is read-only by default; the directive wants bounded repairs.
C4 — `WATCHER.md §14` has Shadow write keys; PR #293's Shadow run is BLOCKED for absent secrets.
C5 — the ticket tool `watcher/bridge/hub.py:17` points at issue **#240**; the live channel is **#292**.

_Phase 1 deliverable 2 of 4. Read-only._
