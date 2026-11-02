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
| R1 | **This spec** exists and is accurate | file committed; every [V] row re-checkable | this file |
| R2 | Shell tool on the developer path | a company mission can run a real command locally and record output | test + run log |
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

## 5. Current slice

This PR delivers **R1** (the spec) and stands up the branch `goal/claude-code-parity`. R2 begins
next. Nothing else is claimed.
