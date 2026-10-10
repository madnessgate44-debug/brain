"""Regression checks for explicit post-PR CI dispatch."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_python_ci_supports_explicit_dispatch():
    workflow = (WORKFLOWS / "brain-ci.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow


def test_company_workflow_dispatches_and_records_post_pr_checks():
    workflow = (WORKFLOWS / "brain-chat-company-workflow.yml").read_text(encoding="utf-8")
    assert "actions: write" in workflow
    assert "createWorkflowDispatch" in workflow
    assert "listWorkflowRuns" in workflow
    assert "brain-ci.yml" in workflow
    assert "tests.yml" in workflow
    assert "browser-runtime-smoke.yml" in workflow
    assert "POST_PR_VERIFICATION_FAILED" in workflow
    assert "GITHUB_TOKEN" in workflow


def test_dispatched_verification_workflows_support_manual_dispatch():
    for name in ("brain-ci.yml", "tests.yml", "browser-runtime-smoke.yml"):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in workflow
