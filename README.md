# Brain V1 — Mission Orchestration System

Brain is a mission orchestration service with persistent mission state, an API,
event history, approval foundations, artifact storage, runtime recovery, and a
separate AI-assisted software-company workflow.

## Execution capabilities and boundaries

The standard mission worker is a deterministic document worker. It creates a
Markdown artifact named `mission-brief.md` from the mission title and objective
and records worker/artifact events. It does not perform web research, call an AI
model, edit repositories, or claim the mission's broader objective was achieved.

The software-company workflow is a separate, implemented code path under
`brain/company/` and `brain/runtime/`. It coordinates specialist roles, proposes
bounded repository changes on a `brain/...` branch, runs actual repository checks
through GitHub Actions, records evidence, and opens a pull request only after
the configured review gates pass. It does not merge pull requests or deploy.

**Important operational limitation:** code being present is not proof that a live
deployment is configured or that the full workflow has passed an end-to-end run.
The AI provider, GitHub credentials, control API, Actions runner, and repository
permissions must be configured and tested in the target environment.

## Architecture

- `brain/api/`: FastAPI endpoints, including the authenticated
  `POST /company-workflows` workflow-start endpoint.
- `brain/services/`: mission lifecycle and approval/artifact services.
- `brain/runtime/`: mission runtime and worker implementations.
- `brain/repositories/`: database access.
- `brain/storage/`: workspace and artifact storage.
- `brain/company/`: specialist role contracts, provider adapter, orchestration,
  bounded GitHub gateway, and release gates.
- `tests/`: automated tests.

Brain's database-backed mission model remains the source of truth; the system
does not replace it with a second JSON queue.

## Software-company workflow

The workflow defines nine specialist roles: product owner, UX/UI designer,
software architect, implementation engineer, independent code reviewer, QA
engineer, security auditor, customer advocate, and release manager. Their
prerequisites and release gates are defined in `brain/company/`.

The coordinator inspects the target repository, collects structured deliverables
from the specialist roles, commits a proposed change set to a dedicated
`brain/...` branch, runs repository checks through GitHub Actions, permits bounded
repair after review feedback, and opens a pull request only after required gates
pass. Role outputs and the workflow report are stored as mission artifacts. A
successful workflow pauses for human review; merge and deployment remain manual.

Configure these secrets through the runtime environment or deployment secret
manager, never by committing them to the repository:

- `BRAIN_AI_BASE_URL`: OpenAI-compatible chat-completions endpoint.
- `BRAIN_AI_MODEL`: model identifier.
- `BRAIN_AI_API_KEY`: provider credential.
- `BRAIN_GITHUB_OWNER`: only permitted GitHub owner.
- `BRAIN_GITHUB_TOKEN`: least-privilege token for the repository operations
  required by the workflow and test dispatch.
- `BRAIN_CONTROL_REPOSITORY`: repository hosting Brain's Actions runner, normally
  `madnessgate44-debug/brain` for this repository.
- `BRAIN_CONTROL_API_KEY`: long random secret protecting workflow start.

Start a workflow by sending an authenticated `POST /company-workflows` request
with a JSON body containing `title`, `objective`, and `repository`
(`owner/repository`). Supply the control secret in the `X-Brain-API-Key` header.
The API response provides the mission ID and status, event, and artifact endpoints.
The API must be running and reachable for this interface to be used.

Do not treat an agent's assertion as test evidence. QA must use the real check
runner's result, and release remains blocked if required evidence is missing.
The workflow is not complete until the pull request has been reviewed and the
resulting change has been accepted by a human.

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

Check `brain.api.app` and `.env.example` before deployment. Configure secrets
only through the runtime environment, never by committing them.

## Phone-first remote test runner

The fixed remote test runner can be dispatched from a phone without a terminal:

1. Open an issue in this repository.
2. Put the exact marker `/brain test` in the issue body.
3. Optionally add `repository: owner/repository` to target another public
   repository owned by the same GitHub account. If omitted, Brain is tested.
4. GitHub Actions detects supported Python or Node.js projects and runs their
   available test suite, build, or lint checks.
5. The workflow comments PASS/FAIL on the issue and attaches the report as an
   Actions artifact.
6. Review the workflow run and report before deciding what to change next.

The runner ignores shell commands and code supplied in issue text. It checks out
the target without persisting Git credentials and runs tests in a job with
read-only repository permissions; only the reporting job can write an issue
comment. Private-repository access requires a token limited to the required
repositories and read-only Contents permission for checkout. Never put tokens in
issue bodies or commit them to files.

This runner is a fixed test/build runner, not a general-purpose remote terminal.
The separate software-company workflow can propose code changes, but it requires
its own provider/GitHub configuration and a verified end-to-end deployment.

## First-milestone acceptance criteria

1. A mission can be created and started through the API.
2. The runtime writes a non-empty `mission-brief.md` artifact.
3. Event history records worker start and artifact creation.
4. A successful worker run settles the mission as completed.
5. Invalid worker inputs fail explicitly and are covered by tests.
6. The worker does not claim external research or AI actions it did not perform.

## Not yet established

- A production-hosted control API with durable uptime and monitoring.
- A successful live end-to-end software-company run against a real target
  repository, including provider calls, GitHub Actions test evidence, and PR
  creation.
- Durable distributed execution leases and cross-process duplicate-run protection.
- Production usage/cost monitoring and operational alerting.

Do not treat deployment-dependent capabilities as verified until their acceptance
checks have passed in the target environment.
