# Purpose — what this app claims to do (for the Watcher's purpose audit)

The Watcher's audit must compare the code to the **purpose of the app**, not to a checklist
of features. This file states the purpose and the claims the app makes about itself.
`watcher/knowledge/tools/purpose_audit.py` checks every claim against `brain/` and reports:
OK (implemented in production), UNTESTED (only tests match), or MISSING — with file:line evidence.

Format: one claim per line, three TAB-separated fields: claim, probe regex, path hint.

Mission orchestration with persistent state	brain.core.models|class Mission|mission_state	brain/services
Execution-to-artifact path (a mission produces an artifact)	mission-brief|artifact_path	brain/runtime
Internal browser worker (bounded, allowlisted)	BRAIN_BROWSER_ALLOWED_DOMAINS|BrowserPolicyError	brain/runtime/workers
Remote test execution over GitHub Actions	brain-task-runner|actions/runs	brain/company
Nine-role software-company workflow	WORKFLOW_ORDER	_company
Real agentic developer (shell + file editing loop)	TerminalTool	brain/company/openhands_developer.py
Release gates enforced before a pull request	evaluate_release_gate	brain/company/workflow.py
Authenticated control API	BRAIN_CONTROL_API_KEY	brain/api
Session resume across restart	persistence_dir|resume	brain/company/session.py
Skills loaded from files (SKILL.md style)	load_role_skill	brain/company/agent_runner.py
Lifecycle hooks fired on tool use	HookConfig	brain/company/hooks.py
Parallel role execution	asyncio.gather	brain/company/engine.py
