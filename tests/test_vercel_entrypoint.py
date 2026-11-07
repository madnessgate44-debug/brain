"""The serverless (Vercel) entrypoint must expose a module-level ASGI app.

Since the MCP connector landed, `index.py` serves the REST API *and* the
connector from one combined ASGI app, so the module-level `app` is the
`CombinedApp` callable rather than a bare `FastAPI` instance. It must still be a
valid ASGI callable, and it must still serve the REST API (`create_app`).
"""

import importlib.util
from pathlib import Path

from brain.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def _load_entrypoint():
    spec = importlib.util.spec_from_file_location("vercel_index", ROOT / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_index_py_exists_at_repo_root():
    assert (ROOT / "index.py").is_file()


def test_index_exposes_an_asgi_app():
    module = _load_entrypoint()
    app = module.app
    assert callable(app)
    # An ASGI app is a three-argument callable (scope, receive, send).
    assert app.__call__.__code__.co_argcount >= 3


def test_index_serves_the_rest_api():
    module = _load_entrypoint()
    api_app = module.app.api_app if hasattr(module.app, "api_app") else module.app
    assert isinstance(api_app, type(create_app()))


def test_entrypoint_does_not_pull_the_heavy_developer_backend():
    # The serverless bundle must stay lean; openhands-sdk lives only in the
    # company developer backend, not on the API request path.
    assert "openhands" not in (ROOT / "index.py").read_text()
