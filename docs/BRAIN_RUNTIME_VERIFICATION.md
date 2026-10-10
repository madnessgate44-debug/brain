# Brain Runtime & Verification Report

This document records verified evidence from the `madnessgate44-debug/brain` repository and successful GitHub Actions runs as of October 2026.

## Summary of Verified Operations

1. **Direct GitHub Repository Operations**
   - Operations executed through the connected GitHub integration (via `GitHubRepositoryGateway`) successfully validate repository metadata, read source files under strict path and size constraints, inspect tree snapshots, and commit changes on isolated `brain/...` branches without writing to the default branch.

2. **Gemini-Backed Specialist Workflow**
   - The software-company specialist workflow orchestrates nine specialist roles (Product Owner, UX/UI Designer, Software Architect, Implementation Engineer, Independent Code Reviewer, QA Engineer, Security Auditor, Customer Advocate, Release Manager) backed by the Gemini-compatible model adapter (`OpenAICompatibleProvider`).
   - **Execution History Note:** Earlier runs encountered blocks at the security gate (due to control-key length requirements) and the customer-review gate. Following the merge of PR #62, which enforces the 24-character control-key minimum for `BRAIN_CONTROL_API_KEY`, subsequent gated runs successfully satisfy all mandatory release gates, culminating in the creation of a reviewable pull request.

3. **Authenticated Mission-Free POST /chat Runtime Check**
   - The `POST /chat` endpoint provides direct conversational access via the configured model provider without creating a mission or writing to a repository.
   - **Invariants Enforced:** Requires the `X-Brain-API-Key` header matching `BRAIN_CONTROL_API_KEY`. As of PR #62, `BRAIN_CONTROL_API_KEY` must contain at least 24 characters (returning HTTP 503 if misconfigured or HTTP 401 on authentication failure).

4. **Read-Only Amina Audit**
   - Read-only missions inspect the target repository snapshot and generate evidence-bounded analysis reports without modifying source files or executing mutation tools.

## Code/CI Verification vs. Persistent Production Deployment

- **Code & CI Verification:** Fully verified through automated unit tests (`pytest`), local FastAPI startup checks, and GitHub Actions workflow runs.
- **Production Deployment:** No production API URL is configured in this repository. Consequently, endpoints such as `/chat` and `/company-workflows` must **not** be claimed as externally reachable over the public internet until a persistent deployment with required environment variables and an external health/smoke test is established and recorded.

## Security & Safety Guardrails

- No secrets, API keys, or tokens are committed or documented.
- Automatic merging and deployment are strictly forbidden; all workflows culminate in a reviewable pull request awaiting human review.
