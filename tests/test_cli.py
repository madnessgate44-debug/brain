import sys

import uvicorn

from brain.cli import main


def test_serve_uses_uvicorn_factory_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["brain", "--serve"])
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    main()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "brain.api.app:create_app"
    assert kwargs["factory"] is True
