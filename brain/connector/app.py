"""One ASGI app that serves the Brain REST API and the MCP connector together.

The owner wants a single URL and a single key. Requests to `/mcp` go to the MCP
connector; every other path goes to the REST API. Both applications run their own
startup/shutdown inside one lifespan so one process and one deployment serve both.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from brain.api.app import create_app
from brain.connector import create_connector_app

logger = logging.getLogger("brain.connector.app")

MCP_MOUNT_PATH = "/mcp"


class CombinedApp:
    """Dispatch `/mcp` to the connector and all other paths to the REST API."""

    def __init__(self, api_app, connector_app):
        self.api_app = api_app
        self.connector_app = connector_app

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope_type == "http" and scope.get("path", "").startswith(MCP_MOUNT_PATH):
            inner = dict(scope)
            remainder = scope["path"][len(MCP_MOUNT_PATH):]
            inner["path"] = remainder or "/"
            inner["root_path"] = scope.get("root_path", "") + MCP_MOUNT_PATH
            await self.connector_app(inner, receive, send)
            return

        await self.api_app(scope, receive, send)

    async def _handle_lifespan(self, scope, receive, send):
        stack = AsyncExitStack()
        try:
            await stack.enter_async_context(self.api_app.router.lifespan_context(self.api_app))
            await stack.enter_async_context(
                self.connector_app.starlette_app.router.lifespan_context(
                    self.connector_app.starlette_app
                )
            )
        except Exception as exc:  # noqa: BLE001 - report any startup failure to the server
            logger.exception("Combined app startup failed")
            await stack.aclose()
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            return

        await send({"type": "lifespan.startup.complete"})
        while True:
            message = await receive()
            if message["type"] == "lifespan.shutdown":
                await stack.aclose()
                await send({"type": "lifespan.shutdown.complete"})
                return


def create_combined_app() -> CombinedApp:
    """Build the combined REST + MCP application."""
    api_app = create_app()
    connector_app = create_connector_app(api_app=api_app)
    return CombinedApp(api_app, connector_app)
