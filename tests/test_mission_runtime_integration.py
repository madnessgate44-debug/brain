"""End-to-end mission execution checks."""

import json
import time

from fastapi.testclient import TestClient

from brain.api.app import create_app


def test_started_mission_persists_artifact_and_completion(monkeypatch):
    """A started mission should create a registered artifact and completion events."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "test-control-key-for-unit-tests-123")
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as client:
        created = client.post(
            "/missions",
            json={"title": "Runtime verification", "objective": "Create a mission brief"},
        )
        assert created.status_code == 201
        mission_id = created.json()["id"]

        started = client.post(f"/missions/{mission_id}/start")
        assert started.status_code == 200

        mission = None
        for _ in range(40):
            response = client.get(f"/missions/{mission_id}")
            assert response.status_code == 200
            mission = response.json()
            if mission["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.05)

        assert mission is not None
        assert mission["status"] == "COMPLETED", mission

        artifacts = client.get(f"/missions/{mission_id}/artifacts")
        assert artifacts.status_code == 200
        assert any(
            item["logical_name"] == "mission-brief.md"
            for item in artifacts.json()
        )

        events = client.get(f"/missions/{mission_id}/events")
        assert events.status_code == 200
        event_types = {item["event_type"] for item in events.json()}
        assert {"mission_created", "mission_started", "worker_started", "artifact_created", "mission_phase_changed"} <= event_types
        events_by_type = {item["event_type"]: item for item in events.json()}
        assert json.loads(events_by_type["mission_created"]["payload_json"])["title"] == "Runtime verification"
        assert json.loads(events_by_type["mission_started"]["payload_json"])["runtime_id"]


def test_failed_mission_persists_detailed_diagnostic_artifacts(monkeypatch):
    """Any mission worker failure should persist a readable and machine-readable report."""
    import os
    os.environ["BRAIN_CONTROL_API_KEY"] = "test-control-key-for-unit-tests-123"
    app = create_app()
    with TestClient(app, headers={"X-Brain-API-Key": "test-control-key-for-unit-tests-123"}) as client:
        created = client.post(
            "/missions",
            json={
                "title": "Failure diagnostic verification",
                "objective": "Exercise the mission failure-report path",
                "metadata": {"workflow_type": "software_company"},
            },
        )
        assert created.status_code == 201
        mission_id = created.json()["id"]

        started = client.post(f"/missions/{mission_id}/start")
        assert started.status_code == 200

        mission = None
        for _ in range(40):
            response = client.get(f"/missions/{mission_id}")
            assert response.status_code == 200
            mission = response.json()
            if mission["status"] == "FAILED":
                break
            time.sleep(0.05)

        assert mission is not None
        assert mission["status"] == "FAILED", mission

        artifacts = client.get(f"/missions/{mission_id}/artifacts")
        assert artifacts.status_code == 200
        names = {item["logical_name"] for item in artifacts.json()}
        assert {"failure-diagnostic.json", "failure-report.md"} <= names

        events = client.get(f"/missions/{mission_id}/events")
        assert events.status_code == 200
        event_types = {item["event_type"] for item in events.json()}
        assert {"mission_failed", "failure_diagnostic_created"} <= event_types
