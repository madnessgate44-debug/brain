"""OpenAI-compatible model adapter for specialist agents.

Credentials are read at runtime and must never be stored in repository files.
The adapter intentionally exposes one narrow operation; workflow policy and tools
remain separate so a model response cannot bypass approval gates.
"""

import asyncio
import os
from typing import Any
from urllib.parse import quote, urlparse

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
            "BRAIN_AI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )).rstrip("/")
        self.model = model or get_setting("BRAIN_AI_MODEL", "gemini-3.5-flash-lite")
        self.timeout_seconds = timeout_seconds
        self._client = client

    @staticmethod
    def _google_retry_delay(response: httpx.Response, fallback: float) -> float:
        """Read Google's retry guidance without exposing raw provider error payloads."""
        retry_after = response.headers.get("Retry-After", "").strip()
        try:
            if retry_after:
                return min(60.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
        try:
            payload = response.json()
            details = payload.get("error", {}).get("details", [])
            for detail in details if isinstance(details, list) else []:
                if not isinstance(detail, dict):
                    continue
                value = detail.get("retryDelay", "")
                if isinstance(value, str) and value.endswith("s"):
                    return min(60.0, max(0.0, float(value[:-1])))
        except (ValueError, TypeError, AttributeError):
            pass
        return min(60.0, max(0.0, fallback))

    async def _complete_google_native(
        self,
        system_prompt: str,
        user_prompt: str,
        client: httpx.AsyncClient,
    ) -> str:
        """Fallback to Google's native generateContent endpoint after compat 429."""
        parsed = urlparse(self.base_url)
        if parsed.hostname != "generativelanguage.googleapis.com" or not parsed.path.endswith("/openai"):
            raise ModelProviderError("Native Gemini fallback is not available for this provider endpoint.")
        native_base = self.base_url[: -len("/openai")]
        url = f"{native_base}/models/{quote(self.model, safe='-._')}:generateContent"
        response = None
        for attempt in range(3):
            try:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.1},
                    },
                )
            except httpx.TransportError:
                if attempt == 2:
                    raise
                await asyncio.sleep(float(2 ** attempt))
                continue

            if response.status_code == 429:
                if attempt == 0:
                    delay = self._google_retry_delay(response, fallback=2.0)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
            if response.status_code in {500, 502, 503, 504} and attempt < 2:
                delay = self._google_retry_delay(response, fallback=float(2 ** (attempt + 1)))
                await asyncio.sleep(delay)
                continue
            response.raise_for_status()
            break

        if response is None:
            raise ModelProviderError("Native Gemini request failed without a response.")
        data = response.json()
        candidates = data.get("candidates", [])
        candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
        candidate_content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        parts = candidate_content.get("parts", []) if isinstance(candidate_content, dict) else []
        text_parts = [
            part["text"] for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ] if isinstance(parts, list) else []
        if not text_parts:
            raise ModelProviderError("Native Gemini fallback returned no text completion.")
        return "\n".join(text_parts).strip()

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
            response = None
            for attempt in range(3):
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
                    continue

                is_google_compat = (
                    urlparse(self.base_url).hostname == "generativelanguage.googleapis.com"
                    and urlparse(self.base_url).path.endswith("/openai")
                )
                # A Google 429 commonly indicates project/model quota exhaustion.
                # Switch once to the native endpoint instead of spending two more
                # compatibility requests on the same exhausted quota.
                if response.status_code == 429 and is_google_compat:
                    return await self._complete_google_native(system_prompt, user_prompt, client)
                if response.status_code in {500, 502, 503, 504} and attempt < 2:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        delay = min(5.0, max(0.0, float(retry_after)))
                    except ValueError:
                        delay = float(2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        delay = min(5.0, max(0.0, float(retry_after)))
                    except ValueError:
                        delay = float(2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                break

            if response is None:
                raise ModelProviderError("Provider request failed without a response.")
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
