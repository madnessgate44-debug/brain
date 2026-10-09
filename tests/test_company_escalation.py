"""Tests for safe escalation behavior when Brain lacks required capabilities."""

import httpx
import pytest

from brain.company.escalation import WorkflowEscalationRequired
from brain.company.github_gateway import GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider, ProviderConfigurationError


@pytest.mark.asyncio
async def test_missing_ai_key_becomes_a_safe_escalation(monkeypatch):
    monkeypatch.setattr("brain.company.llm_provider.get_setting", lambda name, default="": "")
    provider = OpenAICompatibleProvider(api_key=None, model="test-model")

    with pytest.raises(ProviderConfigurationError) as caught:
        await provider.complete("system", "user")

    request = caught.value.to_request("mission-test")
    assert request["blocker_code"] == "ai_provider_configuration_missing"
    assert request["missing_settings"] == ["BRAIN_AI_API_KEY"]
    assert request["secret_values_included"] is False
    assert "api_key" not in str(request).lower() or "BRAIN_AI_API_KEY" in str(request)
    assert "test-secret-value" not in str(request)


def test_missing_github_token_becomes_a_safe_escalation():
    gateway = GitHubRepositoryGateway(
        token="",
        allowed_owner="example-owner",
        api_base_url="https://example.test",
    )

    with pytest.raises(WorkflowEscalationRequired) as caught:
        gateway._validate_repository("example-owner/project")

    request = caught.value.to_request("mission-test")
    assert request["blocker_code"] == "github_token_missing"
    assert request["missing_settings"] == ["BRAIN_GITHUB_TOKEN"]
    assert request["secret_values_included"] is False


@pytest.mark.asyncio
async def test_github_auth_failure_does_not_expose_raw_response_or_token():
    secret = "test-token-must-never-leak"

    def handler(request):
        return httpx.Response(401, text=f"bad token {secret}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = GitHubRepositoryGateway(
        token=secret,
        allowed_owner="example-owner",
        api_base_url="https://example.test",
        client=client,
    )
    try:
        with pytest.raises(WorkflowEscalationRequired) as caught:
            await gateway._request("GET", "/repos/example-owner/project")
    finally:
        await client.aclose()

    request = caught.value.to_request("mission-test")
    assert request["blocker_code"] == "github_auth_or_permission_failed"
    assert secret not in str(request)
    assert secret not in str(caught.value)
