"""Brain MCP connector.

One URL and one key that any chat client with custom-connector support can add:
ChatGPT, Claude, Gemini, OpenHands, and any other MCP client.

The connector speaks the Model Context Protocol over HTTP (streamable HTTP), so the
client discovers Brain's tools at runtime instead of the owner wiring each one by hand.
Authentication is a single Bearer key, the same `BRAIN_CONTROL_API_KEY` the REST API
uses, so the owner has one key to remember.
"""

from __future__ import annotations

import hmac
import logging

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from brain.connector.client import BrainClient
from brain.connector.settings import connector_base_url, connector_key
from brain.company.settings import get_setting

logger = logging.getLogger("brain.connector.mcp")

SERVER_NAME = "brain"


def build_mcp(api_app=None) -> FastMCP:
    """Build the MCP server and register Brain's tools.

    When `api_app` is supplied the tools call it in-process, so a single deployment
    serves both the REST API and the connector with no self-directed network hop.
    """
    transport = httpx.ASGITransport(app=api_app) if api_app is not None else None
    base_url = "http://brain.local" if api_app is not None else None

    def make_client() -> BrainClient:
        return BrainClient(transport=transport, base_url=base_url)

    server = FastMCP(
        SERVER_NAME,
        instructions=(
            "Brain is a mission orchestration service. Use these tools to chat with the "
            "configured model, create and run missions, and read their status, events and "
            "artifacts. Missions run bounded work and produce artifacts; a mission does not "
            "claim work it did not do."
        ),
        stateless_http=True,
        # Served at the process root; the combined app strips the "/mcp" prefix before
        # dispatching here. The public HTTPS host is not known at build time, so
        # host/origin checks are disabled and the Bearer key is the guard.
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @server.tool()
    async def brain_chat(message: str) -> str:
        """Send a message to Brain's configured model and return its reply."""
        client = make_client()
        return await client.chat(message)

    @server.tool()
    async def brain_create_mission(title: str, objective: str) -> dict:
        """Create a mission with a title and objective. Returns the new mission."""
        client = make_client()
        return await client.create_mission(title, objective)

    @server.tool()
    async def brain_start_mission(mission_id: str) -> dict:
        """Start a created mission so its runtime executes."""
        client = make_client()
        return await client.start_mission(mission_id)

    @server.tool()
    async def brain_get_mission(mission_id: str) -> dict:
        """Get one mission's current phase and status."""
        client = make_client()
        return await client.get_mission(mission_id)

    @server.tool()
    async def brain_list_missions(limit: int = 20) -> dict:
        """List recent missions, newest first."""
        client = make_client()
        return await client.list_missions(limit)

    @server.tool()
    async def brain_list_artifacts(mission_id: str) -> list:
        """List the artifacts a mission produced."""
        client = make_client()
        return await client.list_artifacts(mission_id)

    return server


def _bearer_token() -> str:
    """Read the expected Bearer key for the connector."""
    return connector_key()


class _BearerAuthMiddleware:
    """Reject connector requests that do not carry the Brain control key.

    Plain ASGI middleware so it wraps the MCP transport without depending on a
    particular Starlette/FastMCP version.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        expected = _bearer_token()
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}

        if not expected or len(expected) < 24:
            await _send_json(send, 503, "Connector disabled: BRAIN_CONTROL_API_KEY is not configured.")
            return

        supplied = ""
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if not supplied:
            supplied = headers.get("x-brain-api-key", "").strip()

        if not supplied or not hmac.compare_digest(supplied, expected):
            await _send_json(send, 401, "Invalid Brain control key.")
            return

        await self.app(scope, receive, send)


async def _send_json(send, status_code: int, detail: str) -> None:
    import json

    body = json.dumps({"detail": detail}).encode()
    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class Connector:
    """The connector's ASGI callable plus the underlying Starlette app.

    `call` carries the Bearer-key check; `starlette_app` exposes the router so the
    combined app can run the MCP session manager's lifespan.
    """

    def __init__(self, call, starlette_app, server):
        self.call = call
        self.starlette_app = starlette_app
        self.server = server

    async def __call__(self, scope, receive, send):
        await self.call(scope, receive, send)


def create_connector_app(api_app=None) -> Connector:
    """Build the MCP connector wrapped in Bearer-key auth."""
    server = build_mcp(api_app=api_app)
    mcp_app = server.streamable_http_app()
    guarded = _BearerAuthMiddleware(mcp_app)
    return Connector(guarded, mcp_app, server)


def connector_status() -> dict:
    """Report connector readiness without exposing the key value."""
    key = connector_key()
    return {
        "server": SERVER_NAME,
        "base_url": connector_base_url(),
        "key_configured": bool(key) and len(key) >= 24,
        "model": get_setting("BRAIN_AI_MODEL", ""),
    }
