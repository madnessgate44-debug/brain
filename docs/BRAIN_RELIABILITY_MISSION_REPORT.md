# Brain Reliability and End-to-End Mission Audit Report

- Base Commit: `a8e8f78d2215c07081fb1c9a700d65ce01267fdd`
- Audit Date: 2026-10-11
- Scope: Main branch, open PRs, specialist evidence integrity, failure injection & recovery, workflow retry/resume behavior, and accurate terminal reporting.

## Requirements-to-Evidence / Gap Map

1. **Specialist Evidence Integrity**
   - *Requirement*: Ensure token resolution, web research collection, and source chunking adhere to strict size and permission boundaries.
   - *Evidence*: Verified in `brain/company/run_issue_workflow.py`, `brain/company/github_gateway.py`, and tested by `tests/test_company_run_issue_workflow.py` and `tests/test_company_github_gateway.py`.
   - *Status*: **PASS**

2. **Failure Injection & Recovery**
   - *Requirement*: Persist detailed diagnostic artifacts on worker failures and bootstrap anomalies.
   - *Evidence*: `scripts/write_bootstrap_failure_report.py`, `brain/services/recovery_service.py`, tested by `tests/test_bootstrap_failure_report.py` and `tests/test_recovery.py`.
   - *Status*: **PASS**

3. **Workflow Retry/Resume Behavior**
   - *Requirement*: Prevent concurrent race conditions via atomic git-ref locking and post-PR verification dispatch.
   - *Evidence*: `.github/workflows/brain-chat-company-workflow.yml`, tested by `tests/test_company_workflow_concurrency.py` and `tests/test_company_post_pr_dispatch.py`.
   - *Status*: **PASS**

4. **Accurate Terminal Reporting**
   - *Requirement*: Redact secrets from execution reports and render valid JSON/Markdown failure summaries.
   - *Evidence*: `tests/test_bootstrap_failure_report.py` validates secure redaction and robust repair paths.
   - *Status*: **PASS**

## Summary of Audit Findings
- All core operational blockers have robust regression test coverage.
- Multi-token fallback mechanism (`build_gateway`) successfully handles permission gaps.
- Shared lease locking (`brain-company-workflow-lock`) protects concurrent runs.
