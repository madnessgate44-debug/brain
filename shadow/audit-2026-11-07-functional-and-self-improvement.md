# Audit — functional behaviour and self-improvement, 2026-11-07

Auditor: session agent (OpenHands), on owner instruction "run a complete audit on brain …
how the app is functioning and is it fit in its purpose or not and how is it improving itself".
Scope: **behaviour and self-improvement**, not code style. Code metrics are included only where
they bear on those two questions.

Method: run the app, exercise every endpoint, run the repo's own audit tools, read the CI and
cron history from the GitHub API, and compare what the repo *claims* about itself against what
the running system does.

Truth time: **2026-11-07T15:36Z** (GitHub `Date` header).

---

## 1. Verdict in two lines

- **Purpose fit — mostly honest, deliberately narrow.** Every capability the README says is
  live works when exercised [V]; the README's "planned, not yet implemented" list is accurate,
  and the worker explicitly refuses to claim work it did not do [V]. The gap is that the
  headline purpose ("operate a coding agent from a phone") is *not* reachable: there is no
  served UI, and the browser worker — the phone bridge — needs an optional dependency that is
  not installed [V].
- **Self-improvement — the machinery is real and runs; the outcomes it promises are not met.**
  A purpose audit, an agent-status check, a weakness ledger, a daily learning loop and per-PR
  Shadow audits all exist and execute [V]. But the ledger's own closure criteria are mostly
  still open: report-only commits have *not* fallen, two "scheduled" loops have never run, and
  the learning loop failed four days straight before recovering [V].

---

## 2. Does the app function? (exercised, not read)

Local server: `uvicorn brain.api.app:create_app --factory --port 8123`, isolated DB/workspace
under `/tmp/auditws`. Production: `https://brain-one-pi.vercel.app`.

| # | Capability | How tested | Result |
|---|---|---|---|
| F1 | Health + DB connect | `GET /health` (local + prod) | **PASS** — `database_connected:true` [V] |
| F2 | Mission lifecycle E2E | `POST /missions` → `POST /missions/{id}/start` → `GET` | **PASS** — INTAKE→EXECUTE→**COMPLETE** [V] |
| F3 | Execution-to-artifact | read artifact on disk | **PASS** — `mission-brief.md` written, non-empty, honest wording [V] |
| F4 | Event history | `GET /missions/{id}/events` | **PASS** — 5 events: created, started, worker_started, artifact_created, phase_changed [V] |
| F5 | Control-key auth | no key / bad key / good key | **PASS** — 401 / 401 / 200 on prod and local [V] |
| F6 | `/chat` with a real model | `POST /chat` (gemini-2.5-flash) | **PASS** — returned `BRAIN_CHAT_OK` [V] |
| F7 | Connector + MCP mount | `GET /connector`, `POST /mcp` | **PASS** — `/connector` 200 (`mcp_path:/mcp`); `/mcp` 401 without key [V] |
| F8 | Company workflow | `POST /company-workflows` with no GitHub token | **PASS (honest fail)** — mission FAILED with `GitHubGatewayError` + `failure-diagnostic.json`, no false success [V] |
| F9 | Browser worker | import playwright | **NOT RUN / UNKNOWN** — `playwright` not installed in this env [V] |
| F10 | Phone UI | search for a served HTML route | **ABSENT** — `brain-app.html`, `brain-ui-mobile.html` exist at repo root but nothing serves them [V] |

**Reading:** the backend is a genuine, tested mission orchestrator. The worker is deliberately
deterministic and says so. The honest-failure path (F8) is the single best signal in the repo:
the system refuses to report success it did not achieve.

### Purpose audit (the repo's own tool)

`python3 watcher/knowledge/tools/purpose_audit.py` → **12/12 claims OK** [V]. But the tool's
own depth section is the honest one:

- `[x]` agentic loop covers 9/9 roles
- `[~]` **patch contract bounds what the agent may change — PARTIAL** (30 files, 200 bytes/file,
  deletions forbidden)
