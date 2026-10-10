# Brain Runtime Verification and Evidence Log

This document records verified execution evidence from the Brain repository and successful GitHub Actions runs. It establishes what has been tested and verified in code/CI while explicitly distinguishing local and CI verification from a persistent production deployment.

---

## Summary of Verification Scope

| Verification Area | Status | Evidence Source |
|-------------------|--------|-----------------|
| **Direct GitHub Repository Operations** | Verified | GitHub REST API integration (`brain/company/github_gateway.py`), test suite (`tests/`), and Actions workflows |
| **Gemini-Backed Specialist Workflow** | Verified | OpenAI-compatible provider adapter (`brain/company/llm_provider.py`), specialist agent runner (`brain/company/agent_runner.py`), and workflow engine (`brain/company/engine.py`) |
| **Authenticated Mission-Free `POST /chat`** | Verified | FastAPI chat endpoint (`brain/api/routes/chat.py`) and automated API tests |
| **Read-Only Amina Audit** | Verified | Capability planning (`brain/company/mission_capabilities.py`) and issue workflow runner (`brain/company/run_issue_workflow.py`) |

---

## 1. Direct GitHub Repository Operations

- **Implementation:** `brain/company/github_gateway.py` implements a least-surprise GitHub REST client using `httpx`. It validates repository owners against `BRAIN_GITHUB_OWNER`, enforces safe path verification (rejecting absolute paths, parent directory traversal, and `.git/` modifications), and operates exclusively on isolated feature branches prefixed with `brain/`.
- **Safety Guarantees:** 
  - Never writes to the default branch.
  - Never merges pull requests.
  - Never executes arbitrary issue-supplied shell commands.
- **GitHub Actions Integration:** Workflows such as `.github/workflows/brain-task-runner.yml` and `.github/workflows/brain-chat-company-workflow.yml` execute test suites, run preflights, and post structured reports as issue comments with read-only repository permissions except where the reporting job comments on issues.

---

## 2. Gemini-Backed Specialist Workflow

- **Provider Adapter:** `brain/company/llm_provider.py` connects to OpenAI-compatible endpoints, including Google's Gemini API via `https://generativelanguage.googleapis.com/v1beta/openai`, with automatic fallback to native `generateContent` on quota (429) responses.
- **Specialist Roles:** `brain/company/roles.py` defines nine distinct specialist roles (Product Owner, UX/UI Designer, Software Architect, Implementation Engineer, Independent Code Reviewer, QA Engineer, Security Auditor, Customer Advocate, and Release Manager) with mandatory independent review gates.
- **Execution Engine:** `brain/company/engine.py` enforces strict role ordering, bounded implementation repair cycles (up to 2 attempts), and tool-backed test execution evidence before a pull request can be proposed.

---

## 3. Authenticated Mission-Free `POST /chat` Runtime Check

- **Implementation:** `brain/api/routes/chat.py` provides an authenticated conversational endpoint that interacts directly with the configured model provider without creating a mission, enqueuing a background workflow, or mutating a repository.
- **Security & Validation:**
  - Requires `X-Brain-API-Key` matching `BRAIN_CONTROL_API_KEY` (minimum 24 characters, verified using `hmac.compare_digest`).
  - Validates conversation bounds (1 to 16 messages, maximum 6,000 characters per message).
  - Requires the final message in the transcript to be from the `user` role.
- **Verification Status:** Verified via local test runner and FastAPI app factory tests. 

> **Important Distinction:** Successful code and CI test execution for `POST /chat` proves that the endpoint logic, authentication check, and provider integration function correctly. **It does not by itself make the endpoint externally reachable.** A persistent production deployment requires running the FastAPI application behind an HTTPS server with environment secrets configured and an allocated public URL. No production API URL is configured in this repository; do not claim that `/chat` is externally reachable until deployment and external smoke testing are performed.

---

## 4. Read-Only Amina Audit

- **Capability Planning:** `brain/company/mission_capabilities.py` inspects issue objectives to classify requested operations into `read_only` or `mutating` modes prior to credential checks.
- **Read-Only Behavior:** When no affirmative repository mutation intent (such as fix, repair, refactor, implement, create, or update) is detected, Brain defaults to `read_only` mode. It collects bounded repository snapshots and invokes the configured model to generate a comprehensive, evidence-bounded audit report without altering source files, running tests, or opening pull requests.

---

## Compliance and Safety Notes

1. **No Secrets:** This documentation and the repository test suites contain no credentials, tokens, or live API keys.
2. **No Unsupported Claims:** Success claims are strictly bounded to repository tests, CI action logs, and tool-verified execution outputs.
3. **Deployment Separation:** Code verification and CI checks are distinct from production hosting. No production deployment URL exists in this repository.
