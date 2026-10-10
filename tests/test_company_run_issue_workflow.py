"""Tests for capability-aware target repository credential resolution."""

import pytest

import brain.company.run_issue_workflow as workflow
from brain.company.github_gateway import GitHubGatewayError
from brain.company.mission_capabilities import plan_capabilities


class FakeGateway:
    def __init__(self, token, allowed_owner):
        self.token = token
        self.allowed_owner = allowed_owner

    async def verify_write_access(self, repository):
        if self.token == "no-write":
            raise GitHubGatewayError("write access denied")
        return {"repository": repository, "write_access": True}

    async def inspect_repository(self, repository, max_files=80):
        if self.token == "no-read":
            raise GitHubGatewayError("read access denied")
        return {"repository": repository, "default_branch": "main"}


@pytest.mark.asyncio
async def test_write_gateway_uses_primary_token_when_it_has_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("fix defects"),
    )

    assert gateway.token == "primary-write"


@pytest.mark.asyncio
async def test_write_gateway_falls_back_to_actions_token_when_primary_lacks_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="no-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("fix defects"),
    )

    assert gateway.token == "actions-write"


@pytest.mark.asyncio
async def test_gateway_reports_detailed_failures_when_no_token_has_required_capability(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured credential satisfied") as error:
        await workflow.build_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="no-write",
            actions_token="no-write",
            capability_plan=plan_capabilities("fix defects"),
        )

    assert "BRAIN_GITHUB_TOKEN" in str(error.value)
    assert "write access denied" in str(error.value)


@pytest.mark.asyncio
async def test_gateway_reports_when_no_credentials_are_configured(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured credential satisfied") as error:
        await workflow.build_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="",
            actions_token="",
            capability_plan=plan_capabilities("fix defects"),
        )

    assert "No GitHub credential is configured" in str(error.value)


@pytest.mark.asyncio
async def test_read_only_mission_uses_read_access_without_write_preflight(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="read-only-token",
        actions_token="",
        capability_plan=plan_capabilities("Audit and report findings"),
    )

    assert gateway.token == "read-only-token"



@pytest.mark.asyncio
async def test_control_repository_write_prefers_scoped_actions_token(monkeypatch):
    """Use the workflow's contents:write token for writes to its own repository."""
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/brain",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "actions-write"


@pytest.mark.asyncio
async def test_external_repository_write_keeps_primary_token_first(monkeypatch):
    """Do not try the control-repository GITHUB_TOKEN first for another repository."""
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/other-project",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "primary-write"


@pytest.mark.asyncio
async def test_control_repository_actions_token_uses_read_preflight_then_actual_write(monkeypatch):
    """Do not reject GITHUB_TOKEN solely because repo metadata reports push=false."""
    class ActionsTokenMetadataGateway(FakeGateway):
        async def verify_write_access(self, repository):
            raise GitHubGatewayError("metadata reports push=false")

    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", ActionsTokenMetadataGateway)

    gateway = await workflow.build_gateway(
        repository="owner/brain",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "actions-write"
