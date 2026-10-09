"""Tests for provider configuration and structured specialist outputs."""

import json

import httpx
import pytest

from brain.company.agent_runner import AgentOutputError, SpecialistAgentRunner
from brain.company.llm_provider import (
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)


@pytest.mark.asyncio
async def test_provider_fails_explicitly_when_credentials_are_missing():
    provider = OpenAICompatibleProvider(api_key="", model="", base_url="https://example.test/v1")
    with pytest.raises(ProviderConfigurationError, match="BRAIN_AI_API_KEY"):
        await provider.complete("system", "user")


@pytest.mark.asyncio
async def test_provider_calls_configured_compatible_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ready"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1",
        client=client,
    )
    try:
        result = await provider.complete("system role", "user task")
    finally:
        await client.aclose()

    assert result == "ready"
    assert requests[0].url.path == "/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    body = json.loads(requests[0].content)
    assert body["model"] == "test-model"


@pytest.mark.asyncio
async def test_specialist_rejects_missing_prerequisites_before_model_call():
    class NeverCalledProvider:
        async def complete(self, system_prompt, user_prompt):
            raise AssertionError("provider must not be called")

    runner = SpecialistAgentRunner(NeverCalledProvider())
    with pytest.raises(ValueError, match="missing required evidence"):
        await runner.run("developer", "Build the feature", {"acceptance_criteria": "AC-1"})


@pytest.mark.asyncio
async def test_specialist_rejects_non_structured_output():
    class FakeProvider:
        async def complete(self, system_prompt, user_prompt):
            return "Looks good, I built it!"

    runner = SpecialistAgentRunner(FakeProvider())
    evidence = {
        "product_brief": "brief",
        "acceptance_criteria": ["AC-1"],
        "screen_specification": "screens",
        "architecture": "architecture",
        "file_plan": ["src/main.py"],
    }
    with pytest.raises(AgentOutputError, match="valid JSON"):
        await runner.run("developer", "Build the feature", evidence)



@pytest.mark.asyncio
async def test_specialist_retries_malformed_json_once_then_accepts_valid_output():
    class FakeProvider:
        def __init__(self):
            self.calls = 0

        async def complete(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 1:
                return '{"status": "PASS", broken}'
            return json.dumps({
                "status": "PASS",
                "deliverables": {
                    "change_set": {"files": [{"path": "brain/a.py", "content": "pass\\n"}]},
                    "implementation_notes": "Implemented safely",
                },
                "findings": [],
                "blockers": [],
                "evidence_needed": [],
            })

    provider = FakeProvider()
    runner = SpecialistAgentRunner(provider)
    evidence = {
        "product_brief": "brief",
        "acceptance_criteria": ["AC-1"],
        "screen_specification": "backend flow contract",
        "architecture": "architecture",
        "file_plan": ["brain/a.py"],
    }
    result = await runner.run("developer", "Build the feature", evidence)
    assert result["status"] == "PASS"
    assert result["role"] == "developer"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_specialist_stops_after_one_failed_json_repair():
    class FakeProvider:
        def __init__(self):
            self.calls = 0

        async def complete(self, system_prompt, user_prompt):
            self.calls += 1
            return "not JSON"

    provider = FakeProvider()
    runner = SpecialistAgentRunner(provider)
    evidence = {
        "product_brief": "brief",
        "acceptance_criteria": ["AC-1"],
        "screen_specification": "backend flow contract",
        "architecture": "architecture",
        "file_plan": ["brain/a.py"],
    }
    with pytest.raises(AgentOutputError, match="after one repair attempt"):
        await runner.run("developer", "Build the feature", evidence)
    assert provider.calls == 2
