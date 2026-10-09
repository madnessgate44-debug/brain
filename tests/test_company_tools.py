"""Regression tests for GitHub-backed company workflow tools."""

import pytest

from brain.company.tools import GitHubCompanyTools


class FakeGateway:
    def __init__(self):
        self.apply_calls = []
        self.requests = []
        self.comment_body = (
            "## Brain remote test run\n\n"
            "**Result:** EXECUTION_ERROR\n"
            "**Workflow run:** https://github.com/example/brain/actions/runs/123"
        )

    async def apply_change_set(self, **kwargs):
        self.apply_calls.append(kwargs)
        return {
            "repository": kwargs["repository"],
            "branch": kwargs["branch_name"],
            "diff": "FILE: src/app.py\n+changed",
            "changed_files": [item["path"] for item in kwargs["change_set"]["files"]],
        }

    async def _request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        if method == "POST":
            return {"number": 9, "html_url": "https://github.com/example/brain/issues/9"}
        if method == "GET" and path.endswith("/comments"):
            return [{"body": self.comment_body}]
        raise AssertionError(f"Unexpected request: {method} {path}")


@pytest.mark.asyncio
async def test_repair_changes_extend_the_same_branch():
    gateway = FakeGateway()
    tools = GitHubCompanyTools(gateway=gateway, control_repository="owner/brain")

    first = await tools.apply_change_set(
        {"summary": "Initial implementation", "files": [{"path": "src/a.py", "content": "a"}]},
        "owner/app",
    )
    second = await tools.apply_change_set(
        {"summary": "Repair implementation", "files": [{"path": "src/b.py", "content": "b"}]},
        "owner/app",
    )

    assert first["branch"] == second["branch"]
    assert gateway.apply_calls[0]["update_branch"] is False
    assert gateway.apply_calls[1]["update_branch"] is True
    assert gateway.apply_calls[0]["branch_name"] == gateway.apply_calls[1]["branch_name"]


@pytest.mark.asyncio
async def test_check_runner_execution_error_is_not_reported_as_executed():
    gateway = FakeGateway()
    tools = GitHubCompanyTools(
        gateway=gateway,
        control_repository="owner/brain",
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/app", "brain/mission-123")

    assert result["status"] == "FAIL"
    assert result["executed"] is False
    assert result["execution_error"] is True
    assert result["run_url"] == "https://github.com/example/brain/actions/runs/123"
