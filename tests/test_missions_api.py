"""Mission API tests."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app


@pytest.fixture
def client(monkeypatch):
    """Create a test client with application startup and shutdown enabled."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key-for-unit-tests-123")
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as test_client:
        yield test_client


def test_create_mission(client):
    """Test mission creation."""
    data = {
        "title": "Test Mission",
        "objective": "Test objective",
        "priority": "HIGH",
        "risk_level": "MEDIUM",
        "max_loop_iterations": 5,
    }

    response = client.post("/missions", json=data)
    assert response.status_code == 201

    mission = response.json()
    assert mission["title"] == "Test Mission"
    assert mission["objective"] == "Test objective"
    assert mission["phase"] == "INTAKE"
    assert mission["status"] == "PENDING"
    assert "id" in mission


def test_list_missions(client):
    """Test mission listing."""
    # Create a mission first
    data = {"title": "Test Mission 2", "objective": "Test objective 2"}
    client.post("/missions", json=data)

    response = client.get("/missions")
    assert response.status_code == 200

    data = response.json()
    assert "missions" in data
    assert "total" in data
    assert len(data["missions"]) > 0


def test_get_mission(client):
    """Test getting a specific mission."""
    # Create mission
    create_data = {"title": "Test Mission 3", "objective": "Test objective 3"}
    create_response = client.post("/missions", json=create_data)
    mission_id = create_response.json()["id"]

    # Get mission
    response = client.get(f"/missions/{mission_id}")
    assert response.status_code == 200

    mission = response.json()
    assert mission["id"] == mission_id
    assert mission["title"] == "Test Mission 3"


def test_start_mission(client):
    """Test starting a mission."""
    # Create mission
    create_data = {"title": "Test Mission 4", "objective": "Test objective 4"}
    create_response = client.post("/missions", json=create_data)
    mission_id = create_response.json()["id"]

    # Start mission
    response = client.post(f"/missions/{mission_id}/start")
    assert response.status_code == 200

    data = response.json()
    assert data["mission_id"] == mission_id
    assert data["status"] in ["RUNNING", "COMPLETED"]
    assert "runtime_id" in data


def test_mission_events(client):
    """Test mission events endpoint."""
    # Create mission
    create_data = {"title": "Test Mission 5", "objective": "Test objective 5"}
    create_response = client.post("/missions", json=create_data)
    mission_id = create_response.json()["id"]

    # Get events
    response = client.get(f"/missions/{mission_id}/events")
    assert response.status_code == 200

    events = response.json()
    assert len(events) > 0
    assert events[0]["event_type"] == "mission_created"


def test_shutdown_cancels_active_mission_runtime(monkeypatch):
    """Application shutdown must stop background tasks before closing SQLite."""
    from brain.runtime.mission_runtime import MissionRuntime

    async def wait_until_cancelled(self):
        await asyncio.sleep(60)

    monkeypatch.setattr(MissionRuntime, "run", wait_until_cancelled)
    app = create_app()
    with TestClient(app) as test_client:
        created = test_client.post(
            "/missions",
            json={"title": "Shutdown test", "objective": "Exercise runtime cleanup"},
        )
        assert created.status_code == 201
        mission_id = created.json()["id"]
        started = test_client.post(f"/missions/{mission_id}/start")
        assert started.status_code == 200
        registry = app.state.boot_service.runtime_registry
        assert mission_id in registry.list_active()

    assert registry.list_active() == []


def test_mission_api_rejects_requests_without_control_key(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key-for-unit-tests-123")
    with TestClient(create_app()) as unauthenticated_client:
        response = unauthenticated_client.get("/missions")
    assert response.status_code == 401


def test_mission_api_fails_closed_when_control_key_is_missing(monkeypatch):
    monkeypatch.delenv("BRAIN_CONTROL_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/missions", headers={"X-Brain-API-Key": "x" * 32})
    assert response.status_code == 503
