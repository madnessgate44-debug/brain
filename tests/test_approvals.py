"""Approval API tests."""

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app
from brain.domain.enums import ApprovalType


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_create_approval(client):
    """Test creating an approval request."""
    # Create a mission first
    mission_data = {"title": "Test Mission", "objective": "Test objective"}
    mission_response = client.post("/missions", json=mission_data)
    mission_id = mission_response.json()["id"]
    
    # Create approval
    approval_data = {
        "approval_type": ApprovalType.PLAN_REVIEW.value,
        "reason": "Need plan review before execution"
    }
    response = client.post(
        f"/missions/{mission_id}/approvals",
        json=approval_data
    )
    assert response.status_code == 200
    
    approval = response.json()
    assert approval["mission_id"] == mission_id
    assert approval["status"] == "PENDING"
    assert "id" in approval


def test_respond_to_approval(client):
    """Test responding to an approval request."""
    # Create a mission
    mission_data = {"title": "Test Mission", "objective": "Test objective"}
    mission_response = client.post("/missions", json=mission_data)
    mission_id = mission_response.json()["id"]
    
    # Create approval
    approval_data = {
        "approval_type": ApprovalType.PLAN_REVIEW.value,
        "reason": "Need plan review"
    }
    approval_response = client.post(
        f"/missions/{mission_id}/approvals",
        json=approval_data
    )
    approval_id = approval_response.json()["id"]
    
    # Respond to approval
    response_data = {
        "approved": True,
        "response_note": "Plan looks good"
    }
    response = client.post(
        f"/approvals/{approval_id}/respond",
        json=response_data
    )
    assert response.status_code == 200
    
    approval = response.json()
    assert approval["status"] == "APPROVED"
    assert approval["response_note"] == "Plan looks good"