# Forge diagnosis — run 2026-11-01 (Firstborn @ 36a9916e900f9019ef1c46d95d08985c38fbac9d)

Read-only inspection. Every claim carries a file/line or run id.

## 1. Execution paths (CONFIRMED)
- **Default mission path:** `.github/workflows/forge.yml` (triggers: `issues: [labeled]` + `workflow_dispatch`)
  → step `Run Forge Agent` = `npx tsx src/agent/forge-runner.ts` (forge.yml:144)
  → `new ForgeAgent(token)` + `agent.executeTask(task)` (forge-runner.ts:23,36)
  → deterministic staged pipeline in `src/agent/forge.ts` (1115 lines), which DOES call the model at
  `this.model.generatePlanAndPatch(...)` (forge.ts:618, retries :627, repair :683/:719).
- **Loop path (separate):** `.github/workflows/forge-loop.yml` (trigger: `workflow_dispatch` ONLY)
  → `npx tsx src/agent/loop-runner.ts` (forge-loop.yml:51) → `runAgentLoop(...)` (loop-runner.ts:87).
- **The default path never imports or calls the loop runner.** (grep: no `loop-runner`/`runAgentLoop`
  reference in forge.ts / forge-runner.ts.)

## 2. Symptom verdicts
| # | symptom | verdict | evidence |
|---|---|---|---|
| 1 | no complete demonstrated mission | **DISPROVED (once)** | run `39758340323` → taskId `131`, status `PR_OPENED`, PR #133, evidence artifact `12417705780` |
| 2 | loop not used by default path | **CONFIRMED** | §1 call graph |
| 3 | completion claims lack evidence | **CONFIRMED** | recurring F-A; bot "complete" comments with no run id |
| 4 | browser unclear | **CONFIRMED GAP** | no browser refs in forge.ts / forge-runner.ts; tools exist only in `tools.ts` gated by `allowBrowser` (loop-runner.ts:74) |
| 5 | boundaries unclear | **PARTIAL** | cross-repo token guard exists (forge.yml step 7) and is enforced |
| 6 | durable execution/recovery unproven | **CONFIRMED GAP** | `server.ts:21` in-memory `reportsStore`; `GET /api/tasks/:id` reads only the Map (server.ts:143); disk JSON written (:128) but never read back |
| 7 | coordination/context | **CONFIRMED** | F-H |
| 8 | 10 vs 11 commands | **RESOLVED: 10** | `src/services/test-runner.ts` |
| 9 | E2E proof required | **PARTIAL** | one exists (2026-10-22, PR #133 open/unmerged); not repeatable on current main |
| 10 | zero-cost | **PARTIAL** | keyless freelm primary; Gemini fallback gated by `FIRSTBORN_KEYLESS_ONLY` (model.ts:149,166) — but run 131 shows a real `google/gemini-3.5-flash` call |

## 3. The one real mission (CONFIRMED)
- Run `39758340323`, 2026-10-22T09:49Z, event `issues`, conclusion `success`.
- Evidence artifact `forge-evidence` (id `12417705780`, 17282 B) contains `131.json`:
  - `status: PR_OPENED`, `baseCommitSha 5e1e584c…`, `branch forge/task-131-39758340323`,
    `headCommitSha 060965a3…`, `prUrl https://github.com/madnessgate44-debug/Firstborn/pull/133`
  - `modelInvoked`: `provider google`, `model gemini-3.5-flash`, `callsCount 1`, `fallbackUsed false`,
    `keylessRouteErrors`: groq 413 (TPM 8000 < 10121), google gemini-3.7-flash 503.
  - `requirements`: REQ-1 `PASS` (npm run lint=0) …
  - `testResults`: `npm install` exit 0, `npm run lint` exit 0.
- PR #133 exists, state `open`, `merged: false`, head `forge/task-131-39758340323`, author `github-actions[bot]`.

## 4. Why recent runs fail (CONFIRMED root cause)
- Runs 2026-10-25/26 all `failure` at **step 7 "Verify cross-repository write access before running Forge"**
  (job `run-forge`); `run-readonly-audit` skipped. The agent step never executes.
- Log: `::error::BLOCKED before writes: cross-repository mission requires FORGE_CROSS_REPO_TOKEN or
  FORGE_DELIVER_TOKEN with verified target-repository push access.`
- So the default path is gated shut by a credential/boundary check, not by a code defect.

## 5. Loop path (CONFIRMED)
- `forge-loop.yml` ran only twice (2026-10-13, both `success`), both `workflow_dispatch`.
- Browser tools are ON by default in the loop (`allowBrowser = process.env.FORGE_ALLOW_BROWSER !== 'false'`,
  loop-runner.ts:74) and `browser_close` is released in a `finally` (loop-runner.ts:~100).
- Browser viewport is single 1280x800 (`src/services/browser.ts:74`); no mobile viewport.

## 6. Most consequential unresolved question
Is `FIRSTBORN_KEYLESS_ONLY=true` set for the default workflow? Run 131 made a real
`google/gemini-3.5-flash` call. If keyless-only is not enforced, the default path can bill Gemini —
a direct breach of symptom 10. (Cannot read secret/env values; must verify from workflow config.)

## 7. Next diagnostic actions
1. Verify `FIRSTBORN_KEYLESS_ONLY` in `.github/workflows/forge.yml` env (read-only).
2. Prove a real browser action with observable output (loop path, non-billable if keyless).
3. Determine what the cross-repo guard needs to pass for a fresh E2E mission on current main.

## 8. Browser capability — PROVEN (loop path), real Chromium
`CHROMIUM_PATH=/usr/bin/chromium npx tsx --test tests/browser-capability-matrix.test.ts` → 10/10 pass, 0 fail.
Real Chromium (`/usr/bin/chromium`), local HTTP fixture, no model, no cost. Passes include form submit via
browser_type+Enter, scroll (real wheel), navigation, extract, close/reopen. Absent from the default path.

## 9. Durable state — server DISPROVEN, CI PROVEN
- server.ts:21 `reportsStore = new Map()`; :122 set; :143 `GET /api/tasks/:id` reads only the Map → 404
  after restart (disk JSON at :126-131 is written but never read back).
- CI: artifact `12417705780` (forge-evidence) is retrievable → durable.

## 10. Cost gate (open question to ChatGPT/owner)
forge.yml:134-140 removed `FIRSTBORN_KEYLESS_ONLY=true` for coding and passes GROQ_API_KEY+GEMINI_API_KEY.
limits.ts bounds volume (maxModelCalls 8/50, modelAttempts 2, maxRepairAttempts 2, maxRuntimeMs 10min)
but sets no cost ceiling. isConfigured() returns true unconditionally (model.ts:153).
