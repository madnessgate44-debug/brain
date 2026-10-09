import httpx
import pytest

from brain.company.llm_provider import ModelProviderError, OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_provider_retries_transient_503_then_returns_completion(monkeypatch):
    calls = 0
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "0"}, request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "generated code"}}]},
            request=request,
        )

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test-model",
            client=client,
        )
        result = await provider.complete("system", "user")

    assert result == "generated code"
    assert calls == 2
    assert delays == [0.0]


@pytest.mark.asyncio
async def test_provider_stops_after_three_transient_server_errors(monkeypatch):
    calls = 0

    async def no_sleep(_delay):
        return None

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request)

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test-model",
            client=client,
        )
        with pytest.raises(ModelProviderError, match="503"):
            await provider.complete("system", "user")

    assert calls == 3
