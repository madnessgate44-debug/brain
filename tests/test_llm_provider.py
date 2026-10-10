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


@pytest.mark.asyncio
async def test_provider_falls_back_to_native_gemini_immediately_after_compatibility_429(monkeypatch):
    compatibility_calls = 0
    native_calls = 0

    async def no_sleep(_delay):
        return None

    def handler(request):
        nonlocal compatibility_calls, native_calls
        if request.url.path.endswith(":generateContent"):
            native_calls += 1
            payload = request.read().decode("utf-8")
            assert "systemInstruction" in payload
            return httpx.Response(
                200,
                json={
                    "candidates": [{
                        "content": {"parts": [{"text": "native Gemini result"}]}
                    }]
                },
                request=request,
            )
        compatibility_calls += 1
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
            model="gemini-2.5-flash",
            client=client,
        )
        result = await provider.complete("system instructions", "write code")

    assert result == "native Gemini result"
    assert compatibility_calls == 1
    assert native_calls == 1


@pytest.mark.asyncio
async def test_native_gemini_retries_429_using_google_retry_delay(monkeypatch):
    compatibility_calls = 0
    native_calls = 0
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    def handler(request):
        nonlocal compatibility_calls, native_calls
        if request.url.path.endswith(":generateContent"):
            native_calls += 1
            if native_calls == 1:
                return httpx.Response(
                    429,
                    json={
                        "error": {
                            "status": "RESOURCE_EXHAUSTED",
                            "details": [{"retryDelay": "7s"}],
                        }
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"candidates": [{
                    "content": {"parts": [{"text": "recovered"}]}
                }]},
                request=request,
            )
        compatibility_calls += 1
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
        result = await provider.complete("system", "user")

    assert result == "recovered"
    assert compatibility_calls == 1
    assert native_calls == 2
    assert delays == [7.0]


@pytest.mark.asyncio
async def test_native_gemini_stops_after_three_rate_limited_attempts(monkeypatch):
    native_calls = 0

    async def no_sleep(_delay):
        return None

    def handler(request):
        nonlocal native_calls
        if request.url.path.endswith(":generateContent"):
            native_calls += 1
            return httpx.Response(
                429,
                json={"error": {"status": "RESOURCE_EXHAUSTED"}},
                request=request,
            )
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
        with pytest.raises(ModelProviderError, match="429"):
            await provider.complete("system", "user")

    assert native_calls == 2


def test_provider_defaults_to_configured_gemini_endpoint(monkeypatch):
    """A Gemini key works without an additional endpoint/model override."""
    monkeypatch.setattr(
        "brain.company.llm_provider.get_setting",
        lambda name, default="": default,
    )

    provider = OpenAICompatibleProvider(api_key="test-key")

    assert provider.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert provider.model == "gemini-3.5-flash-lite"