- `[~]` **developer works in a temporary workspace, not the repo checkout — PARTIAL**
- `[x]` committed evidence of a live issue→PR run
- `[x]` 9/9 roles have a skill file; skill router exists; 7/7 Watcher tools scheduled

So the app *does what its own purpose file claims*, and the tool correctly distinguishes
"present" from "deep". The two PARTIALs are the same two the ledger has carried since 2026-11-03
(W3) — unchanged.

---

## 3. Is it improving itself?

### 3.1 What is real [V]

- `scripts/agent_status.py` — reports the three agents, their loops, and the report-only ratio.
- `watcher/knowledge/tools/purpose_audit.py` — claims vs code, with a depth section.
- `scripts/skill_check.py` — **PASS**: "skill check required by the OS; all 9 roles have a skill file".
- `watcher/knowledge/WEAKNESSES.md` — W1–W7, each with a check.
- Daily loops actually run: `watcher-daily` (7 runs), `watcher-session-log` (7), `shadow-keys`
  (18), `shadow-audit` (50), `watcher-learning` (10) — all `schedule`-triggered [V].
- Per-PR Shadow audits: 9 audit files in `shadow/`, 481-line audit log [V].

This is not theatre. There is a real improvement apparatus, and it fires on a schedule.

### 3.2 Where it is not improving (the honest part)

**S1 — Two "scheduled" loops have never run — but this is not yet a defect.**
`Session agent loop` and `Shadow report and sweep` are `active` in the API yet have **0 runs
ever** [V]. Cause found: both only reached `main` **today**, in the #272 merge at ~15:14Z
(workflow registration timestamps `2026-11-07T15:14Z`; first-parent history shows the file first
appears in `b67f28c`) [V]. Their first cron is not due yet (session-agent-loop: 05:00Z daily;
shadow-report: 07:00Z/19:00Z/`5 * * * *`). **Correction to a prior claim:** the ledger's W4
entry says all three loops are scheduled and running; in fact two of the three had never run as
of this audit. The distinction matters — "registered" ≠ "proven to run".

**S2 — The learning loop failed four days straight, then recovered.**
`watcher-learning` runs: 11-03 fail, 11-04 fail, 11-05 fail, 11-06 fail, **11-07 success** [V].
Failed step is always `Transcribe (captions, else local ASR)`. The loop that is supposed to
*learn for* the owner produced nothing for four days and nobody was told.

**S3 — W1 "report instead of build" has not fallen.**
`agent_status.py`: report-only **34%** over 58 commits, **29%** over 174 [V]; independent
7-day count **35% (47/133)** [V]. The ledger's own "done when" is "below 25%". The ratio has not
crossed it; the ledger still says W1 is open. The check is honest; the number is not improving.

**S4 — The improvement is measured by presence, not outcome.**
`purpose_audit` is a regex presence check over `brain/`; it reports OK when a symbol exists,
which is exactly weakness W3 ("we mistake presence for depth"). The depth section is a manual
addendum, not a gate. Nothing fails when depth regresses.

**S5 — Code drift is unmanaged.**
Configured but never gated by CI [V]:
- ruff: **96 errors** (68 unused imports, 13 star-imports, 6 ambiguous names, …)
- mypy `strict`: **173 errors in 43 files**
- black: **152 files would be reformatted**
`brain-ci.yml` runs only `pytest -q`; no workflow invokes ruff/mypy/black [V]. So the configured
standard drifts freely and every future reader pays for it.

**S6 — Dead and stale surfaces.**
- `.github/workflows/agent-zero-company-worker.yml` and `agent-zero-runtime-smoke.yml` are on
  `main` but trigger only on a branch pattern / manual dispatch that cannot fire [V].
- **76** doc references point at files that do not exist (`docs/BACKLOG.md`, `docs/STATUS.md`
  — which the self-driving-loop skill *requires* — plus many cross-repo names) [V].
