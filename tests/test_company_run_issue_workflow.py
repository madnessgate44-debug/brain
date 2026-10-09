"""Tests for choosing a GitHub token with verified write access."""

import pytest

import brain.company.run_issue_workflow as workflow
from brain.company.github_gateway import GitHubGatewayError


class FakeGateway:
    def __init__(self, token, allowed_owner):
        self.token = token
        self.allowed_owner = allowed_owner

    async def verify_write_access(self, repository):
        if self.token == "no-write":
            raise GitHubGatewayError("write access denied")
        return {"repository": repository, "write_access": True}


@pytest.mark.asyncio
async def test_write_gateway_uses_primary_token_when_it_has_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_write_ready_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
    )

    assert gateway.token == "primary-write"


@pytest.mark.asyncio
async def test_write_gateway_falls_back_to_actions_token_when_primary_lacks_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_write_ready_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="no-write",
        actions_token="actions-write",
    )

    assert gateway.token == "actions-write"


@pytest.mark.asyncio
async def test_write_gateway_fails_before_model_calls_when_no_token_can_write(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured GitHub token has verified"):
        await workflow.build_write_ready_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="no-write",
            actions_token="no-write",
        )



@pytest.mark.asyncio
async def test_write_gateway_fails_when_no_tokens_are_configured(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured GitHub token has verified"):
        await workflow.build_write_ready_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="",
            actions_token="",
        )
