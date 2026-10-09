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
3. GitHub Actions installs the project dependencies and runs `pytest -q`.
4. The workflow comments PASS/FAIL on the issue and attaches the full test report.
5. Review the workflow run and report before deciding what to change next.

The runner deliberately ignores shell commands and code supplied in the issue body.
It only runs the fixed test command. This is a real remote execution bridge, but it
is not yet a general-purpose remote terminal or autonomous code-editing agent.

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