- No lockfile; `requirements.txt` and `pyproject.toml` duplicate the dependency list by hand [V].
- 379 branches; 8 merges vs 133 commits in the last 7 days; 179 PRs lifetime, 0 open [V].

**S7 — Purpose vs. the phone.**
The stated mission is to operate the agent **from a phone**. Today: no served UI (F10), and the
browser worker (the intended phone bridge) is unverified here (F9) and flagged "not yet
verified" in the README itself. The README is honest about this; the gap is real and unmet.

---

## 4. Requirement-by-requirement

| R | Criterion | Result |
|---|---|---|
| R1 | App runs and serves the documented API | **PASS** [V] — 15 paths on prod; 10 local routes exercised |
| R2 | Core mission path produces a real artifact | **PASS** [V] — F2–F4 |
| R3 | Auth protects every mutating route | **PASS** [V] — F5, F7 |
| R4 | The app does not over-claim | **PASS** [V] — F8, README's "planned" list, honest worker wording |
| R5 | Fits the stated purpose (phone-operable coding agent) | **PARTIAL** — no UI (F10); browser worker unverified (F9) |
| R6 | Self-improvement loop runs unattended | **PASS** [V] — 6 scheduled workflows with real run history |
| R7 | Self-improvement produces measurable improvement | **PARTIAL/FAIL** — S1–S3: ratio not falling, 4-day silent learning outage |
| R8 | Improvement is measured by outcome, not presence | **FAIL** — S4 |
| R9 | Code standard is enforced | **FAIL** — S5 |
| R10 | Repo surface is coherent (no dead/stale references) | **FAIL** — S6 |
| R11 | No secrets in the tree | **PASS** [V] — sweep clean; no `.env`; only `*.example` |
| R12 | Tests pass | **PASS** [V] — 457 passed, 2 skipped, 76% coverage |

---

## 5. Verification ledger

| # | Command / action | Exit | Verdict | Evidence excerpt |
|---|---|---|---|---|
| L1 | `python3 watcher/knowledge/tools/purpose_audit.py` | 0 | PASS | `checked 12 ok 12`; depth: 2 PARTIAL |
| L2 | `python3 scripts/agent_status.py --commits 60` | 0 | PASS | `[x] watcher/shadow/session`; `Report-only 20/58 (34%)` |
| L3 | `python3 scripts/skill_check.py` | 0 | PASS | `OK - skill check required by the OS; all 9 roles have a skill file` |
| L4 | local mission lifecycle (curl script) | 0 | PASS | `phase COMPLETE status COMPLETED`; 5 events; `mission-brief.md` on disk |
| L5 | `POST /chat` (gemini-2.5-flash) | 0 | PASS | `{"reply":"BRAIN_CHAT_OK","model":"gemini-2.5-flash"}` |
| L6 | prod auth probes | 0 | PASS | `/missions` 401, `/mcp` 401, `/health` 200, `/connector` 200 |
| L7 | `POST /company-workflows` (no token) | 0 | PASS | `phase FAILED error Runtime failed: BRAIN_GITHUB_TOKEN is not configured.` |
| L8 | `python3 -m ruff check .` | 0 | FAIL(std) | `Found 96 errors` |
| L9 | `python3 -m mypy brain` | 0 | FAIL(std) | `Found 173 errors in 43 files` |
| L10 | `python3 -m black --check .` | 1 | FAIL(std) | `152 files would be reformatted` |
| L11 | `pytest -q --cov=brain` | 0 | PASS | `457 passed, 2 skipped`; `TOTAL 4116 1006 76%` |
| L12 | GitHub Actions runs (schedule) | 0 | PASS | watcher-learning: fail×4 then success 11-07 |
| L13 | workflow run history for the two new loops | 0 | PASS | `total 0` for `session-agent-loop`, `shadow-report` |
| L14 | workflow registration timestamps | 0 | PASS | both `created 2026-11-07T10:14-05:00` (= 15:14Z) |
| L15 | secret shape sweep (`git grep -nE`) | 1 | PASS | no matches at real key lengths |
| L16 | main CI check-runs (`1a9cffb`) | 0 | PASS | 7/7 `success` |
| L17 | Vercel deployments (project `brain`) | 0 | PASS | 6 most recent all `READY` |

