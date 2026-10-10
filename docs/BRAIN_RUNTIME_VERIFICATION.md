# Brain Runtime Verification

This document compiles verified evidence from the Brain repository and successful GitHub Actions runs.

## Summary of Verified Execution

1. **Direct GitHub Repository Operations:** Verified via `brain/company/github_gateway.py` and `brain/company/tools.py` for bounded repository inspection, isolated branch creation under the `brain/` prefix, change-set commits, and pull request creation without direct writes to the default branch, automatic merging, or deployment.
2. **Gemini-backed Specialist Workflow:** Verified via `brain/company/agent_runner.py`, `brain/company/engine.py`, and `brain/company/llm_provider.py`. The workflow coordinates nine specialist roles through structured JSON contracts with strict parser validation, bounded developer repair cycles, and mandatory release gates (independent review, actual test runner execution, security audit, and customer review).
3. **Authenticated Mission-Free `POST /chat` Runtime Check:** Implemented in `brain/api/routes/chat.py`. Requires an authenticated request with an `X-Brain-API-Key` header where the configured key must contain at least 24 characters (per the invariant enforced in merged PR #62). Bounded conversation context is validated (1-16 messages, 1-6000 characters per message, ending with a user message) and processed directly by the OpenAI-compatible provider adapter without creating missions, enqueuing workflows, or writing to repositories.
4. **Read-Only Amina Audit:** Verified via read-only capability planning (`brain/company/mission_capabilities.py`) and issue-driven specialist run execution (`brain/company/run_issue_workflow.py`), producing evidence-bounded analysis reports without claiming unexecuted tests or modifying repository files.

## Production Deployment Distinction

- **Code/CI Verification vs. Production Deployment:** Successful local/CI test runs and automated GitHub Actions verification confirm that all backend logic, validation rules, security gates, and endpoints operate correctly in test/CI environments.
- **External Reachability:** No production API URL is configured in this repository. The `POST /chat` and control endpoints are **not** externally reachable via a persistent public deployment until an explicit HTTPS base URL is configured and external health/chat smoke tests are executed against that persistent environment.

## Security & Safety Invariants

- **Control Key Length:** `BRAIN_CONTROL_API_KEY` minimum length of 24 characters is strictly enforced.
- **Scope Guard:** No automated merging, default branch writing, or deployment occurs.
- **No Secret Commit:** Credentials and tokens are read exclusively from runtime environment variables or local `.env` configuration and are never committed to repository files.
