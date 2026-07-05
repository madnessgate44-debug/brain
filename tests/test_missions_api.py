"""Mission API tests."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


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