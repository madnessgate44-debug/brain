import httpx
import pytest

from brain.company.llm_provider import (
    ModelProviderError,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)


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
        with pytest.raises(ModelProviderError, match="HTTP 503"):
            await provider.complete("system", "user")

    assert calls == 3


@pytest.mark.asyncio
async def test_google_compatible_429_honors_retry_delay_without_native_fallback(monkeypatch):
    calls = 0
    delays = []
    paths = []

    async def no_sleep(delay):
        delays.append(delay)

    def handler(request):
        nonlocal calls
        calls += 1
        paths.append(request.url.path)
        if calls == 1:
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
            json={"choices": [{"message": {"content": "recovered"}}]},
            request=request,
        )

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="test-model",
            client=client,
        )
        result = await provider.complete("system", "user")

    assert result == "recovered"
    assert calls == 2
    assert delays == [7.0]
    assert paths == ["/v1beta/openai/chat/completions"] * 2


@pytest.mark.asyncio
async def test_google_compatible_429_stops_after_bounded_attempts(monkeypatch):
    calls = 0
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            json={
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [{"retryDelay": "1s"}],
                }
            },
            request=request,
        )

    monkeypatch.setattr("brain.company.llm_provider.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="test-model",
            client=client,
        )
        with pytest.raises(ModelProviderError, match="HTTP 429"):
            await provider.complete("system", "user")

    assert calls == 3
    assert delays == [1.0, 1.0]


def test_provider_requires_explicit_model_and_keeps_compatible_endpoint(monkeypatch):
    monkeypatch.setattr(
        "brain.company.llm_provider.get_setting",
        lambda name, default="": default,
    )
    provider = OpenAICompatibleProvider(api_key="test-key")
    assert provider.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert not provider.model


@pytest.mark.asyncio
async def test_provider_fails_before_network_call_when_model_missing(monkeypatch):
    monkeypatch.setattr(
        "brain.company.llm_provider.get_setting",
        lambda name, default="": default,
    )
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.invalid/v1",
    )
    with pytest.raises(ProviderConfigurationError, match="BRAIN_AI_MODEL is not configured"):
        await provider.complete("system", "user")


def test_provider_normalizes_gemini_v1beta_to_openai_compatible_path():
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="test-model",
    )
    assert provider.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_company_workflow_does_not_select_a_hardcoded_model_fallback():
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "brain"
        / "company"
        / "run_issue_workflow.py"
    ).read_text(encoding="utf-8")
    assert 'model=os.environ.get("BRAIN_AI_MODEL")' in source
    assert "gemini-3.5-flash-lite" not in source
