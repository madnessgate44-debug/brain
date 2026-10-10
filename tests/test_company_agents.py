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


@pytest.mark.asyncio
async def test_specialist_prompt_uses_real_newlines_in_role_contract():
    """Role-specific system prompts use line breaks, not literal backslash-n text."""
    from brain.company.roles import ROLE_BY_KEY

    class CapturingProvider:
        def __init__(self):
            self.system_prompts = []

        async def complete(self, system_prompt, user_prompt):
            self.system_prompts.append(system_prompt)
            role = ROLE_BY_KEY["ux_designer"]
            return json.dumps({
                "status": "PASS",
                "deliverables": {key: "verified test value" for key in role.deliverables},
                "findings": [],
                "blockers": [],
                "evidence_needed": [],
            })

    provider = CapturingProvider()
    runner = SpecialistAgentRunner(provider)
    await runner.run(
        "ux_designer",
        "Specify backend interaction behavior.",
        {"product_brief": "brief", "acceptance_criteria": ["AC-1"]},
    )

    prompt = provider.system_prompts[0]
    assert "\nScope applicability rule:" in prompt
    assert "\\nScope applicability rule:" not in prompt
    assert "software company.\nYour responsibility:" in prompt
    assert "\\nYour responsibility:" not in prompt


@pytest.mark.asyncio
async def test_customer_advocate_scope_rule_covers_non_ui_work():
    """Documentation/test-only missions must not be blocked for lacking visual design."""
    from brain.company.roles import ROLE_BY_KEY

    class CapturingProvider:
        def __init__(self):
            self.system_prompts = []

        async def complete(self, system_prompt, user_prompt):
            self.system_prompts.append(system_prompt)
            role = ROLE_BY_KEY["customer_advocate"]
            return json.dumps({
                "status": "PASS",
                "deliverables": {key: "not applicable to documentation-only scope" for key in role.deliverables},
                "findings": [],
                "blockers": [],
                "evidence_needed": [],
            })

    provider = CapturingProvider()
    runner = SpecialistAgentRunner(provider)
    await runner.run(
        "customer_advocate",
        "Create a documentation-only runtime verification report.",
        {
            "product_brief": "Record evidence accurately",
            "acceptance_criteria": ["No unsupported claims"],
            "screen_specification": "Not applicable: documentation-only work",
            "change_set": {"files": [{"path": "docs/report.md", "content": "Evidence log"}]},
            "test_results": {"status": "PASS", "executed": True},
        },
    )

    prompt = provider.system_prompts[0]
    assert "documentation-only" in prompt
    assert "test-only" in prompt
    assert "Do not invent UI work" in prompt
