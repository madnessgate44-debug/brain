"""Integration tests for mission pause and durable escalation recording."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import brain.runtime.mission_runtime as runtime_module
from brain.company.escalation import WorkflowEscalationRequired
from brain.domain.enums import MissionPhase, MissionStatus


class FakeSession:
    async def commit(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeArtifactStore:
    workspace_root = Path("/tmp/brain-escalation-test")

    def save_artifact(self, mission_id, logical_name, content, metadata):
        self.saved = {
            "mission_id": mission_id,
            "logical_name": logical_name,
            "content": content,
            "metadata": metadata,
        }
        return self.workspace_root / mission_id / logical_name


@pytest.mark.asyncio
async def test_runtime_persists_escalation_and_pauses_instead_of_failing(monkeypatch):
    mission = SimpleNamespace(
        id="mission-escalation-test",
        status=MissionStatus.RUNNING.value,
        metadata_json=json.dumps({
            "workflow_type": "software_company",
            "repository": "owner/repository",
        }),
        objective="Test escalation",
        title="Escalation test",
    )
    state = {"events": [], "artifacts": [], "phase": None, "status": None}

    class FakeMissionRepository:
        def __init__(self, session):
            pass

        async def get_by_id(self, mission_id):
            return mission

        async def update_phase(self, mission_id, phase):
            state["phase"] = phase

        async def update_status(self, mission_id, status):
            state["status"] = status

        async def mark_failed(self, *args, **kwargs):
            raise AssertionError("Escalation must not mark the mission failed")

    class FakeEventRepository:
        def __init__(self, session):
            pass

        async def append_event(self, **kwargs):
            state["events"].append(kwargs)

    class FakeArtifactRepository:
        def __init__(self, session):
            pass

        async def create(self, **kwargs):
            state["artifacts"].append(kwargs)

    class FakeEngine:
        async def run(self, objective, repository):
            raise WorkflowEscalationRequired(
                "ai_provider_configuration_missing",
                "Provider configuration is missing.",
                missing_settings=("BRAIN_AI_API_KEY",),
            )

    monkeypatch.setattr(runtime_module, "MissionRepository", FakeMissionRepository)
    monkeypatch.setattr(runtime_module, "EventRepository", FakeEventRepository)
    monkeypatch.setattr(runtime_module, "ArtifactRepository", FakeArtifactRepository)
    monkeypatch.setattr(runtime_module, "GitHubRepositoryGateway", lambda: object())
    monkeypatch.setattr(runtime_module, "GitHubCompanyTools", lambda gateway: object())
    monkeypatch.setattr(runtime_module, "OpenAICompatibleProvider", lambda: object())
    monkeypatch.setattr(runtime_module, "SpecialistAgentRunner", lambda provider: object())
    monkeypatch.setattr(runtime_module, "CompanyWorkflowEngine", lambda runner, tools: FakeEngine())

    runtime = runtime_module.MissionRuntime(
        mission_id=mission.id,
        runtime_id="runtime-escalation-test",
        session_factory=lambda: FakeSession(),
        artifact_store=FakeArtifactStore(),
    )

    await runtime.run()

    assert state["status"] == MissionStatus.PAUSED
    assert state["phase"] == MissionPhase.WAITING_FOR_APPROVAL
    escalation_events = [
        event for event in state["events"]
        if event["event_type"] == "escalation_requested"
    ]
    assert len(escalation_events) == 1
    payload = json.loads(escalation_events[0]["payload_json"])
    assert payload["missing_settings"] == ["BRAIN_AI_API_KEY"]
    assert payload["secret_values_included"] is False
    assert any(
        artifact["logical_name"] == "escalation-request.json"
        for artifact in state["artifacts"]
    )
