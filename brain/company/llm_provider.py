"""OpenAI-compatible model adapter for specialist agents.

Credentials are read at runtime and must never be stored in repository files.
The adapter intentionally exposes one narrow operation; workflow policy and tools
remain separate so a model response cannot bypass approval gates.
"""

import os
from typing import Any

import httpx

from brain.company.settings import get_setting


class ProviderConfigurationError(RuntimeError):
    """Raised when model-provider settings are missing or invalid."""


class ModelProviderError(RuntimeError):
    """Raised when the model provider fails or returns an unusable response."""


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
        self.api_key = api_key or get_setting("BRAIN_AI_API_KEY")
        self.base_url = (base_url or get_setting(
            "BRAIN_AI_BASE_URL", "https://api.openai.com/v1"
        )).rstrip("/")
        self.model = model or get_setting("BRAIN_AI_MODEL")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the assistant's textual completion or fail explicitly."""
        if not self.api_key:
            raise ProviderConfigurationError(
                "BRAIN_AI_API_KEY is not configured; no agent was executed."
            )
        if not self.model:
            raise ProviderConfigurationError(
                "BRAIN_AI_MODEL is not configured; no agent was executed."
            )
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
                raise ModelProviderError("Provider returned an empty completion.")
            return content.strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelProviderError(f"Model provider request failed: {exc}") from exc
        finally:
            if owns_client and client is not None:
                await client.aclose()
