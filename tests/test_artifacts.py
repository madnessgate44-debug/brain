"""Artifact API tests."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app
from brain.domain.enums import ArtifactType


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_create_artifact(client):
    """Test creating an artifact."""
    # Create a mission
    mission_data = {"title": "Test Mission", "objective": "Test objective"}
    mission_response = client.post("/missions", json=mission_data)
    mission_id = mission_response.json()["id"]
    
    # Create artifact
    artifact_data = {
        "artifact_type": ArtifactType.DOCUMENTATION.value,
        "logical_name": "test_doc.md",
        "mime_type": "text/markdown",
        "size_bytes": 1024,
        "metadata": {"author": "test"}
    }
    response = client.post(
        f"/missions/{mission_id}/artifacts",
        json=artifact_data
    )
    assert response.status_code == 201
    
    artifact = response.json()
    assert artifact["mission_id"] == mission_id
    assert artifact["logical_name"] == "test_doc.md"
    assert "id" in artifact


def test_list_artifacts(client):
    """Test listing artifacts for a mission."""
    # Create a mission
    mission_data = {"title": "Test Mission", "objective": "Test objective"}
    mission_response = client.post("/missions", json=mission_data)
    mission_id = mission_response.json()["id"]
    
    # Create an artifact
    artifact_data = {
        "artifact_type": ArtifactType.DOCUMENTATION.value,
        "logical_name": "doc1.md"
    }
    client.post(f"/missions/{mission_id}/artifacts", json=artifact_data)
    
    # List artifacts
    response = client.get(f"/missions/{mission_id}/artifacts")
    assert response.status_code == 200
    
    artifacts = response.json()
    assert len(artifacts) > 0
    assert artifacts[0]["mission_id"] == mission_id