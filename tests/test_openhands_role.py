"""Tests for the investigative role loop (openhands_role) and its runner wiring."""

import json

import pytest

from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.roles import ROLE_BY_KEY


def _real_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="test-key", model="test-model", base_url="https://example.test/v1"
    )


def _evidence() -> dict:
    return {
        "product_brief": "brief",
        "acceptance_criteria": ["AC-1"],
        "architecture": "Keep the module boundary.",
        "change_set": {"summary": "s", "files": [{"path": "src/main.py", "content": "print('x')\n"}]},
        "test_results": {"status": "PASS", "executed": True},
        "repository_snapshot": {
            "repository": "owner/repo",
            "source_contents": {"src/main.py": "print('x')\n"},
        },
    }


@pytest.mark.asyncio
async def test_non_developer_role_uses_the_investigative_loop(monkeypatch):
    """Every role that is not the developer must reach the OpenHands SDK loop, not single-shot."""
    captured = {}

    async def fake_role(role_key, role_title, system_prompt, user_prompt, evidence, provider):
        captured["role_key"] = role_key
        captured["provider"] = provider
        role = ROLE_BY_KEY[role_key]
        from brain.company.agent_runner import _DECISION_VALUES

        return json.dumps({
            "status": "PASS",
            "deliverables": {
                key: (sorted(_DECISION_VALUES[key])[0] if key in _DECISION_VALUES else "verified value")
                for key in role.deliverables
            },
            "findings": [],
            "blockers": [],
            "evidence_needed": [],
        })

    monkeypatch.setattr(
        "brain.company.openhands_role.run_openhands_role", fake_role, raising=False
    )
    provider = _real_provider()
    runner = SpecialistAgentRunner(provider)
    result = await runner.run("code_reviewer", "Review the change", _evidence())

    assert captured["role_key"] == "code_reviewer"
    assert captured["provider"] is provider
    assert result["role"] == "code_reviewer"
    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_investigative_role_repairs_malformed_json_once(monkeypatch):
    calls = {"n": 0}

    async def flaky_role(role_key, role_title, system_prompt, user_prompt, evidence, provider):
        calls["n"] += 1
        if calls["n"] == 1:
            return "I reviewed it and it looks fine."  # prose, not JSON
        role = ROLE_BY_KEY[role_key]
        return json.dumps({
            "status": "PASS",
            "deliverables": {key: "PASS" if key in {"review_decision"} else "value"
                             for key in role.deliverables},
            "findings": [],
            "blockers": [],
            "evidence_needed": [],
        })

    monkeypatch.setattr(
        "brain.company.openhands_role.run_openhands_role", flaky_role, raising=False
    )
    runner = SpecialistAgentRunner(_real_provider())
    result = await runner.run("code_reviewer", "Review the change", _evidence())

    assert calls["n"] == 2  # one repair
    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_investigative_role_still_rejects_unrepaired_output(monkeypatch):
    async def always_prose(role_key, role_title, system_prompt, user_prompt, evidence, provider):
        return "no json here"

    monkeypatch.setattr(
        "brain.company.openhands_role.run_openhands_role", always_prose, raising=False
    )
    runner = SpecialistAgentRunner(_real_provider())
    with pytest.raises(Exception):
        await runner.run("code_reviewer", "Review the change", _evidence())


def test_role_prompt_demands_evidence_and_json():
    from brain.company.openhands_role import _role_prompt

    prompt = _role_prompt("code_reviewer", "Code Reviewer", "CONTRACT", "TASK")
    assert "Investigate" in prompt
    assert "read-only" in prompt
    assert "exactly one JSON object" in prompt
    assert "CONTRACT" in prompt and "TASK" in prompt


def test_safe_relative_path_rejects_escapes():
    from brain.company.openhands_role import _safe_relative_path

    assert _safe_relative_path("src/main.py") == "src/main.py"
    for bad in ("/etc/passwd", "../x", "a\\b", ".git/config"):
        with pytest.raises(Exception):
            _safe_relative_path(bad)
