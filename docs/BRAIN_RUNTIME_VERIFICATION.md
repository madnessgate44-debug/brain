# Brain Runtime and Workflow Verification Report

This operational report documents verified execution results, past failure investigations, and workflow criteria for Brain maintainers.

## 1. Verified Component Checks

- **Gemini API Check:** [Issue #49 Comment](https://github.com/madnessgate44-debug/brain/issues/49#issuecomment-6091820836)
- **Mission-Free /chat Check:** [GitHub Actions Run 38012717500](https://github.com/madnessgate44-debug/brain/actions/runs/38012717500)
- **Automated Test Suite:** [GitHub Actions Run 38012614896](https://github.com/madnessgate44-debug/brain/actions/runs/38012614896)
- **Browser Runtime Smoke Test:** [GitHub Actions Run 38012685280](https://github.com/madnessgate44-debug/brain/actions/runs/38012685280)

## 2. Individual Component Checks vs. Full Specialist Workflow

- **Individual Component Checks:** Test isolated capabilities (such as model conversation, automated test execution, or browser tasks) independently without running the complete multi-role specialist pipeline.
- **Full Specialist Workflow:** A simulation is successful **only** if it reaches every mandatory gate, runs real repository checks via GitHub Actions, and creates a reviewable pull request. Neither a read-only audit nor a skipped workflow constitutes successful full execution.

## 3. Historical Failures and Remediation

- **Customer-Review Decision-Format Defect:** [Attempt Run 38035265565](https://github.com/madnessgate44-debug/brain/actions/runs/38035265565) failed due to strict validation expectations on decision formats; fixed in [Pull Request #73](https://github.com/madnessgate44-debug/brain/pull/73).
- **Temporary Rate-Limit Failure:** [Attempt Run 38035279284](https://github.com/madnessgate44-debug/brain/actions/runs/38035279284) encountered upstream model provider rate limits (HTTP 429), addressed via retry and native fallback logic.
- **Workflow-Token PR-Permission Failure:** [Attempt Run 38035578614](https://github.com/madnessgate44-debug/brain/actions/runs/38035578614) failed because the workflow token could not create a PR. [PR #76](https://github.com/madnessgate44-debug/brain/pull/76) separated content-write and PR credentials in code, but the configured PAT also lacks PR-creation permission; the permission blocker remains unresolved inside the Actions workflow.

## 4. Production and Hosting Boundaries

- No public production API URL or persistent browser hosting environment is verified in this repository.


## 5. Latest Full-Specialist Acceptance Attempt

- **Run:** [38035949405](https://github.com/madnessgate44-debug/brain/actions/runs/38035949405)
- **Result:** The specialist workflow reached the final pull-request creation step after the mandatory reviews and remote test runner completed, but the run failed with HTTP 403: `Resource not accessible by personal access token` from the GitHub pull-request API.
- **Interpretation:** This is not a 100% successful end-to-end simulation. The implementation, review gates, and remote checks progressed, but Brain's configured PR credential lacks the required permission. The repository setting that allows the workflow token to create PRs is also not verified as enabled.
- **Required remediation:** Grant the configured PAT pull-request write access or enable the repository Actions setting that allows `GITHUB_TOKEN` to create pull requests. Re-run the full specialist acceptance workflow afterward.
