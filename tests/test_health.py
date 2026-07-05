"""Health endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "database_connected" in data
    assert "instance_id" in data
    assert "uptime_seconds" in data


def test_health_database_connected(client):
    """Test health endpoint shows database connectivity."""
    response = client.get("/health")
    data = response.json()
    # Database should be connected after boot
    assert data["database_connected"] is True