---

## 6. Ranked fixes (smallest complete change first)

1. **Make the improvement outcome a gate (S4).** Turn `purpose_audit`'s depth section into a
   CI job that fails on a regression, and have `agent_status.py` fail when the report-only ratio
   rises above its target. This is the structural fix the ledger itself calls for.
2. **Gate the code standard (S5).** Add `ruff check`, `mypy`, `black --check` to `brain-ci.yml`
   (advisory first, then blocking), and clear the 96/173/152 backlog in one sweep.
3. **Report the learning-loop failure (S2).** The four-day silent outage is a missing alert; a
   failed scheduled run should open an issue. Add a lockfile (S6).
4. **Serve the UI (S7).** Route the existing `brain-ui-mobile.html` from the app so the phone
   purpose is reachable; verify the browser worker on a real host (F9).
5. **Retire dead surfaces (S6).** Delete the two non-firing agent-zero workflows; fix or
   archive the 76 stale doc references.

---

## 7. What was not done / limits

- Browser worker not exercised (dependency absent). [UNKNOWN]
- No live `POST /company-workflows` success path (needs a GitHub token + model key) — only the
  honest-failure path was proven. [UNKNOWN]
- Coverage measured on `brain/` only; `scripts/`, `watcher/`, `shadow/` are untested by CI.
- This audit changes no product code; it is a report plus the two audit tools' output.

---

## 8. COMPLIANCE HEADER

```text
TOOL DECLARATION
- Tools confirmed available this session: terminal (bash), file_editor, browser tools (unused),
  tavily (unused), GITHUB_TOKEN via curl, VERCEL_TOKEN via curl, GEMINI_POOL_1 via curl.
- Skills considered: owner-policy, engineering-execution-os, code-review-rubric,
  security-threat-model, dependency-supply-chain, testing-strategy, secret-redaction-scan,
  observability, scope-discipline, owner-brief, self-driving-loop, architecture-and-adr,
  performance-engineering, incident-response, evidence-based-citations. Router (repo):
  security, ci-cd-pipelines, secret-redaction-scan, security_auditor, zero-cost-gate.
- Tools requested but absent: playwright (browser worker), bandit/pip-audit (not installed).
- No other access claimed.

COMPLIANCE HEADER
- Outcome claimed: COMPLETED — behavioural + self-improvement audit; 12 requirements scored.
- Tools confirmed this session: terminal, file_editor, GitHub API, Vercel API.
- Tools absent / not claimed: playwright, bandit, pip-audit.
- Evidence refs: L1–L17 above; files shadow/audit-2026-11-07-functional-and-self-improvement.md,
  watcher/knowledge/audits/purpose-20261107.md.
- Requirements: R1 PASS | R2 PASS | R3 PASS | R4 PASS | R5 PARTIAL | R6 PASS |
  R7 PARTIAL/FAIL | R8 FAIL | R9 FAIL | R10 FAIL | R11 PASS | R12 PASS
- Checks run (Verification Ledger): see §5 (17 entries, each with command, exit code, verdict, excerpt).
- Changed files: this report + watcher/knowledge/audits/purpose-20261107.md (diff inspected: Y).
- Regressions checked: none — no product code changed.
- Not attempted / out of scope: browser worker run; live company-workflow success path.
- Blockers / unknowns: browser worker UNKNOWN in this environment.
- Repo/PR/deploy state: main 1a9cffb; CI 7/7 green; prod READY (uptime ~232s at check).
- Unsupported claims removed: Y
- Claim tags applied inline in body: Y
```

— Session agent (OpenHands), on behalf of the owner. This report was created by an AI agent.
