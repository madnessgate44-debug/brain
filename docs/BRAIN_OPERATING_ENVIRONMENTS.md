# Brain operating environments

## Purpose

Brain has two separate execution environments. The internal environment is the current priority; external browser operations remain a separate capability and must not be treated as part of internal readiness.

## Environment A — Internal

**Flow:** operator → ChatGPT → Brain task/control logic → GitHub.

Scope:
- Interpret a request as a bounded task with explicit acceptance criteria.
- Inspect the actual repository and preserve existing project decisions.
- Propose changes on isolated branches rather than writing directly to the default branch.
- Run repository tests/build checks through GitHub Actions.
- Record a reviewable diff, workflow evidence, and an honest result report.
- Fail closed when credentials, permissions, or required evidence are missing.
- Require human review before merge or deployment.

Internal acceptance criteria:

| ID | Requirement | Evidence required |
|---|---|---|
| INT-01 | A phone-originated task can trigger a GitHub workflow | Issue event and workflow run URL |
| INT-02 | The workflow validates repository/branch input | Successful validation job; invalid inputs rejected |
| INT-03 | The target is checked out without persisted write credentials | Workflow configuration and successful checkout |
| INT-04 | Real tests or build checks execute | Logs with command result and exit code |
| INT-05 | Result is reported to the initiating issue | PASS/FAIL comment with workflow URL |
| INT-06 | Changes are isolated and reviewable | Dedicated branch and pull request diff |
| INT-07 | Missing provider or GitHub permissions stop work clearly | Sanitized failure/escalation; no false PASS |
| INT-08 | Merge/deployment are never inferred from a successful test | Explicit human approval gate |

## Environment B — External

**Flow:** operator → ChatGPT → Brain → browser.

Scope: authorized website navigation, research, page inspection, and browser actions. External execution requires its own browser/session controls and explicit approval for mutating actions. External permissions do not grant repository-write permission, and internal repository permissions do not authorize external account actions.

External acceptance is tracked separately and is not a prerequisite for declaring the internal task runner operational.

## Shared control rules

- A task has a stable identifier, objective, constraints, and acceptance criteria.
- A model's assertion is not execution evidence.
- Every success claim must cite actual test/run evidence.
- Retry loops are bounded; repeated quota or permission errors must not be disguised as progress.
- Secrets remain in runtime/GitHub Secrets and never enter task bodies, commits, artifacts, or comments.
- Repository changes stay on a dedicated branch until human review.
- Browser actions that submit, select, click, type, or otherwise change state require the applicable explicit approval.
- Failure reports identify the blocker and next safe action without leaking credentials.

## Current implementation boundary

The GitHub issue-triggered fixed test runner is an operational internal execution path. The separate AI-assisted software-company workflow is implemented in code, but must be considered **not end-to-end ready** until a live run proves that the configured model provider is available, GitHub write permissions work, changes are committed to an isolated branch, real checks pass, and a review pull request is created. A running workflow or a successful unit-test suite alone does not satisfy this full criterion.
