"""CORS regression coverage for the hosted Brain frontend."""

from fastapi.testclient import TestClient

from brain.api.app import create_app


def test_hosted_brain_frontend_origin_can_preflight_authenticated_api(monkeypatch):
    origin = "https://madnessgate44-debug.github.io"
    monkeypatch.delenv("BRAIN_CORS_ORIGINS", raising=False)
    app = create_app()

    with TestClient(app) as client:
        response = client.options(
            "/chat",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-brain-api-key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
