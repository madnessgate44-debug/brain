"""Static security checks for issue-triggered GitHub workflows."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_owner_triggered_workflows_require_owner_as_event_sender():
    workflow_paths = [
        ".github/workflows/brain-chat-company-workflow.yml",
        ".github/workflows/brain-chat-runtime-check.yml",
        ".github/workflows/ai-provider-secret-check.yml",
    ]
    for relative_path in workflow_paths:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "github.event.issue.user.login == github.repository_owner" in content, relative_path
        assert "github.event.sender.login == github.repository_owner" in content, relative_path


def test_task_runner_checks_issue_author_and_event_sender_in_condition_and_payload():
    content = (ROOT / ".github/workflows/brain-task-runner.yml").read_text(encoding="utf-8")
    assert "github.event.sender.login == github.repository_owner" in content
    assert "github.event.sender.login == 'github-actions[bot]'" in content
    assert 'sender = (event.get("sender") or {}).get("login", "")' in content
    assert "sender.casefold() == owner.casefold()" in content
    assert "brain-internal-verification: true" in content
