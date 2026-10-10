"""Tests for safe credential separation in company workflow tools."""

import pytest

from brain.company.tools import GitHubCompanyTools


class FakeGateway:
    def __init__(self, name):
        self.name = name
        self.calls = []

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path.endswith("/issues"):
            return {"number": 42, "html_url": "https://github.com/owner/brain/issues/42"}
        if method == "GET" and path.endswith("/issues/42/comments"):
            return [{
                "body": (
                    "## Brain remote test run\n\n"
                    "**Result:** PASS\n"
                    "Workflow run: https://github.com/owner/brain/actions/runs/123"
                )
            }]
        raise AssertionError(f"Unexpected request: {method} {path}")


@pytest.mark.asyncio
async def test_verification_issue_uses_separate_pat_gateway():
    """PAT-created issue events can trigger the test workflow; GITHUB_TOKEN events cannot."""
    write_gateway = FakeGateway("actions-token")
    trigger_gateway = FakeGateway("pat")
    tools = GitHubCompanyTools(
        gateway=write_gateway,
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/brain", "brain/test-branch")

    assert result["executed"] is True
    assert result["status"] == "PASS"
    assert result["run_url"] == "https://github.com/owner/brain/actions/runs/123"
    assert len(write_gateway.calls) == 0
    assert [call[0] for call in trigger_gateway.calls] == ["POST", "GET"]
