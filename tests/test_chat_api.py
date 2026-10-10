"""Tests for the mission-free Brain chat endpoint."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app
from brain.company.llm_provider import ModelProviderError, ProviderConfigurationError


class FakeProvider:
    """Deterministic model provider for API contract tests."""

    model = "test-model"
    calls: list[tuple[str, str]] = []

    def __init__(self):
        self.calls = []

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return "Verified test reply."


@pytest.fixture
def chat_client(monkeypatch):
    """Create an authenticated API client with test-only configuration."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key")
    monkeypatch.setenv("BRAIN_AI_API_KEY", "test-model-key")
    monkeypatch.setenv("BRAIN_AI_MODEL", "test-model")
    monkeypatch.setenv("BRAIN_AI_BASE_URL", "https://example.invalid/v1")
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_chat_returns_model_reply_without_creating_mission(chat_client, monkeypatch):
    """Ordinary chat uses the provider and does not enqueue a mission."""
    import brain.api.routes.chat as chat_route

    provider = FakeProvider()
    monkeypatch.setattr(chat_route, "OpenAICompatibleProvider", lambda: provider)

    before = chat_client.get("/missions").json()["total"]
    response = chat_client.post(
        "/chat",
        headers={"X-Brain-API-Key": "test-control-key"},
        json={
            "messages": [
                {"role": "user", "content": "Remember that I am auditing Brain."},
                {"role": "assistant", "content": "Understood."},
                {"role": "user", "content": "What are we doing?"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Verified test reply.",
        "model": "test-model",
        "messages_in_context": 3,
    }
    assert len(provider.calls) == 1
    system_prompt, transcript = provider.calls[0]
    assert "chat-only" in system_prompt
    assert "Remember that I am auditing Brain." in transcript
    assert "What are we doing?" in transcript
    assert chat_client.get("/missions").json()["total"] == before


def test_chat_rejects_invalid_control_key(chat_client):
    """The chat endpoint is not anonymously accessible."""
    response = chat_client.post(
        "/chat",
        headers={"X-Brain-API-Key": "wrong-key"},
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 401


def test_chat_requires_latest_message_from_user(chat_client):
    """A request cannot ask Brain to continue an assistant-only transcript."""
    response = chat_client.post(
        "/chat",
        headers={"X-Brain-API-Key": "test-control-key"},
        json={"messages": [{"role": "assistant", "content": "A previous reply"}]},
    )
    assert response.status_code == 422


def test_chat_hides_provider_errors(chat_client, monkeypatch):
    """Provider failures return sanitized errors rather than credentials or raw payloads."""
    import brain.api.routes.chat as chat_route

    class BrokenProvider:
        model = "test-model"

        async def complete(self, system_prompt: str, user_prompt: str) -> str:
            raise ModelProviderError("private provider details")

    monkeypatch.setattr(chat_route, "OpenAICompatibleProvider", BrokenProvider)
    response = chat_client.post(
        "/chat",
        headers={"X-Brain-API-Key": "test-control-key"},
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "The configured model provider did not return a usable response."
    )
    assert "private provider details" not in response.text


def test_chat_reports_missing_provider_configuration(chat_client, monkeypatch):
    """Missing provider configuration is reported without calling the provider."""
    import brain.api.routes.chat as chat_route

    class UnconfiguredProvider:
        model = ""

        async def complete(self, system_prompt: str, user_prompt: str) -> str:
            raise ProviderConfigurationError("secret config detail")

    monkeypatch.setattr(chat_route, "OpenAICompatibleProvider", UnconfiguredProvider)
    response = chat_client.post(
        "/chat",
        headers={"X-Brain-API-Key": "test-control-key"},
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The configured model provider is unavailable or incomplete."
    )
    assert "secret config detail" not in response.text
