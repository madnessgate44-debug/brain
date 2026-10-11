"""CORS policy tests for browser-facing API access."""

from fastapi.testclient import TestClient

from brain.api.app import create_app


def test_cors_allows_only_get_post_and_options(monkeypatch):
    origin = "https://frontend.example"
    monkeypatch.setenv("BRAIN_CORS_ORIGINS", origin)
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key-for-unit-tests-123")

    with TestClient(create_app()) as client:
        allowed = client.options(
            "/missions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert allowed.status_code == 200
        allowed_methods = {
            method.strip()
            for method in allowed.headers["access-control-allow-methods"].split(",")
        }
        assert {"GET", "POST", "OPTIONS"} <= allowed_methods
        assert "DELETE" not in allowed_methods
        assert "PUT" not in allowed_methods
        assert "PATCH" not in allowed_methods

        denied = client.options(
            "/missions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert denied.status_code == 400
