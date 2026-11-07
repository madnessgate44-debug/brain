"""The serverless (Vercel) entrypoint must expose a module-level ASGI app."""

import importlib.util
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]


def test_index_py_exists_at_repo_root():
    assert (ROOT / "index.py").is_file()


def test_index_exposes_fastapi_app():
    spec = importlib.util.spec_from_file_location("vercel_index", ROOT / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.app, FastAPI)


def test_entrypoint_does_not_pull_the_heavy_developer_backend():
    # The serverless bundle must stay lean; openhands-sdk lives only in the
    # company developer backend, not on the API request path.
    assert "openhands" not in (ROOT / "index.py").read_text()
