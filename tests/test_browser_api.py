"""Tests for browser API endpoints and authentication guards."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app
from brain.company.settings import get_setting


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "secret-control-key-with-sufficient-length-24+")
    app = create_app()
    return TestClient(app)


def test_browser_task_unauthorized(client):
    response = client.post("/browser/tasks", json={"title": "test", "objective": "test", "actions": [{"op": "goto", "url": "https://chatgpt.com"}]})
    assert response.status_code == 401


def test_browser_task_mutating_requires_approval(client):
    headers = {"X-Brain-API-Key": "secret-control-key-with-sufficient-length-24+"}
    response = client.post(
        "/browser/tasks",
        headers=headers,
        json={
            "title": "Mutating task",
            "objective": "Click button",
            "actions": [{"op": "goto", "url": "https://chatgpt.com"}, {"op": "click", "selector": "#submit"}],
            "owner_approved": False,
        },
    }
    assert response.status_code == 409
