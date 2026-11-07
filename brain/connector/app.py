"""One ASGI app that serves the Brain REST API and the MCP connector together.

The owner wants a single URL and a single key. Requests to `/mcp` go to the MCP
connector; every other path goes to the REST API. Both applications run their own
startup/shutdown inside one lifespan so one process and one deployment serve both.
"""

from __future__ import annotations

import asyncio
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
        self._stack = None
        self._start_lock = asyncio.Lock()
        self._mcp_task = None
        self._mcp_started = None
        self._mcp_stop = None

    @property
    def started(self) -> bool:
        return self._stack is not None

    async def startup(self) -> None:
        """Run both applications' startup once."""
        if self._stack is not None:
            return
        async with self._start_lock:
            if self._stack is not None:
                return
            stack = AsyncExitStack()
            await stack.enter_async_context(self.api_app.router.lifespan_context(self.api_app))

            # The MCP session manager runs a task group that must be entered and exited in
            # the same task, so its lifespan runs in a dedicated long-lived task rather than
            # in whichever task happened to trigger startup.
            self._mcp_started = asyncio.Event()
            self._mcp_stop = asyncio.Event()
            self._mcp_task = asyncio.create_task(self._run_mcp_lifespan())
            await self._mcp_started.wait()

            self._stack = stack

    async def _run_mcp_lifespan(self) -> None:
        try:
            async with self.connector_app.starlette_app.router.lifespan_context(
                self.connector_app.starlette_app
            ):
                self._mcp_started.set()
                await self._mcp_stop.wait()
        except Exception:  # noqa: BLE001 - surface startup failure to the awaiting caller
            logger.exception("MCP connector startup failed")
            self._mcp_started.set()
            raise

    async def shutdown(self) -> None:
        """Run both applications' shutdown."""
        if self._stack is None:
            return
        stack, self._stack = self._stack, None
        if self._mcp_stop is not None:
            self._mcp_stop.set()
        if self._mcp_task is not None:
            try:
                await self._mcp_task
            except Exception:  # noqa: BLE001 - shutdown must not mask the original error
                logger.exception("MCP connector shutdown failed")
            self._mcp_task = None
        await stack.aclose()

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        # Serverless hosts may deliver requests without running the ASGI lifespan,
        # so start on first use when startup has not already run.
        if not self.started:
            await self.startup()

        if scope_type == "http" and scope.get("path", "").startswith(MCP_MOUNT_PATH):
            inner = dict(scope)
            remainder = scope["path"][len(MCP_MOUNT_PATH):]
            inner["path"] = remainder or "/"
            inner["root_path"] = scope.get("root_path", "") + MCP_MOUNT_PATH
            await self.connector_app(inner, receive, send)
            return

        await self.api_app(scope, receive, send)

    async def _handle_lifespan(self, scope, receive, send):
        try:
            await self.startup()
        except Exception as exc:  # noqa: BLE001 - report any startup failure to the server
            logger.exception("Combined app startup failed")
            await self.shutdown()
            await send({"type": "lifespan.startup.failed", "message": str(exc)})
            return

        await send({"type": "lifespan.startup.complete"})
        while True:
            message = await receive()
            if message["type"] == "lifespan.shutdown":
                await self.shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return


def create_combined_app() -> CombinedApp:
    """Build the combined REST + MCP application."""
    api_app = create_app()
    connector_app = create_connector_app(api_app=api_app)
    return CombinedApp(api_app, connector_app)
