# How close is brain to a Claude-Code-like experience?

**Answered:** 2026-11-03, by reading the code (not a checklist). **Method:** every claim below
was checked against the running source with file:line evidence, and the app's own claims were
audited by `watcher/knowledge/tools/purpose_audit.py` (12/12 claims implemented in production).

The owner's test for an audit is right: **an audit must compare the code to the purpose of the
app, and must find what is actually broken — not restate a feature list.** This is that audit.

## The honest distance

Think of the gap in three parts: the **loop**, the **reach**, and the **proof**.

### 1. The loop — FIXED: all nine roles now have it
- A real agentic loop (shell + file editing, run -> observe -> act) exists for **every role**.
  The `developer` uses `brain/company/openhands_developer.py` (file editing + terminal);
  every other role uses `brain/company/openhands_role.py`, added 2026-11-03: it runs the same
  OpenHands SDK conversation with file + terminal tools, scoped to a read-only temporary copy,
  and returns the role's JSON contract.
- Wiring: `brain/company/agent_runner.py:412` — the non-developer branch calls
  `run_openhands_role`, so product, UX, architecture, review, QA, security, customer, and
  release all **read the code and run checks** before they answer, instead of judging pasted text.
- **Verified:** `watcher/knowledge/tools/purpose_audit.py` reports
  **"Agentic loop covers 9 of 9 roles (0 run single-shot)"**.
- **Distance now:** Claude Code is one loop for one agent; here all nine company roles loop.
  Remaining gap is the *reach* (below), not the loop. **~5/10** for "the agent can act".

### 2. The reach — the loop cannot use most of a real repo
The loops are real but **hemmed in**:
- The developer runs in a throwaway `tempfile.TemporaryDirectory` (`openhands_developer.py:196`),
  seeded only from `source_contents` the gateway already fetched. No git, no full checkout.
- The investigative roles are seeded from the same `source_contents`, so a role can only read
  files the gateway already fetched for it.
- **Deletions and new files are allowed (2026-11-09)**: the adapter collects an agent edit, a new
  file, or a deletion (`{"path", "deleted": true}`) and the write gateway commits it — a deletion
  becomes a tree entry with `sha: null`, which removes the path. The engine validator accepts
  deletion markers. See "Lifted the patch contract" below.
- The patch contract is now "up to 30 files, <=200 KB each, text only; deletions and new files
  allowed, guarded by the independent review gates".
- **Distance:** Claude Code edits the repo in place with full git and shell. Here the agent
  works in a sandbox seeded from fetched files (still no full checkout). The change *kinds* are
  now unbounded, but the *reach* (a real checkout) is not. **~4/10** for "the agent can change a repo".

### 3. The proof — the engine path has landed one real run, and today it cannot
- The loop **is** wired into the running service: `brain/runtime/mission_runtime.py:94` builds
  `CompanyWorkflowEngine(SpecialistAgentRunner(OpenAICompatibleProvider()), tools)` for a
  mission whose `metadata.workflow_type == "software_company"`. So it is reachable, not dead.
- But it only engages with a real provider; **tests inject fakes** (`agent_runner.py:403`
  comment). So the suite proves the *wiring*, not a live end-to-end coding run.
- **This engine path has landed one real issue -> PR run, on 2026-10-11.** PR #218 (branch
  `brain/mission-523096880e41`, one test added to `tests/test_openhands_developer.py`) was opened by
  run 38148411690 from an owner issue containing `/brain simulate`, and merged 2026-11-07.
  Verified from that run's log (`- Mode: implementation`, `- Pull request: …/pull/218`). The earlier
  sentence here said no such run existed; that was wrong about the run and right about the proof —
  `watcher/knowledge/evidence/` still holds only session-loop traces, so no engine-path trace is
  committed. The session-agent loop is a different path (a Cloud conversation, not this engine) and
  it has landed one: run 45209420890 filed issue #358 and opened PR #359 inside four minutes
  (`watcher/knowledge/evidence/session-loop-20261123-154852.md`). `purpose_audit.verify_trace`
  checks that ordering against GitHub; the 2026-11-24 record in the same directory is refuted by
  it, because PR #359 predates both that run and the issue it names.
