# Brain Operating Modes

Brain supports three primary operating modes, explicitly separating fully implemented code and automated workflows from unconfigured production deployments.

---

## 1. Direct GitHub Repository Operations

### Overview
Mode 1 provides direct, safe remote repository operations executed via GitHub Actions workflow definitions (such as `.github/workflows/brain-task-runner.yml`) and GitHub issue triggers.

### Mechanics & Verification
- **Trigger:** An issue opened by the repository owner containing the exact marker `/brain test` and optional `repository: owner/name` targeting a public repository owned by the same account.
- **Execution:** GitHub Actions automatically detects Python or Node.js projects, checks out the repository with read-only permissions (unless configured with fine-grained secrets), and runs the actual test/build/lint suite.
- **Output:** Comments PASS/FAIL status directly on the triggering GitHub issue and attaches the full execution report as a GitHub Actions workflow artifact.
- **Safety Guardrails:** Arbitrary shell commands supplied in issue bodies are ignored. Credentials are never persisted, and only the reporting job has permission to comment on the issue.

---

## 2. Gemini-Backed Specialist Software Workflow

### Overview
Mode 2 coordinates a rigorous, nine-role specialist software workflow (`brain/company/`) backed by an OpenAI-compatible model provider (such as Gemini).

### Mechanics & Verification
- **Trigger:** An authenticated `POST /company-workflows` request containing `title`, `objective`, and `repository` (`owner/repository`), secured by the `X-Brain-API-Key` header (`BRAIN_CONTROL_API_KEY`).
- **Pipeline:** `CompanyWorkflowEngine` runs specialist roles in order: Product Owner, UX/UI Designer, Software Architect, Implementation Engineer, Independent Code Reviewer, QA Engineer, Security Auditor, Customer Advocate, and Release Manager.
- **Repository Integration:** The implementation engineer produces a structured change set. `GitHubRepositoryGateway` commits these changes exclusively to an isolated `brain/...` branch (never writing to the default branch).
- **Verification & Review:** Real test checks are dispatched via GitHub Actions. After all mandatory quality gates pass, a reviewable pull request is opened.
- **Scope Boundary:** **No automatic merge or deployment occurs.** The workflow pauses for human review and stores all role outputs and reports as mission artifacts.

---

## 3. Authenticated Mission-Free POST /chat API

### Overview
Mode 3 provides an authenticated, stateless conversational endpoint (`POST /chat` in `brain/api/routes/chat.py`) for direct model interactions.

### Mechanics & Verification
- **Header & Payload:** Requires `X-Brain-API-Key: <BRAIN_CONTROL_API_KEY>` and a JSON body containing validated message turns (`messages` array with `user` and `assistant` roles; final message must be from `user`; limit of 16 messages and 6,000 characters per message).
- **Execution:** Invokes `OpenAICompatibleProvider` directly without creating database missions, enqueuing background workers, or mutating any repository.
- **Implementation vs. Deployment Distinction:** 
  - **Implemented Code:** The endpoint is fully implemented in FastAPI, validated by tests, and operational when run locally or in CI with valid `BRAIN_AI_API_KEY`, `BRAIN_AI_MODEL`, and `BRAIN_AI_BASE_URL` settings.
  - **Production Deployment:** Successful local/CI runtime tests **do not** make the endpoint externally reachable. A persistent deployment must run the application with required environment variables and expose its HTTPS base URL. Because no production deployment URL is configured in this repository, the endpoint must not be treated as externally reachable until deployment and external health/chat smoke tests are successfully recorded.

---

## Summary of Guardrails
- No secrets, private data, or token contents are ever logged or committed.
- All destructive or mutating capabilities require explicit authentication, signature verification, and owner approval.
- Scope boundaries strictly prohibit automatic merges, default-branch writes, and deployments.
