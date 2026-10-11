"""Sanitized provider-error diagnostics tests."""

from pathlib import Path

import httpx
import pytest

from brain.company.llm_provider import ModelProviderError, OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_compatible_429_reports_safe_quota_identifiers_without_raw_error_text(monkeypatch):
    async def no_sleep(_delay):
        return None

    error_body = {
        "error": {
            "status": "RESOURCE_EXHAUSTED",
            "message": "private provider message that must not be exposed",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                            "quotaId": "GenerateRequestsPerMinutePerProjectPerModel",
                        }
                    ],
                }
            ],
        }
    }

    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(429, json=error_body, request=request)

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="test-model",
            client=client,
        )
        with pytest.raises(ModelProviderError) as error:
            await provider.complete("system", "user")

    message = str(error.value)
    assert "HTTP 429" in message
    assert "provider_status=RESOURCE_EXHAUSTED" in message
    assert "quota_metric=generativelanguage.googleapis.com/generate_content_free_tier_requests" in message
    assert "quota_id=GenerateRequestsPerMinutePerProjectPerModel" in message
    assert "private provider message" not in message


def test_ai_provider_secret_check_uses_the_production_compatible_endpoint():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "ai-provider-secret-check.yml"
    ).read_text(encoding="utf-8")
    assert "vars.BRAIN_AI_MODEL" in workflow
    assert "secrets.BRAIN_AI_BASE_URL" in workflow
    assert "/chat/completions" in workflow
    assert '"Authorization": "Bearer " + api_key' in workflow
    assert "generateContent" not in workflow
    assert "x-goog-api-key" not in workflow
    assert "types: [opened, edited]" not in workflow
