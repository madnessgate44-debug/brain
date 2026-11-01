"""Serverless entrypoint.

Vercel (and similar hosts) look for a module-level ASGI `app`. This file serves the
REST API and the MCP connector from one app, exactly like the uvicorn entrypoint
`brain.connector.app:create_combined_app`.
"""

from brain.connector.app import create_combined_app

app = create_combined_app()
