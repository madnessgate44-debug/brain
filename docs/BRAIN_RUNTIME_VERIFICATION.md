# Brain Runtime Verification Report

This operational report documents verified runtime checks, historical failures, and deployment boundaries for Brain maintainers using verified repository facts and direct execution evidence.

## 1. Verified Component Checks

- **Gemini API Check:** [GitHub Issue #49 Comment](https://github.com/madnessgate44-debug/brain/issues/49#issuecomment-6091820836)
- **Mission-Free `/chat` Check:** [GitHub Actions Run 38012717500](https://github.com/madnessgate44-debug/brain/actions/runs/38012717500)
- **Automated Test Suite:** [GitHub Actions Run 38012614896](https://github.com/madnessgate44-debug/brain/actions/runs/38012614896)
- **Browser Runtime Smoke Test:** [GitHub Actions Run 38012685280](https://github.com/madnessgate44-debug/brain/actions/runs/38012685280)

## 2. Component Checks vs. Full Specialist Workflow

Individual component checks (such as the Gemini API integration, mission-free chat endpoint, test runner, and browser smoke test) validate isolated subsystems or endpoints independently.

In contrast, the **full specialist workflow** is a multi-role orchestration pipeline coordinated by the software-company engine (`brain/company/engine.py`). A full specialist simulation is successful only when it:
1. Reaches and passes every mandatory gate across all nine specialist roles.
2. Executes real repository checks via GitHub Actions.
3. Creates a reviewable pull request on an isolated branch.

Read-only audits or skipped workflows do not constitute successful full execution.

## 3. Historical Simulation Failures and Corrective Fixes

Previous mutation attempts encountered and resolved three distinct defects:
- **Customer-Review Decision-Format Defect:** Specialist output contained prose instead of a strict enum value (`PASS`, `NEEDS_WORK`, `BLOCKED`). Resolved in [PR #73](https://github.com/madnessgate44-debug/brain/pull/73).
- **Temporary Rate-Limit Failure:** Upstream quota or rate limiting during model completions ([Actions Run 38035279284](https://github.com/madnessgate44-debug/brain/actions/runs/38035279284)). Handled via exponential backoff and native Gemini fallback adapters.
- **Workflow-Token PR-Permission Failure:** The default GITHUB_TOKEN lacked explicit `pull-requests:write` permission on the control repository ([Actions Run 38035578614](https://github.com/madnessgate44-debug/brain/actions/runs/38035578614)). Resolved via [PR #75](https://github.com/madnessgate44-debug/brain/pull/75), [PR #76](https://github.com/madnessgate44-debug/brain/pull/76), and PR #79 routing fixes.

## 4. Operational Limitations and Hosting Status

- **No Public Production API URL:** No public production API URL is verified or deployed.
- **No Persistent Browser Hosting:** Persistent browser hosting or live multi-device session bridging is not verified in production.

## 5. Verification Summary

All reported checks are backed by verifiable GitHub Actions runs and issue comments. This report changes only `docs/BRAIN_RUNTIME_VERIFICATION.md` without merging, deploying, or altering default-branch code.
