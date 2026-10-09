"""OpenAI-compatible model adapter for specialist agents.

Credentials are read at runtime and must never be stored in repository files.
The adapter intentionally exposes one narrow operation; workflow policy and tools
remain separate so a model response cannot bypass approval gates.
"""

from typing import Any

import httpx

from brain.company.settings import get_setting
from brain.company.escalation import WorkflowEscalationRequired


class ProviderConfigurationError(WorkflowEscalationRequired):
    """Raised when model-provider settings are missing or invalid."""

    def __init__(self, setting: str):
        super().__init__(
            "ai_provider_configuration_missing",
            "Required runtime setting " + setting + " is not configured; Brain cannot call its AI provider.",
            missing_settings=(setting,),
            suggested_action=(
                "Configure the named setting in the deployment/runtime secret manager, "
                "then resume the paused mission. Do not place credentials in chat or source control."
            ),
        )


class ModelProviderError(WorkflowEscalationRequired):
    """Raised when a provider request fails; raw response details are not exposed."""

    def __init__(self):
        super().__init__(
            "ai_provider_request_failed",
            "Brain's AI provider request failed. Check provider authentication, model access, quota, endpoint, and network connectivity.",
            suggested_action=(
                "Verify the provider configuration and account access in the runtime secret manager, "
                "then resume the paused mission. Raw provider responses are intentionally not recorded."
            ),
        )


class OpenAICompatibleProvider:
    """Call a configured OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 90.0,
        client: httpx.AsyncClient | None = None,
    ):
        # Google AI Studio's OpenAI-compatible endpoint is the default for Brain.
        # The credential itself is always injected at runtime; never hardcode it here.
        self.api_key = api_key or get_setting("BRAIN_AI_API_KEY")
        self.base_url = (base_url or get_setting(
            "BRAIN_AI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )).rstrip("/")
        self.model = model or get_setting("BRAIN_AI_MODEL", "gemini-2.5-flash")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the assistant's textual completion or fail explicitly."""
        if not self.api_key:
            raise ProviderConfigurationError("BRAIN_AI_API_KEY")
        if not self.model:
            raise ProviderConfigurationError("BRAIN_AI_MODEL")
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ModelProviderError()
            return content.strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelProviderError() from exc
        finally:
            if owns_client and client is not None:
                await client.aclose()
