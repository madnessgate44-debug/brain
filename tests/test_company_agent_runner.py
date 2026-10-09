"""Contract tests for all specialist agent roles without live API calls."""

import json

import pytest

from brain.company.agent_runner import AgentOutputError, SpecialistAgentRunner
from brain.company.roles import ROLE_BY_KEY, WORKFLOW_ORDER


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


def _evidence():
    # Include every prerequisite so each role is tested independently of prior model calls.
    return {
        "user_request": "Test the specialist contract",
        "product_brief": "brief",
        "acceptance_criteria": ["AC-1"],
        "open_questions": [],
        "user_journeys": ["start", "finish"],
        "screen_specification": "mobile screen",
        "design_system": "accessible",
        "architecture": "service architecture",
        "file_plan": ["src/app.py"],
        "technical_risks": [],
        "change_set": {"summary": "test", "files": [{"path": "src/app.py", "content": "pass"}]},
        "implementation_notes": "notes",
        "review_findings": [],
        "review_decision": "PASS",
        "test_plan": ["pytest"],
        "test_results": {"status": "PASS", "executed": True},
        "defect_list": [],
        "security_findings": [],
        "security_decision": "PASS",
        "customer_review": "PASS",
        "usability_findings": [],
        "release_decision": "READY_FOR_HUMAN_APPROVAL",
        "release_checklist": ["human review"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("role_key", WORKFLOW_ORDER)
async def test_every_specialist_role_accepts_its_contract_and_returns_required_fields(role_key):
    role = ROLE_BY_KEY[role_key]
    deliverables = {key: {"evidence": "test"} for key in role.deliverables}
    payload = {
        "status": "PASS",
        "deliverables": deliverables,
        "findings": [],
        "blockers": [],
        "evidence_needed": [],
    }
    provider = FakeProvider(json.dumps(payload))
    runner = SpecialistAgentRunner(provider)

    result = await runner.run(role_key, "Test every role", _evidence())

    assert result["status"] == "PASS"
    assert result["role"] == role_key
    assert all(key in result["deliverables"] for key in role.deliverables)
    assert len(provider.calls) == 1
    system_prompt, user_prompt = provider.calls[0]
    assert role.title in system_prompt
    assert "Return exactly one JSON object" in system_prompt
    assert json.loads(user_prompt)["role"] == role_key


@pytest.mark.asyncio
async def test_specialist_runner_rejects_missing_required_deliverable():
    role = ROLE_BY_KEY["product_owner"]
    provider = FakeProvider(json.dumps({
        "status": "PASS",
        "deliverables": {"product_brief": "brief"},
        "findings": [],
        "blockers": [],
        "evidence_needed": [],
    }))
    runner = SpecialistAgentRunner(provider)

    with pytest.raises(AgentOutputError, match="omitted required deliverables"):
        await runner.run("product_owner", "Test malformed output", _evidence())


@pytest.mark.asyncio
async def test_specialist_runner_rejects_non_json_output():
    provider = FakeProvider("I finished the work.")
    runner = SpecialistAgentRunner(provider)

    with pytest.raises(AgentOutputError, match="not valid JSON"):
        await runner.run("product_owner", "Test malformed output", _evidence())
