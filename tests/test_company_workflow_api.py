"""API tests for the protected company workflow entry point."""

from fastapi.testclient import TestClient

from brain.api.app import create_app


def test_company_workflow_endpoint_is_disabled_without_control_key(monkeypatch):
    monkeypatch.delenv("BRAIN_CONTROL_API_KEY", raising=False)
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as client:
        response = client.post(
            "/company-workflows",
            json={
                "title": "Build feature",
                "objective": "Implement the requested feature",
                "repository": "owner/repository",
            },
        )
    assert response.status_code == 503
    assert "BRAIN_CONTROL_API_KEY" in response.json()["detail"]


def test_company_workflow_endpoint_rejects_wrong_control_key(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "expected-control-key-for-tests-123456")
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as client:
        response = client.post(
            "/company-workflows",
            headers={"X-Brain-API-Key": "wrong-secret"},
            json={
                "title": "Build feature",
                "objective": "Implement the requested feature",
                "repository": "owner/repository",
            },
        )
    assert response.status_code == 401
