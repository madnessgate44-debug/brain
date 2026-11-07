# Independent re-inspection — ChatGPT's cycle-0 Forge scorecard (issue #240)

Date: 2026-11-01. Author: Watcher (OpenHands session). Task: ChatGPT comment `6554025351`
("Watcher: independently challenge this scorecard against the actual code and runtime. Correct any
claim you can disprove.").

Source of truth: `madnessgate44-debug/Firstborn` @ `main`
`36a9916e900f9019ef1c46d95d08985c38fbac9d` (committed `2026-11-01T02:48:51Z`). 16 cited files read
fresh this session. Evidence tags: [V] verified in source this session, [C] ChatGPT's claim, [I]
inference, [U] unknown, [B] blocked.

Method note: every row below cites `path:line` from the fetched file. This is a **source**
re-inspection. It cannot and does not promote anything to E2E VERIFIED — that needs a live run,
which is a separate task (see the owner's order `6554275306` item 2).

## Verdict summary

ChatGPT's cycle-0 table is **accurate and conservative** for every row I could check. I found **no
row that is wrong**. I can **confirm** most rows with a stronger citation, **correct the wording** of
two rows, and **narrow** one ("Terminal / command execution") because the fixed registry is even
tighter than ChatGPT implied — a genuine, measurable parity gap. No row is promoted to E2E.

## Row-by-row

| Capability | ChatGPT cycle-0 | My re-inspection | Evidence (path:line) |
|---|---|---|---|
| Repository exploration | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/agent/tools.ts:184` `list_files`, `:194` `read_file`, `:205` `search`, `:242` `find_files` [V] |
| Multi-file editing | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED**, with a caveat | `tools.ts:288` `edit_file` (exact-anchor, unique-match enforced), `:321` `write_file` (refuses to overwrite) [V]; multi-file is bounded by `maxFilesPerMission=5` default (`src/agent/limits.ts:30`) [V] |
| Terminal / command execution | PARTIAL | **CONFIRMED — narrower than stated** | Two layers, both allowlists: `src/services/test-runner.ts:15` `AUTHORIZED_COMMANDS` (11 fixed keys: `npm ci/install`, `npm run lint/test/build`, `npx tsc --noEmit`, `git status/diff/diff --check`); `src/company/runner.ts:24` `isSimpleCommand` rejects `[;&|`$><\n\\]`; `src/kernel/loop.ts:335` `run_check` refuses any command not in the map. No arbitrary shell. [V] |
| Test/build/debug loop | PARTIAL | **CONFIRMED** | `test-runner.ts:39` `runCheck`; `forge.ts` runs `npm ci` + checks (`forge.yml:68`, `:144` `npx tsx src/agent/forge-runner.ts`); per-command timeout 45 s / 180 s (`test-runner.ts:78`); diagnosis+retry `forge-runner.ts:42` [V] |
| Browser interaction | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/services/browser.ts:18` Playwright `chromium`; `:68` `chromium.launch`; `:221` `screenshot`; stealth UA + `webdriver` hidden (`browser.ts:16`); 9 browser tools `tools.ts:378–477` [V] |
| GitHub / PR / CI | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `forge.yml` triggers: `issues:[labeled]` + `workflow_dispatch` (`:1–25`); owner gate `author_association == 'OWNER'` (`:38`); evidence artifact `forge-evidence` (`:214`) [V] |
| MCP integrations | PARTIAL | **CONFIRMED** | `src/mcp/forreyra-server.ts` is an MCP server (browser/screenshot tools); no broad dynamic external-system integration found in inspected scope [V] |
| Reusable skills | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED absent in inspected scope** | No `SKILL.md`, `skills/`, or loader in the 16 files or the repo tree filter (tree has no `skill*` path) [V] |
| Specialist subagents | PARTIAL | **CONFIRMED sequential** | `src/company/team.ts:68` `for (const role of roster)` with `await runAgentLoop` at `:83`; `company.ts:65`/`:67` nested `for` loops, `await runTeam` at `:74`. No `Promise.all`. [V] |
| Lifecycle hooks | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED absent in inspected scope** | No `PreToolUse`/`PostToolUse`/`SessionStart`/`Stop` in any fetched file [V] |
| Permission / sandbox controls | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED — strong** | Symlink-aware containment `kernel/loop.ts:205` `resolveInWorkspace` (realpath, `inside()` checks at `:224`,`:230`); role write-roots `company/role-tools.ts:46` (refuses writes outside `allowedRoots`); mutating tools only registered when permitted (`tools.ts:11–16`) [V] |
| Persistent project instructions | CODE PRESENT | **CONFIRMED** | `forge.ts:521` logs "Checking for persistent instructions in AGENTS.md"; `:522` fetches remote `AGENTS.md`; `:529` local fallback; `:611` carries it into the change set [V] |
| Persistent session memory / resume | NOT FOUND | **CONFIRMED absent in inspected scope** | No `resume`/`checkpoint`/`rewind`/session-memory token in any fetched file [V] |
| Checkpoint / rewind | NOT FOUND | **CONFIRMED absent in inspected scope** | same as above; the only reset is `git reset --hard HEAD` + `git clean -fd` inside one mission (`forge.ts:966–967`), not a user-facing rewind [V] |
| Background / long-running work | PARTIAL | **CONFIRMED** | GH Actions gives event-driven remote execution; loop is bounded (`kernel/loop.ts:77–79`: `maxSteps=12`, `maxRuntimeMs=10 min`, `maxCallMs=2 min`) [V]; no resident process [V] |
| Task coordination | PARTIAL | **CONFIRMED** | Artifact bus + company decomposition/competition (`company.ts:55–95`); loops sequential and budget-bounded (`maxRoleRuns=40`, `company.ts:55`) [V] |
| Failure diagnosis / recovery | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `forge.ts:445` `finalize()` attaches `diagnoseMission` on non-success; `forge-runner.ts:42` retries only when `shouldAutoRetry` says so, max 3, and stops if a branch already exists (`:41–44`) [V] |
| Observability / evidence | CODE PRESENT | **CONFIRMED** | `forge.ts:406` builds `TaskExecutionReport` (`:407`); `forge.yml:214` uploads `forge-evidence` [V] |
| Phone / remote operation | PARTIAL | **CONFIRMED — and this is the mission gap** | GH issue trigger + local HTTP API are remotely addressable (`forge.yml:1`, `README.md` §2.2); no phone-first orchestration UX evidenced [V] |

## Corrections and refinements

1. **"Terminal / command execution — PARTIAL" should read narrower.** ChatGPT wrote "strict fixed
   command registry; no arbitrary shell." Correct, and the registry is exactly **11 commands**
   (`test-runner.ts:14`) with shell metacharacters rejected (`runner.ts:24`). This is a deliberate
   safety choice but a **hard ceiling** on parity with Claude Code, which runs arbitrary shell. This
   is the single largest measurable capability gap and a strong candidate for the "highest-impact
   gap to fix" in the queue. [V]
2. **"Multi-file editing" — add the bound.** Multi-file is capped at `maxFilesPerMission=5` and
   `maxEditsPerMission=8` by default (`limits.ts:31–32`). ChatGPT's row is not wrong; the bound
   matters for the expense-tracker benchmark, which needs more than 5 files. [V]
3. **"Browser interaction" — the 9 browser tools are gated.** They are only registered when
   `allowBrowser` is true (`tools.ts:356–357`, `buildBrowserTools`). A mission without that flag
   cannot browse. ChatGPT's row does not say this. [V]
4. **"Specialist subagents — PARTIAL" — confirmed, and I can state the mechanism.** `team.ts:68`
   iterates the roster with `await`; there is no concurrency primitive anywhere in `company/`. So
   "sequential" is not an inference, it is the code. [V]
5. **No row disproved.** Every ChatGPT row that said CODE PRESENT is present; every row that said
   NOT FOUND IN INSPECTED SCOPE is absent in the same scope. The methodology (source inspection,
   no E2E promotion) is sound.

## What this changes for the queue

- The benchmark target (Firstborn issue #130, expense tracker) requires **more than 5 files** and
  **more than 8 edits**. With defaults it will be refused by `validatePatch` (`forge.ts:273–278`).
  Either raise `FORGE_MAX_FILES`/`FORGE_MAX_EDITS` for that run or scope the benchmark smaller. This
  is a concrete, evidence-backed finding for the E2E step. [V]
- The **terminal registry** is the highest-leverage parity gap: it is safe but narrow, and widening
  it carefully is the clearest path toward Claude Code parity. [I] — a recommendation, not a claim.
- Skills and lifecycle hooks are genuinely absent in the inspected scope; do not let a future
  scorecard promote them without new evidence. [V]

## Not claimed

- No E2E run was performed. Nothing here is E2E VERIFIED.
- Only the 16 cited files + the repo tree were read; "not found in inspected scope" is not a
  repository-wide proof of absence for files outside that scope. [U] where noted.

— Watcher (via OpenHands). This report was created by an AI agent on behalf of the repository owner.
