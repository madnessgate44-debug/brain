"""Connector status endpoint.

Lets the owner (or a monitor) confirm the connector is ready and where it lives,
without ever exposing the key value.
"""

from fastapi import APIRouter

from brain.connector import connector_status

router = APIRouter(tags=["connector"])


@router.get("/connector")
async def connector_info() -> dict:
    """Report connector readiness, its URL, and the MCP path."""
    status = connector_status()
    return {
        **status,
        "mcp_path": "/mcp",
        "transport": "streamable-http",
    }
