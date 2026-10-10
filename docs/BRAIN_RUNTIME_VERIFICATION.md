# Brain Runtime Verification & Operating Modes Report

This report provides a concise, evidence-backed summary of Brain's current operating modes, separating verified component capabilities from incomplete end-to-end specialist workflows and deployment readiness.

## 1. Successful Component & Runtime Checks

The following operating modes and components have been successfully verified via repository test suites and GitHub Actions:

- **Live Gemini API Secret Check:** Passed successfully ([Issue #49 Comment](https://github.com/madnessgate44-debug/brain/issues/49#issuecomment-6091820836)).
- **Mission-Free Conversational API (`POST /chat`):** Authenticated runtime check passed successfully and correctly did not create a mission ([Action Run 38012717500](https://github.com/madnessgate44-debug/brain/actions/runs/38012717500)).
- **Repository Test Suite:** Passed successfully with 111 tests passed and 1 skipped ([Action Run 38012614896](https://github.com/madnessgate44-debug/brain/actions/runs/38012614896)).
- **Acceptance Branch Remote Test Runner:** Passed successfully on the current acceptance branch ([Action Run 38034742396](https://github.com/madnessgate44-debug/brain/actions/runs/38034742396)).
- **Browser Runtime CI Smoke Test:** Passed successfully ([Action Run 38012685280](https://github.com/madnessgate44-debug/brain/actions/runs/38012685280)).

## 2. Incomplete Specialist End-to-End Workflow Status

**The full specialist workflow is NOT YET VERIFIED.** 

Recent execution attempts encountered gated validation stops:
- Failed at the customer-review gate ([Action Run 38034702378](https://github.com/madnessgate44-debug/brain/actions/runs/38034702378)).
- Failed at the architect gate following overly restrictive mission instructions ([Action Run 38034852137](https://github.com/madnessgate44-debug/brain/actions/runs/38034852137)).

*Important:* Do not claim that the full specialist workflow has passed, created a pull request, or executed unverified changes.

## 3. Production Deployment & Reachability

- **No Public Production API URL:** No public production URL or persistent hosting environment is currently configured in the repository.
- **Reachability Notice:** Although local and CI runtime checks for `/chat` and API endpoints pass, `/chat` and other API routes are not externally reachable until a persistent deployment exposes an HTTPS base URL and external health smoke tests are recorded.

## 4. GitHub Integration vs. Internal Test Runner

- **Direct GitHub Integration Reads & Operations:** Governed by `GitHubRepositoryGateway` and `GitHubCompanyTools`, handling structured repository inspection, bounded branch creation, and reviewable pull request proposals on dedicated `brain/...` branches without writing to the default branch or auto-merging.
- **Internal Issue-Triggered Test Runner:** Operates via GitHub Actions workflow detection upon recognizing the `/brain test` marker on issues, executing target project test suites and reporting results back via issue comments and artifacts.
