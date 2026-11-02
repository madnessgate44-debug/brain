# Goal: make Brain's agents Claude-Code-class

**Set by owner:** 2026-11-02. **Status:** STARTED (spec + roadmap). **Owner of merge:** Ahmed.

## 0. The goal (verbatim intent)

The agents that live **inside this `brain` repo** must reach Claude-Code-class capability.
Scope of "the agents":

| Agent | Location | What it is today |
|---|---|---|
| Shadow | `shadow/shadow.py` | one-shot auditor prompt (no tools) |
| Watcher | `watcher/` + `watcher/bridge/loop.py` | operator + loop runner |
| The "company" | `brain/company/` | 9-role coding workflow (the coding agent) |

Note: there is **no component named "Force" inside `brain`** [V] (`grep -i 'forge\|force' brain/`
returns one docstring). "Forge" is the separate `Firstborn` repo. The `brain/company` coding agent
is treated as the "Force" the owner means until corrected.

## 1. The gap, verified this session

| Claude Code capability | In brain today? | Evidence |
|---|---|---|
| Arbitrary shell / bash | NO | `grep -rIE 'subprocess\|os.system\|shell=True' brain/` -> 0 hits [V] |
| Reusable skills (SKILL.md) | NO | no `SKILL*` file in tree [V] |
| Lifecycle hooks | NO | no Pre/PostToolUse, Stop tokens [V] |
| Session resume / checkpoint | NO | only a comment "never auto-resume missions" `brain/services/recovery_service.py:16` [V] |
| Parallel subagents | NO | company roles run sequentially [V] |
| MCP client | NO | not present in `brain/` [V] |
| Tool-using loop | PARTIAL | developer role only, via OpenHands SDK `brain/company/openhands_developer.py:134` [V] |
| Sandbox + permission gates | STRONG | domain allowlist + owner-approval (`browser_worker.py`), 9 mandatory gates (`roles.py`) [V] |

**Root cause:** the company's 8 non-developer roles are structured *single-shot* prompts
(`brain/company/agent_runner.py`, `llm_provider.py` -> one `chat/completions` call), and Shadow is
one prompt. Only the developer role uses a real agentic loop.

## 2. The path — one runtime, already pinned

`pyproject.toml` already depends on `openhands-sdk==1.54.0` and `openhands-tools==1.54.0` [V].
That SDK supplies the Claude-Code-class primitives directly:

- `TerminalTool` (bash), `FileEditorTool`, `TaskTrackerTool` — `docs.openhands.dev/sdk/getting-started`
- Skills — `openhands.sdk.context.Skill` / `AgentContext(skills=...)` — `/sdk/guides/skill`
- Hooks — `openhands.sdk.hooks.HookConfig` — `/sdk/guides/hooks`
- Persistence — `Conversation(persistence_dir=...)` — `/sdk/guides/convo-persistence`
- Parallel tool execution, task-tool-set subagents, MCP — `/sdk/guides/parallel-tool-execution`, `/task-tool-set`, `/mcp`

So the goal is not to build these from scratch. It is to **run Shadow, Watcher, and the company
roles on that one runtime** instead of bespoke single-shot Gemini prompts.

## 3. Roadmap (each item = its own bounded PR)

| # | Requirement | Acceptance criterion | Evidence expected |
|---|---|---|---|
| R1 | **This spec** exists and is accurate | file committed; every [V] row re-checkable | this file — DONE |
| R2 | Shell tool on the developer path | the developer agent's tool list includes a local shell, scoped to the isolated workspace | `tests/test_openhands_developer.py` — DONE |
| R3 | Skills loader for role prompts | roles load from `SKILL.md`-style files | test + a sample skill |
| R4 | Hooks wired to the event bus | a PreToolUse hook fires and is logged | test + log |
| R5 | Session persistence / resume | a mission resumes across process restart | test + restart log |
| R6 | Shadow gets tools + a real loop | Shadow can read a diff itself, not just a prompt | test + run log |
| R7 | Parallel role execution | independent gates run concurrently | timing test |

Order R2 -> R3 -> R4 -> R5 -> R6 -> R7. Each is the smallest complete change for that row.

## 4. Constraints (non-negotiable)

- Free, no-card only (owner policy). Never push to `main`. Draft PR within 10 min of first edit.
- No merge without owner. No secret in any file.
- Every claim tagged [V]/[C]/[I]/[A]/[U]/[B]; every check in the Verification Ledger.

## 5. Progress

| Slice | State | Evidence |
|---|---|---|
| R1 spec | COMPLETED | `docs/GOAL_CLAUDE_CODE_PARITY.md` |
| R2 shell tool | VERIFIED | tool list asserted by test **and** a real command ran through the SDK terminal: `echo HELLO_AUDIT_123 && pwd` -> `HELLO_AUDIT_123` / `/tmp`, exit 0 |
| R3 skills loader | PARTIAL -> VERIFIED | 8 prompt-based roles verified by test; the **developer** role was a defect (skill loaded but discarded on the SDK path) — fixed in `e6eaf07`; suite 301 passed / 1 skipped |

### Audit corrections (2026-11-02)

An audit found my first R2/R3 report overstated its evidence. Two corrections:

1. **R2/R3 were marked COMPLETED on structural evidence only** (the tool appears in a list; a file
   exists). That violates the OS rule *build ≠ behavior*. R2 is now proven by a real run; R3 is
   proven per role.
2. **Real defect:** the developer role returns through `run_openhands_developer` *before* the
   system prompt is used (`agent_runner.py:401`), so `developer.md` was loaded but never applied.
   Fixed: `_task_prompt` now prepends the skill. Regression test added.

Honest current count of Claude-Code-class primitives present: **1 of 7** as first-class features
(agentic loop, in the developer role only, via the SDK). Sandbox/approval gates are strong and
arguably ahead of Claude Code. Shell exists only inside the developer agent's loop, not as a Brain
capability. Missing: SDK-format skills, hooks, session resume, parallel agents, MCP, repo-navigation
tools.

R2 note: the shell is added to the developer agent's tool list and runs inside the isolated
temporary workspace. Brain's GitHub Actions check runner stays the authoritative test evidence;
a local run is advisory. This is the Claude-Code-style "agent runs its own checks" behaviour,
without letting the agent self-certify.

Next slice: **R4 — wire a lifecycle hook to the event bus.**
