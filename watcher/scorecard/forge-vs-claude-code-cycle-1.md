# Forge vs Claude Code — cycle 1 (independent re-inspection)

Ranked-plan task **#3**: "Independent re-inspection of your cycle-0 scorecard" (owner Watcher,
dependency: Firstborn read). Author: Watcher (OpenHands session), 2026-11-01.

Tags: [V] verified against source in this session, [C] reported claim, [I] inference,
[U] unknown, [B] blocker.

## Scope and method

- Target: `madnessgate44-debug/Firstborn`, branch `main`, commit
  `36a9916e900f9019ef1c46d95d08985c38fbac9d` (2026-11-01T02:48:51Z). [V]
- Method: read the repository tree through the GitHub API, then read every file the cycle-0
  scorecard cited plus the full `src/`, `tests/`, `.github/workflows/`, and `docs/` trees. No
  file was copied from ChatGPT's summary; each row was checked against source. [V]
- This is a **source-inspection** re-check, exactly like cycle 0. No live Forge run was executed
  here, so every runtime row stays E2E UNVERIFIED. [V]

## Result: cycle-0 rows independently confirmed

Cycle 0 was methodologically sound. I could not disprove any row; I confirmed 20 of 20. Two
rows move from "NOT FOUND IN INSPECTED SCOPE" to "NOT FOUND IN THE FULL TREE" (a stronger
negative), and one row gains a named root cause for a failing test.

| # | capability | cycle-0 | cycle-1 verdict | evidence |
|---|---|---|---|---|
| 1 | Repository exploration | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/agent/tools.ts:184` list_files, `:194` read_file, `:205` search, `:242` find_files |
| 2 | Multi-file editing | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/agent/tools.ts:288` edit_file (exact-anchor), `:321` write_file (refuses overwrite) |
| 3 | Terminal / command execution | PARTIAL | **CONFIRMED** | `src/services/test-runner.ts:15` `AUTHORIZED_COMMANDS` = 11 fixed entries; `:49` rejects anything else with exit 126. No shell/eval. |
| 4 | Test/build/debug loop | PARTIAL | **CONFIRMED** | `src/agent/forge.ts:852` bounded 3-attempt repair loop; `test-runner.ts:68` per-command SIGKILL + exit 124 timeout |
| 5 | Browser interaction | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/services/browser.ts:56` BrowserService, `:68` `chromium.launch`, `:221` screenshot; `src/agent/tools.ts:374` buildBrowserTools |
| 6 | GitHub / PR / CI | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `.github/workflows/forge.yml:4` `issues:[labeled]`, `:40` owner-only gate, `:43-45` `contents:write`/`pull-requests:write`; `src/agent/policy.ts:119` allowOpenPr |
| 7 | MCP integrations | PARTIAL | **CONFIRMED** | `src/mcp/forreyra-server.ts:21` `McpServer`, `:12-13` stdio transport, 10 `registerTool` calls |
| 8 | Reusable skills | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED, strengthened** | Full-tree grep for `SKILL.md`/`skills/` returns nothing; no loader/registry exists |
| 9 | Specialist subagents | PARTIAL | **CONFIRMED** | `src/company/team.ts:68` `for (const role of roster)` — sequential await; `src/company/company.ts:65,67` nested sequential loops |
| 10 | Lifecycle hooks | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED, strengthened** | Full-tree grep for `PreToolUse`/`PostToolUse`/`SessionStart`/`hooks` returns nothing |
| 11 | Permission / sandbox controls | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/agent/policy.ts:18` 4 profiles, `:120` `allowMerge = false` (hard), `:107` branch-prefix gate; `src/kernel/loop.ts:205` `resolveInWorkspace` |
| 12 | Persistent project instructions | CODE PRESENT | **CONFIRMED** | `src/agent/loop-runner.ts:19-30` `loadMemory` reads `AGENTS.md`; `src/services/model.ts` `buildLoopPrompt` fences it as UNTRUSTED (`tests/memory.test.ts`) |
| 13 | Persistent session memory / resume | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED** | No resume/rehydrate path; task evidence is written, session state is not |
| 14 | Checkpoint / rewind | NOT FOUND IN INSPECTED SCOPE | **CONFIRMED** | No code-level equivalent; only chat-sync cursors in `docs/CHAT_SYNC_PROTOCOL.md` |
| 15 | Background / long-running work | PARTIAL | **CONFIRMED** | Event-driven via Actions only; no `schedule:`/`cron:` in any Firstborn workflow [V]; no resident process |
| 16 | Task coordination | PARTIAL | **CONFIRMED** | Artifact bus + company decomposition (`src/company/company.ts`), sequential and bounded |
| 17 | Failure diagnosis / recovery | CODE PRESENT; E2E UNVERIFIED | **CONFIRMED** | `src/agent/forge.ts:63` `classifyFailure`, `:87` `withBoundedRetry`; `src/agent/diagnosis.ts` |
| 18 | Observability / evidence | CODE PRESENT | **CONFIRMED** | `src/types/agent.ts:72` `TaskExecutionReport`; `src/agent/mission-trace.ts` |
| 19 | Phone / remote operation | PARTIAL | **CONFIRMED** | GitHub issue trigger + HTTP API entry points are remotely addressable; no proven phone orchestration UX |
| 20 | Score discipline (no % assigned) | correct | **CONFIRMED** | Zero live runs were executed in cycle 0, so a percentage would reward declarations |

