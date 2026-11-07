"""Serverless entrypoint.

Vercel detects a FastAPI project by looking for a module-level ASGI `app` in one of
its conventional paths (this file is one). It serves the same application as the
uvicorn entrypoint `brain.api.app:create_app`.
"""

from brain.api.app import create_app

app = create_app()
