# Brain Runtime and Workflow Verification

This document records verified evidence from the repository and successful GitHub Actions runs for Brain V1. It clearly distinguishes local code/CI verification from persistent production deployments.

## 1. Direct GitHub Repository Operations
- **Definition:** Operations performed through the connected GitHub integration (such as repository inspection, branch creation, commit creation, and pull request opening) using `BRAIN_GITHUB_TOKEN` and `BRAIN_GITHUB_OWNER`.
- **Status:** Verified in CI and test runner runs. Distinct from Brain's internal issue-triggered test runner (`/brain test`).

## 2. Gemini-backed Specialist Workflow & History
- **Specialist Roles:** Product owner, UX/UI designer, software architect, implementation engineer, independent code reviewer, QA engineer, security auditor, customer advocate, and release manager.
- **Execution History & Gate Status:**
  - Prior attempts experienced blocking at specific gates: one stopped at the security audit gate due to control-key length requirements; another stopped at the customer-review gate.
  - These invariants are now fully enforced by merged PR #62 (requiring `BRAIN_CONTROL_API_KEY` to be at least 24 characters).
  - The complete specialist workflow has achieved verified branch creation and real test-runner PASS status in successful GHA runs.

## 3. Authenticated Mission-Free POST /chat Runtime Check
- **Endpoint:** `POST /chat` (implemented in `brain/api/routes/chat.py`).
- **Authentication & Security:** Requires header `X-Brain-API-Key` matching `BRAIN_CONTROL_API_KEY` (enforced minimum length of 24 characters per PR #62).
- **Behavior:** Directly invokes the configured OpenAI-compatible model provider (e.g., Gemini via `https://generativelanguage.googleapis.com/v1beta/openai`) without creating a mission, enqueuing a workflow, or writing to a repository.

## 4. Read-Only Amina Audit
- **Scope:** Read-only inspection and evaluation mode.
- **Status:** Verified for generating evidence-bounded audit reports without executing mutations or modifying repository files.

## 5. Production Deployment Distinction
- **Deployment Status:** No production API URL is configured in this repository.
- **Reachability:** Local and CI runtime checks verify FastAPI functionality and endpoint correctness, but do **not** imply that `/chat` or other endpoints are externally reachable over the public internet until a persistent production deployment is explicitly configured and validated with an external smoke test.
