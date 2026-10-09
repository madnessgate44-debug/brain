# Brain Internal Workflow Runbook

This runbook provides concise instructions for operating Brain's internal workflows, remote test runner, preflight checks, required secrets, and Actions reports.

## 1. Required Secret Names

Configure the following secrets in your GitHub repository Actions settings or local `.env` file:
- `BRAIN_AI_API_KEY`: API key for the OpenAI-compatible AI provider (e.g., Gemini/OpenAI).
- `BRAIN_AI_BASE_URL`: Base URL for the AI provider chat completions endpoint.
- `BRAIN_AI_MODEL`: Model identifier (e.g., `gemini-2.5-flash`).
- `BRAIN_GITHUB_TOKEN`: Fine-grained GitHub personal access token with repository and issue permissions (Contents: write/read, Pull requests: write, Issues: write).
- `BRAIN_GITHUB_ACTIONS_TOKEN`: (Optional) Fallback token for GitHub Actions dispatch.
- `BRAIN_GITHUB_OWNER`: Permitted repository owner login (e.g., `madnessgate44-debug`).
- `BRAIN_CONTROL_REPOSITORY`: Repository hosting Brain's task runner (e.g., `madnessgate44-debug/brain`).
- `BRAIN_CONTROL_API_KEY`: Long random secret (at least 24 characters) protecting authenticated control endpoints.

## 2. Owner-Created `/brain simulate` Workflow

1. **Prerequisite Check**: Before making any model calls, Brain verifies that at least one configured GitHub token possesses repository push/write permission via a Git blob write-access preflight check. If write access is missing, execution halts immediately with a clear permission diagnostic.
2. **Triggering**: Open an issue in the target repository (owned by the allowed account) with the exact marker `/brain simulate` in the issue body, along with a `repository: owner/repository` target specification.
3. **Execution**: The workflow runs through the gated specialist pipeline (Product Owner -> UX/UI Designer -> Software Architect -> Implementation Engineer -> Independent Code Reviewer -> QA Engineer -> Security Auditor -> Customer Advocate -> Release Manager).
4. **Review PR**: Once all mandatory gates pass, Brain commits changes to an isolated `brain/...` branch and opens a review pull request. It **never** auto-merges or deploys.

## 3. Fixed `/brain test` Remote Runner

1. **Triggering**: Open an issue in the control repository containing the exact marker `/brain test` in the issue body.
2. **Targeting**: Optionally include `repository: owner/repository` and `branch: branch-name` in the issue body. If omitted, Brain tests itself.
3. **Execution**: GitHub Actions automatically checks out the target repository with read-only permissions, runs its test/build suite (Python or Node.js), comments PASS/FAIL on the issue, and uploads the full report as a workflow artifact.

## 4. `/brain ai-check` Preflight

- The AI provider secret check preflight workflow (`.github/workflows/ai-provider-secret-check.yml`) verifies that AI credentials and repository push/write permissions are correctly configured and valid prior to initiating autonomous company workflows or model calls.

## 5. Finding Actions Run Reports

1. Navigate to your GitHub repository's **Actions** tab.
2. Select the relevant workflow run (e.g., *Brain Remote Test Runner* or *AI Provider Secret Check*).
3. Inspect the job summary and download the attached **Artifacts** report for complete execution logs and test results.
