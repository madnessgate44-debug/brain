"""Client for Brain's own REST API.

The connector tools call the same FastAPI endpoints every other client uses, so the
connector adds no second execution path and no duplicated business logic. Calls go to
`BRAIN_PUBLIC_BASE_URL` over HTTP; when the connector is served by the same process,
that is the process itself.
"""

from __future__ import annotations

import httpx

from brain.connector.settings import connector_base_url, connector_key


class BrainClient:
    """Call Brain's API, authenticated with the control key."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key or connector_key()
        self.base_url = (base_url or connector_base_url()).rstrip("/")
        self._transport = transport

    def _headers(self) -> dict:
        return {"X-Brain-API-Key": self.api_key}

    async def _request(self, method: str, path: str, json_body=None):
        async with httpx.AsyncClient(
            base_url=self.base_url, transport=self._transport, timeout=120.0
        ) as client:
            response = await client.request(
                method, path, headers=self._headers(), json=json_body
            )
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

    async def chat(self, message: str) -> str:
        """Send one user message and return the model reply text."""
        data = await self._request(
            "POST", "/chat", {"messages": [{"role": "user", "content": message}]}
        )
        return data.get("reply", "")

    async def create_mission(self, title: str, objective: str) -> dict:
        return await self._request(
            "POST", "/missions", {"title": title, "objective": objective}
        )

    async def start_mission(self, mission_id: str) -> dict:
        return await self._request("POST", f"/missions/{mission_id}/start")

    async def get_mission(self, mission_id: str) -> dict:
        return await self._request("GET", f"/missions/{mission_id}")

    async def list_missions(self, limit: int = 20) -> dict:
        return await self._request("GET", f"/missions?limit={int(limit)}")

    async def list_artifacts(self, mission_id: str) -> list:
        return await self._request("GET", f"/missions/{mission_id}/artifacts")