- **Attempted live again on 2026-11-27** (issue #375, run 46020431346). It failed, and each cause is
  read from that run's log rather than inferred:
  1. `capability_planning` classified the objective *"add exactly one regression test …"* as
     `read_only` — *"No affirmative repository mutation action was requested"* — so the workflow
     audited the repository and could never open a pull request. The determiner list in
     `brain/company/mission_capabilities.py:24` did not admit "exactly" or "only". Fixed on this
     branch; `tests/test_mission_capabilities.py` pins the production objective.
  2. The model route answered `HTTP 503` through all three attempts
     (`brain/company/llm_provider.py:196`), which aborted the mission.
  3. `BRAIN_GITHUB_TOKEN` was rejected `401 Bad credentials` at `credential_preflight`, so the write
     path had no usable token either.
- **Distance:** Claude Code's whole value is that it demonstrably does the work. Here the loop is
  built, wired, unit-tested, and has landed a change once; today it is blocked by one code defect
  (fixed here) and two credentials the owner controls. **~2/10** until a run *after* this fix
  produces a pull request.

### Capability table (present / partial / absent), with evidence

| Claude-Code capability | brain today | Evidence |
|---|---|---|
| Agentic shell loop | **PARTIAL** — developer role only | `openhands_developer.py:124-126`; `agent_runner.py:401` |
| File editing | **PARTIAL** — sandboxed; edits, new files, and deletions all allowed | `openhands_developer.py:140-179` (`_collect_change_set`); `github_gateway.py:204-228` |
| Repo navigation / full checkout | **ABSENT** — temp dir seeded from fetched files | `openhands_developer.py:196` |
| Skills (SKILL.md) | **PARTIAL** — prompt files, not SDK `Skill` objects | `agent_runner.py:21,36` |
| Hooks | **PARTIAL** — PreToolUse on the developer conversation | `brain/company/hooks.py:51,68` |
| Session resume | **PARTIAL** — company session wrapper, not the mission runtime | `brain/company/session.py:41,53` |
| Parallel subagents | **PARTIAL** — three review gates run concurrently | `engine.py:375` |
| MCP client | **ABSENT** | not present in `brain/` |
| Approval gates | **STRONG — arguably ahead of Claude Code** | `browser_worker.py` policy, `roles.py` gates |

### Bottom line

**Roughly 4 out of 10** toward a Claude-Code-like experience — up from ~1 of 7 primitives at
the start of the parity work, because the loop, skills, hooks, resume, and parallel gates now
exist, and (2026-11-09) the patch contract allows deletions and new files. The missing 6/10 is
not more features; it is **depth**: one loop that edits a real repo checkout, runs git, and does
it against a live model with committed proof.

### Lifted the patch contract (2026-11-09)

The sandbox contract no longer forbids whole classes of change:

- `_collect_change_set` (`openhands_developer.py:140`) collects an edit, a **new file** the agent
  created, and a **deletion** (as `{"path", "deleted": true}`), bounded only by the count/size caps.
- The engine validator (`engine.py:136`) accepts a deletion marker and rejects a marker that also
  carries content.
- The write gateway (`github_gateway.py:204`) turns a deletion into a Git tree entry with
  `sha: null`, which removes the path on the new branch. Branch-and-PR, independent review, QA,
  security, and release gates are unchanged — they are the guard.

Verified by the suite (`python3 -m pytest -q`: 485 passed, 2 skipped, 2026-11-09) and by
`purpose_audit.py`, whose depth finding now reports **OK** for the contract.

## What the Watcher must do about it (the "act" part)

The Watcher's job is not to report this table. It is to **act on it**, in this order:

1. **Prove the loop once, for real.** Dispatch the company workflow on a trivial issue against
   a real repo and commit the resulting PR link as evidence. (Closes "the proof" gap.)
   *Status 2026-11-26: the check now requires the run, not just the pair. Reading the issue and
   the pull request proved both existed, not that a run produced them; PR #359's body mentions six
   issue numbers, and the record that named issue #363 -> PR #359 is refuted by GitHub's
   timestamps (PR opened 2026-11-23T15:53:36Z, issue filed 2026-11-24T15:48:47Z, named run
   started 2026-11-24T15:40:03Z). `verify_trace` reads `- run:` and requires the run to be
   completed, to precede the issue and the pull request, and to share the PR's author. Only the
   2026-11-23 trace (run 45209420890 -> issue #358 -> PR #359) survives that test. The
   `brain/company` engine path below is still unproven.*
2. **Lift the patch contract.** Allow deletions and unplanned new files inside the sandbox,
   with the existing review gates as the guard. (Closes most of "the reach" gap.)
   *Done 2026-11-09 — see "Lifted the patch contract" above.*
3. **Run a second role on the loop.** Move the reviewer onto the same agentic runtime so it
   reads the diff itself. (Closes the "one of nine" gap.)
4. **Re-measure.** Re-run this audit and `purpose_audit.py`; move the number only with evidence.
