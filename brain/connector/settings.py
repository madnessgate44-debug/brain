"""Connector settings and defaults.

Kept separate from the MCP server so the same values can be reused by tests and by
any future connector transport (for example an OpenAPI/actions endpoint) without
importing the MCP library.
"""

from __future__ import annotations

from brain.company.settings import get_setting

DEFAULT_CONNECTOR_BASE_URL = "http://127.0.0.1:8000"


def connector_key() -> str:
    """The single Bearer key every connector client uses."""
    return get_setting("BRAIN_CONTROL_API_KEY")


def connector_base_url() -> str:
    """Public base URL the connector is served from, used for status and docs."""
    return get_setting("BRAIN_PUBLIC_BASE_URL", DEFAULT_CONNECTOR_BASE_URL).rstrip("/")
