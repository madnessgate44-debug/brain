"""Sanitized provider-error diagnostics tests."""

import httpx
import pytest

from brain.company.llm_provider import ModelProviderError, OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_gemini_429_reports_safe_quota_identifiers_without_raw_error_text(monkeypatch):
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
        if request.url.path.endswith(":generateContent"):
            return httpx.Response(429, json=error_body, request=request)
        return httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"error": {"status": "RESOURCE_EXHAUSTED"}},
            request=request,
        )

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="gemini-3.5-flash-lite",
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