## New finding — root cause of the failing `Verification and Build Checks`

The issue body lists "Firstborn `Verification and Build Checks` fails on push" as a blocker. I
reproduced the failure from the run logs and traced it to source. [V]

- Failing run: `41266700730`, `Verification and Build Checks`, event `push`, branch `main`,
  head `36a9916e…`, 2026-11-01T02:48:54Z. Job `verify` → step **Run Tests** → failure. [V]
- Result line: `# pass 317 / # fail 1` → `not ok 80 - a hanging tool cannot defeat the runtime ceiling`
  (`tests/company.test.ts:270`). [V]
- Assertion error: expected `/Runtime ceiling/`, actual
  `'Step ceiling reached (3); stopping safely.'` [V]

Root cause [I], from source:

1. The test (`tests/company.test.ts:270-281`) passes `limits {maxSteps:3, maxRuntimeMs:100,
   maxCallMs:100}` and a tool whose `run` never resolves, and asserts the reason matches
   `/Runtime ceiling/`. [V]
2. In `src/kernel/loop.ts:177`, a tool call is wrapped in `withDeadline(...)`. When the deadline
   fires, the `catch` at `:180` converts the timeout into a **failed observation**
   (`Tool "…" threw: …`) and the loop **continues** to the next step. [V]
3. The loop therefore burns all 3 steps and exits through the step-ceiling branch at
   `src/kernel/loop.ts:186` → `Step ceiling reached (3); stopping safely.` [V]
4. The `Runtime ceiling reached` message is only produced when the *brain* call times out
   (`:133-134`) or when the top-of-loop runtime check trips (`:121-122`) — neither fires here
   because each tool timeout is swallowed first. [V]

This is a test/behaviour mismatch in `main`, not a flaky test. Two candidate fixes, both one
line, to be chosen by the Firstborn owner (see the proposal below):

- (a) Make the test assert the real behaviour: `/Step ceiling reached/`. Cheapest, but it stops
  testing the runtime ceiling it names.
- (b) Treat a tool deadline as a runtime-ceiling stop: in the `catch` at `loop.ts:180`, return
  `{ status: 'BLOCKED', reason: 'Runtime ceiling reached: …' }` when the error matches
  `/deadline/`. This preserves the test's intent.

Recommendation: (b). It keeps the invariant the test asserts — a hung tool cannot outlive the
ceiling — and matches the brain-call path at `:133`. [I]

I did **not** change Firstborn. Cross-repo edits need coordination (WATCHER.md §8; the
multi-session warning on #240), and the current work order says no merge/deploy. The finding is
queued as a proposal.

## What this does not claim

- No Forge capability is promoted to E2E VERIFIED. Every runtime row remains UNVERIFIED. [V]
- "NOT FOUND IN THE FULL TREE" is a statement about `main` at `36a9916e…` only; a later commit
  could add the capability. [I]
- The root cause is derived from source + the run log, not from a local re-run of the test. [V]
