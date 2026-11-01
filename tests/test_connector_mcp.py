"""Tests for the Brain MCP connector served alongside the REST API."""

import json

from fastapi.testclient import TestClient

from brain.connector.app import create_combined_app

KEY = "test-control-key-for-connector-tests-123456"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _parse_sse(text: str) -> dict:
    """Extract the JSON-RPC object from an MCP streamable-HTTP SSE response."""
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise AssertionError(f"no SSE data line in response: {text!r}")


def _call(client: TestClient, method: str, params: dict, request_id: int = 1) -> dict:
    response = client.post(
        "/mcp",
        headers={**MCP_HEADERS, "Authorization": f"Bearer {KEY}"},
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return _parse_sse(response.text)


def test_connector_rejects_missing_key(monkeypatch):
    """The connector must not answer unauthenticated requests."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        response = client.post(
            "/mcp",
            headers=MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert response.status_code == 401


def test_connector_rejects_wrong_key(monkeypatch):
    """A wrong key is rejected the same as a missing one."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, "Authorization": "Bearer not-the-right-key-at-all-0000"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert response.status_code == 401


def test_connector_initializes_with_key(monkeypatch):
    """A valid key completes the MCP handshake and names the Brain server."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        result = _call(client, "initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        })
    assert result["result"]["serverInfo"]["name"] == "brain"
    assert "tools" in result["result"]["capabilities"]


def test_connector_exposes_expected_tools(monkeypatch):
    """Clients discover the Brain tools without any manual wiring."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        result = _call(client, "tools/list", {})
    names = {tool["name"] for tool in result["result"]["tools"]}
    assert names == {
        "brain_chat",
        "brain_create_mission",
        "brain_start_mission",
        "brain_get_mission",
        "brain_list_missions",
        "brain_list_artifacts",
    }


def test_connector_chat_tool_calls_the_model(monkeypatch):
    """brain_chat returns the provider reply through the connector."""
    import brain.api.routes.chat as chat_route

    class FakeProvider:
        model = "test-model"

        async def complete(self, system_prompt: str, user_prompt: str) -> str:
            return "connector reply"

    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    monkeypatch.setenv("BRAIN_AI_API_KEY", "test-key")
    monkeypatch.setenv("BRAIN_AI_MODEL", "test-model")
    monkeypatch.setenv("BRAIN_AI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(chat_route, "OpenAICompatibleProvider", lambda: FakeProvider())

    with TestClient(create_combined_app()) as client:
        result = _call(client, "tools/call", {
            "name": "brain_chat",
            "arguments": {"message": "hello"},
        })
    content = result["result"]["content"][0]["text"]
    assert content == "connector reply"


def test_connector_create_and_list_mission(monkeypatch):
    """Mission tools drive the same mission store as the REST API."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        created = _call(client, "tools/call", {
            "name": "brain_create_mission",
            "arguments": {"title": "Connector mission", "objective": "Prove the path."},
        }, request_id=2)
        mission = json.loads(created["result"]["content"][0]["text"])
        assert mission["title"] == "Connector mission"

        listed = _call(client, "tools/call", {
            "name": "brain_list_missions",
            "arguments": {"limit": 5},
        }, request_id=3)
        missions = json.loads(listed["result"]["content"][0]["text"])
        assert any(m["id"] == mission["id"] for m in missions["missions"])


def test_rest_api_still_served_by_combined_app(monkeypatch):
    """Mounting the connector must not break the existing REST endpoints."""
    monkeypatch.setenv("BRAIN_CONTROL_API_KEY", KEY)
    with TestClient(create_combined_app()) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        unauthorized = client.get("/missions")
        assert unauthorized.status_code == 401

        authorized = client.get("/missions", headers={"X-Brain-API-Key": KEY})
        assert authorized.status_code == 200
