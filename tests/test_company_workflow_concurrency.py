"""Regression checks for the shared company-workflow lease."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "brain-chat-company-workflow.yml"


def test_company_workflows_share_an_atomic_lease_before_model_execution():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "brain-company-workflow-lock" in text
    assert "Acquire shared specialist workflow lock" in text
    assert "createRef" in text
    assert "acquired_at=" in text
    assert text.index("Acquire shared specialist workflow lock") < text.index(
        "Run Brain's specialist workflow"
    )


def test_company_workflow_releases_lease_even_after_failure():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Release shared specialist workflow lock" in text
    assert "if: always() && steps.mission_lock.outputs.acquired == 'true'" in text
    assert "deleteRef" in text
    assert "staleMs = 60 * 60 * 1000" in text


def test_waiting_for_shared_lease_is_bounded_and_reported():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "timeoutMs = 35 * 60 * 1000" in text
    assert "timeout-minutes: 90" in text
    assert "Timed out waiting for the shared specialist-workflow lease" in text
