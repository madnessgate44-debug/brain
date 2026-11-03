# How close is brain to a Claude-Code-like experience?

**Answered:** 2026-11-03, by reading the code (not a checklist). **Method:** every claim below
was checked against the running source with file:line evidence, and the app's own claims were
audited by `watcher/knowledge/tools/purpose_audit.py` (12/12 claims implemented in production).

The owner's test for an audit is right: **an audit must compare the code to the purpose of the
app, and must find what is actually broken — not restate a feature list.** This is that audit.

## The honest distance

Think of the gap in three parts: the **loop**, the **reach**, and the **proof**.

### 1. The loop — one agent has it, eight do not
- A real agentic loop (shell + file editing, run -> observe -> act) exists, but **only in the
  `developer` role**: `brain/company/openhands_developer.py:124-126` attaches `TerminalTool`
  and `FileEditorTool`; `_run_sdk_sync` (line ~196) runs the SDK conversation.
- It is reached only on one branch: `brain/company/agent_runner.py:401`
  (`role_key == "developer" and isinstance(self.provider, OpenAICompatibleProvider)`).
- The other eight roles are **single-shot**: `agent_runner.py:412` is one
  `provider.complete(...)` call. Product, UX, architecture, review, QA, security, customer,
  release — none of them can read a file or run a command themselves. They judge text.
- **Distance:** Claude Code is one loop that can do all of this. Here, 1 of 9 roles loops.
  **~2/10** for "the agent can act".

### 2. The reach — the loop cannot use most of a real repo
The developer loop is real but **hemmed in**:
- It runs in a throwaway `tempfile.TemporaryDirectory` (`openhands_developer.py:196`), seeded
  only from `source_contents` the gateway already fetched. No git, no full checkout.
- **Deletions are forbidden**: `openhands_developer.py:250-253` raises if the agent deletes a
  file. Refactors, renames, and cleanups are impossible.
- **New files are constrained**: `openhands_developer.py:238` raises on any new file not in the
  architecture plan or named in the request. The agent cannot add a file it discovers it needs.
- The patch contract is "up to 30 files, <=200 KB each, text only, no deletions".
- **Distance:** Claude Code edits the repo in place with full git and shell. Here the agent
  works in a sandbox and can only *propose text*. **~3/10** for "the agent can change a repo".

### 3. The proof — the loop is not proven to run against a live model in CI
- The loop **is** wired into the running service: `brain/runtime/mission_runtime.py:94` builds
  `CompanyWorkflowEngine(SpecialistAgentRunner(OpenAICompatibleProvider()), tools)` for a
  mission whose `metadata.workflow_type == "software_company"`. So it is reachable, not dead.
- But it only engages with a real provider; **tests inject fakes** (`agent_runner.py:403`
  comment). So the suite proves the *wiring*, not a live end-to-end coding run.
- There is **no committed evidence of a real issue -> real PR** produced by this path. R2 was
  proven by a single shell command through the SDK (`echo HELLO_AUDIT_123`), not a code change.
- **Distance:** Claude Code's whole value is that it demonstrably does the work. Here the loop
  is built, wired, and unit-tested but **not proven to land a real change**. **~2/10**.

### Capability table (present / partial / absent), with evidence

| Claude-Code capability | brain today | Evidence |
|---|---|---|
| Agentic shell loop | **PARTIAL** — developer role only | `openhands_developer.py:124-126`; `agent_runner.py:401` |
| File editing | **PARTIAL** — sandboxed, no deletions, bounded new files | `openhands_developer.py:238,250` |
| Repo navigation / full checkout | **ABSENT** — temp dir seeded from fetched files | `openhands_developer.py:196` |
| Skills (SKILL.md) | **PARTIAL** — prompt files, not SDK `Skill` objects | `agent_runner.py:21,36` |
| Hooks | **PARTIAL** — PreToolUse on the developer conversation | `brain/company/hooks.py:51,68` |
| Session resume | **PARTIAL** — company session wrapper, not the mission runtime | `brain/company/session.py:41,53` |
| Parallel subagents | **PARTIAL** — three review gates run concurrently | `engine.py:375` |
| MCP client | **ABSENT** | not present in `brain/` |
| Approval gates | **STRONG — arguably ahead of Claude Code** | `browser_worker.py` policy, `roles.py` gates |

### Bottom line

**Roughly 3 out of 10** toward a Claude-Code-like experience — up from ~1 of 7 primitives at
the start of the parity work, because the loop, skills, hooks, resume, and parallel gates now
exist. The missing 7/10 is not more features; it is **depth**: one loop that can edit a real
repo, delete and add files, run git, and do it against a live model with committed proof.

## What the Watcher must do about it (the "act" part)

The Watcher's job is not to report this table. It is to **act on it**, in this order:

1. **Prove the loop once, for real.** Dispatch the company workflow on a trivial issue against
   a real repo and commit the resulting PR link as evidence. (Closes "the proof" gap.)
2. **Lift the patch contract.** Allow deletions and unplanned new files inside the sandbox,
   with the existing review gates as the guard. (Closes most of "the reach" gap.)
3. **Run a second role on the loop.** Move the reviewer onto the same agentic runtime so it
   reads the diff itself. (Closes the "one of nine" gap.)
4. **Re-measure.** Re-run this audit and `purpose_audit.py`; move the number only with evidence.
