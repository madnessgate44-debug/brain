"""Approval API tests."""

import json

import pytest
from fastapi.testclient import TestClient

from brain.api.app import create_app
from brain.domain.enums import ApprovalType


@pytest.fixture
def client(monkeypatch):
    """Create a test client with application startup and shutdown enabled."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key-for-unit-tests-123")
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as test_client:
        yield test_client


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

    duplicate = client.post(
        f"/missions/{mission_id}/approvals",
        json={
            "approval_type": ApprovalType.EXECUTION_REVIEW.value,
            "reason": "A second pending approval must not replace the first",
        },
    )
    assert duplicate.status_code == 400
    assert "already has a pending approval" in duplicate.json()["detail"]


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

    # A pending approval must prevent mission execution.
    blocked_start = client.post(f"/missions/{mission_id}/start")
    assert blocked_start.status_code == 409
    assert "approval_state is PENDING" in blocked_start.json()["detail"]

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

    allowed_start = client.post(f"/missions/{mission_id}/start")
    assert allowed_start.status_code == 200

    repeated_response = client.post(
        f"/approvals/{approval_id}/respond",
        json={"approved": False, "response_note": "conflicting second response"},
    )
    assert repeated_response.status_code == 409
    assert any(
        item["id"] == approval_id and item["status"] == "APPROVED"
        for item in client.get("/approvals?status_filter=APPROVED").json()
    )

    events_response = client.get(f"/missions/{mission_id}/events")
    assert events_response.status_code == 200
    events_by_type = {
        item["event_type"]: item for item in events_response.json()
    }
    requested_payload = json.loads(events_by_type["approval_requested"]["payload_json"])
    responded_payload = json.loads(events_by_type["approval_responded"]["payload_json"])
    assert requested_payload["approval_id"] == approval_id
    assert responded_payload["approved"] is True


def test_list_pending_approvals(client):
    """The mobile client can load approval state from Brain's API."""
    mission_response = client.post(
        "/missions",
        json={"title": "Approval list test", "objective": "List pending approvals"},
    )
    assert mission_response.status_code == 201
    mission_id = mission_response.json()["id"]
    created = client.post(
        f"/missions/{mission_id}/approvals",
        json={"approval_type": ApprovalType.PLAN_REVIEW.value, "reason": "Verify API listing"},
    )
    assert created.status_code == 200

    response = client.get("/approvals?status_filter=PENDING")
    assert response.status_code == 200
    assert any(item["id"] == created.json()["id"] for item in response.json())



def test_expired_approval_is_not_accepted(client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    mission_response = client.post(
        "/missions",
        json={"title": "Expiry test", "objective": "Approval must expire"},
    )
    mission_id = mission_response.json()["id"]
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    created = client.post(
        f"/missions/{mission_id}/approvals",
        json={
            "approval_type": ApprovalType.PLAN_REVIEW.value,
            "reason": "Expiry test",
            "expires_at": expires_at.isoformat(),
        },
    )
    assert created.status_code == 200
    approval_id = created.json()["id"]

    monkeypatch.setattr(
        "brain.services.approval_service.utc_now",
        lambda: expires_at + timedelta(seconds=1),
    )
    response = client.post(
        f"/approvals/{approval_id}/respond",
        json={"approved": True, "response_note": "Too late"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "EXPIRED"
    assert response.json()["response_note"] is None
    assert client.post(f"/missions/{mission_id}/start").status_code == 409


def test_approval_expiration_must_be_in_the_future(client):
    from datetime import datetime, timedelta, timezone

    mission_response = client.post(
        "/missions",
        json={"title": "Past expiry test", "objective": "Reject past expiration"},
    )
    mission_id = mission_response.json()["id"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    response = client.post(
        f"/missions/{mission_id}/approvals",
        json={
            "approval_type": ApprovalType.PLAN_REVIEW.value,
            "reason": "Past expiry test",
            "expires_at": past,
        },
    )
    assert response.status_code == 400
    assert "must be in the future" in response.json()["detail"]
