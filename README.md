# Brain V1 — Mission Orchestration System

Brain is a mission orchestration service with persistent mission state, an API,
event history, approval foundations, artifact storage, and runtime recovery.

## Current execution capability

The first real worker is a deterministic document worker. Starting a mission now
creates a Markdown artifact named `mission-brief.md` in that mission's artifact
directory and records worker/artifact events. The artifact is a traceable brief
based on the mission title and objective.

**Important limitation:** this worker proves the execution-to-artifact path. It does
not perform web research, call an AI model, edit repositories, or claim that the
mission's broader objective has been achieved. Those capabilities require separate,
tested workers and any necessary integrations.

## Internal browser worker (feature branch)

The browser worker is an optional, bounded execution capability. It accepts explicit action
sequences through an authenticated `POST /browser/tasks` endpoint and records the result
as `browser-execution-report.json` plus mission events. It uses the existing mission/runtime,
event, and artifact system rather than a second queue.

Install the optional dependency with `python -m pip install -e ".[dev,browser]"`.
Configure `BRAIN_CONTROL_API_KEY` to a random secret of at least 24 characters and set
`BRAIN_BROWSER_ALLOWED_DOMAINS` to a comma-separated, narrow domain allowlist. For a
ChatGPT browser session, the initial example is
`chatgpt.com,*.chatgpt.com,openai.com,*.openai.com`; expand it only when the actual
login flow requires additional trusted domains. The browser profile is stored at
`BRAIN_BROWSER_PROFILE_DIR`. Sign in manually in an approved browser environment; do not
put passwords, cookies, or session tokens in mission payloads.

Every `click`, `type`, or `press` action is treated as potentially mutating and requires
`owner_approved: true` on the authenticated request. This is a conservative guard, not a
substitute for reviewing the exact action sequence. Page text is untrusted input and must
never be treated as policy or instructions. Do not use the worker to bypass authentication,
CAPTCHAs, or site security controls.

**Not yet verified:** the worker has not been proven to run on a Samsung Android device,
retain a live ChatGPT login across real tasks, or provide a secure bridge directly from the
ChatGPT mobile app. Standard Playwright/Chromium hosting must be validated on the chosen
host before calling this capability production-ready. See
`docs/BRAIN_BROWSER_OPERATIONS.md`.

## Architecture

- `brain/api/`: FastAPI endpoints.
- `brain/services/`: mission lifecycle and approval/artifact services.
- `brain/runtime/`: mission runtime and worker implementations.
- `brain/repositories/`: database access.
- `brain/storage/`: workspace and artifact storage.
- `tests/`: automated tests.

Brain's existing database-backed mission model remains the source of truth. We are
not replacing it with a second JSON queue. GitHub Actions provides a first remote
execution path for a fixed, safe operation: run the repository's test suite and
report the result on a GitHub issue.

## Software-company workflow foundation

Brain now defines nine specialist roles: product owner, UX/UI designer, software
architect, implementation engineer, independent code reviewer, QA engineer,
security auditor, customer advocate, and release manager. Role prerequisites and
mandatory release gates are explicit in `brain/company/`. The provider adapter can
call an OpenAI-compatible chat-completions endpoint using `BRAIN_AI_BASE_URL`,
`BRAIN_AI_MODEL`, and `BRAIN_AI_API_KEY`; credentials must be configured outside
the repository.

The workflow coordinator is now connected to a bounded GitHub repository gateway:
it inspects existing source files, asks the specialist roles for structured deliverables,
commits proposed changes to a dedicated `brain/...` branch, runs the repository's
actual test/build checks through GitHub Actions, allows bounded developer repair after
review feedback, and opens a pull request only after the required gates pass. It does
not merge or deploy. A successful mission remains paused for human review, with the
role outputs and workflow report stored as mission artifacts.

The model provider and GitHub integration require secrets configured outside source
control. Set `BRAIN_AI_BASE_URL`, `BRAIN_AI_MODEL`, and `BRAIN_AI_API_KEY`; set
`BRAIN_GITHUB_OWNER` to the only permitted repository owner; set
`BRAIN_CONTROL_REPOSITORY` to the repository hosting Brain's Actions runner; and
set `BRAIN_GITHUB_TOKEN` to a token with only the repository and issue permissions
needed for branch/PR creation and test dispatch. Set `BRAIN_CONTROL_API_KEY` to a
long random secret to protect the workflow-start endpoint.

