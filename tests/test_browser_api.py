"""API and runtime integration tests for bounded browser missions."""

import time

from fastapi.testclient import TestClient

from brain.api.app import create_app


def _payload(**overrides):
    payload = {
        "title": "Inspect ChatGPT",
        "objective": "Open ChatGPT and inspect the current page without sending a message",
        "actions": [{"op": "navigate", "url": "https://chatgpt.com/"}],
    }
    payload.update(overrides)
    return payload


def test_browser_endpoint_is_disabled_without_control_key(monkeypatch):
    monkeypatch.delenv("BRAIN_CONTROL_API_KEY", raising=False)
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/browser/tasks", json=_payload())
    assert response.status_code == 503
    assert "BRAIN_CONTROL_API_KEY" in response.json()["detail"]


def test_browser_endpoint_rejects_wrong_control_key(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "x" * 32)
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/browser/tasks",
            headers={"X-Brain-API-Key": "wrong"},
            json=_payload(),
        )
    assert response.status_code == 401


def test_browser_endpoint_rejects_weak_control_key_before_creating_mission(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "too-short")
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/browser/tasks",
            headers={"X-Brain-API-Key": "too-short"},
            json=_payload(),
        )
    assert response.status_code == 503


def test_browser_endpoint_requires_approval_for_mutating_actions(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "x" * 32)
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/browser/tasks",
            headers={"X-Brain-API-Key": "x" * 32},
            json=_payload(actions=[{"op": "type", "selector": "textarea", "text": "hello"}]),
        )
    assert response.status_code == 409


def test_browser_mission_runs_through_mission_runtime_and_records_report(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", "x" * 32)
    monkeypatch.setenv("BRAIN_BROWSER_ALLOWED_DOMAINS", "chatgpt.com,*.chatgpt.com")

    async def fake_execute(self, actions, owner_approved=False):
        return {
            "worker": "browser_worker",
            "status": "succeeded",
            "completed_actions": len(actions),
            "requested_actions": len(actions),
            "results": [{"index": 0, "op": "navigate", "ok": True, "result": {
                "url": "https://chatgpt.com/", "title": "ChatGPT", "http_status": 200
            }}],
        }

    monkeypatch.setattr(
        "brain.runtime.workers.browser_worker.BrowserWorker.execute",
        fake_execute,
    )
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/browser/tasks",
            headers={"X-Brain-API-Key": "x" * 32},
            json=_payload(),
        )
        assert response.status_code == 202, response.text
        mission_id = response.json()["mission_id"]

        mission = None
        for _ in range(40):
            status_response = client.get(f"/missions/{mission_id}")
            assert status_response.status_code == 200
            mission = status_response.json()
            if mission["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.05)

        assert mission is not None
        assert mission["status"] == "COMPLETED", mission
        artifacts = client.get(f"/missions/{mission_id}/artifacts")
        assert artifacts.status_code == 200
        assert any(item["logical_name"] == "browser-execution-report.json" for item in artifacts.json())
        events = client.get(f"/missions/{mission_id}/events")
        event_types = {item["event_type"] for item in events.json()}
        assert "browser_worker_started" in event_types
        assert "browser_worker_completed" in event_types