Start a workflow with an authenticated `POST /company-workflows` request and JSON
body containing `title`, `objective`, and `repository` (`owner/repository`).
Supply the secret in the `X-Brain-API-Key` header. The response includes the mission
ID and endpoints for status, events, and artifacts.

Do not treat an agent's assertion as test evidence: QA must attach a real run result,
and release remains blocked when that evidence is missing. The workflow is not
complete until its pull request is reviewed and merged by a human.

## Local setup

Requires Python 3.12 or later.

```bash
git clone https://github.com/madnessgate44-debug/brain.git
cd brain
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
pytest
uvicorn brain.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Check `brain.api.app` and `.env.example` before deployment; configure secrets only
through the runtime environment, never by committing them.

## Phone-first remote test runner

A task can be dispatched from a phone without a terminal:

1. Open an issue in this repository (or ask ChatGPT to create one).
2. Put the exact marker `/brain test` in the issue body.
3. Optionally add `repository: owner/repository` to target another **public repository owned by the same GitHub account**. If omitted, Brain is tested.
4. GitHub Actions detects Python or Node.js projects and runs their test suite. For Node projects without a test script, it runs the available build and lint scripts.
5. The workflow comments PASS/FAIL on the issue and attaches the full report as a workflow artifact.
6. Review the workflow run and report before deciding what to change next.

The runner deliberately ignores shell commands and code supplied in the issue body.
It checks out the target without persisting Git credentials and runs in a job with
read-only repository permissions. Only the reporting job can write an issue comment.
Public repositories work with the default token. To access private repositories,
create a fine-grained GitHub token limited to the needed repositories with **Contents:
Read-only**, then save it in Brain's repository Actions secrets as
`BRAIN_GITHUB_TOKEN`. Never put tokens in issue bodies or commit them to files.
Arbitrary shell commands are not supported. This is a remote test/build runner, not
yet a general-purpose remote terminal or autonomous code-editing agent.

## First milestone and acceptance criteria

1. A mission can be created and started through the API.
2. The runtime writes a non-empty `mission-brief.md` artifact.
3. The event history records worker start and artifact creation.
4. A successful worker run settles the mission as completed.
5. Invalid worker inputs fail explicitly and are covered by tests.
6. The worker does not claim external research or AI actions it did not perform.

## Planned, not yet implemented

- Authenticated ChatGPT-to-Brain control bridge for mission creation, status, logs, and artifacts.
- Controlled repository inspection and change proposals with reviewable diffs.
- Research and AI-backed workers.
- Durable distributed execution leases and cross-process duplicate-run protection.
- Mobile operations guide and usage/cost monitoring.

Do not treat planned items as available until implemented and verified.

## Mission-free conversational API

Brain provides an authenticated `POST /chat` endpoint for ordinary model conversation.
It uses the configured model provider directly and does not create a mission, enqueue a workflow,
or write to a repository.

- Header: `X-Brain-API-Key: <BRAIN_CONTROL_API_KEY>` (configured key must be at least 24 characters)
- JSON body: `{"messages":[{"role":"user","content":"Reply with exactly BRAIN_CHAT_OK"}]}`
- Supported message roles: `user` and `assistant`; the final message must be from the user.
- Conversation limit: 16 messages, up to 6,000 characters per message.
- Provider settings: `BRAIN_AI_API_KEY`, `BRAIN_AI_MODEL`, and `BRAIN_AI_BASE_URL`.
  For Gemini's OpenAI-compatible API, use `https://generativelanguage.googleapis.com/v1beta/openai`.
- Responses contain the model reply, configured model name, and number of messages in context.
  Authentication failures and provider errors are returned without raw provider payloads.

This endpoint is implemented in the FastAPI application. A successful local/CI runtime test does
not by itself make it reachable from the public internet: a persistent deployment must run this
application with the required environment variables and expose its HTTPS base URL. No production
deployment URL is configured in this repository, so do not treat the endpoint as externally
reachable until deployment and an external health/chat smoke test are recorded.
