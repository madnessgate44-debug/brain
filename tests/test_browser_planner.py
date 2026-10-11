"""Tests for Brain's natural-language browser planner."""
import json

import pytest

from brain.runtime.workers.browser_planner import BrowserPlanner, BrowserPlanningError


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


@pytest.mark.asyncio
async def test_planner_returns_validated_actions_without_executing_them():
    provider = FakeProvider(json.dumps({
        "title": "Inspect example",
        "objective": "Read the Example Domain page",
        "actions": [
            {"op": "navigate", "url": "https://example.com/"},
            {"op": "inspect", "max_chars": 1000},
        ],
    }))
    plan = await BrowserPlanner(provider=provider).plan("Open https://example.com and summarize it")
    assert plan["title"] == "Inspect example"
    assert [item["op"] for item in plan["actions"]] == ["navigate", "inspect"]
    assert plan["execution_started"] is False
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_planner_rejects_invalid_json():
    with pytest.raises(BrowserPlanningError, match="valid JSON"):
        await BrowserPlanner(provider=FakeProvider("not json")).plan("Inspect example.com")


@pytest.mark.asyncio
async def test_planner_rejects_unsupported_or_unbounded_actions():
    response = json.dumps({
        "title": "Run command",
        "objective": "Run a shell command",
        "actions": [{"op": "shell", "command": "id"}],
    })
    with pytest.raises(BrowserPlanningError, match="invalid actions"):
        await BrowserPlanner(provider=FakeProvider(response)).plan("Run a shell command")


@pytest.mark.asyncio
async def test_planner_rejects_empty_objective_before_provider_call():
    provider = FakeProvider("{}")
    with pytest.raises(BrowserPlanningError, match="empty"):
        await BrowserPlanner(provider=provider).plan("  ")
    assert provider.calls == []

@pytest.mark.asyncio
async def test_planner_marks_sensitive_navigation_for_owner_approval(monkeypatch):
    monkeypatch.setenv("BRAIN_BROWSER_SENSITIVE_DOMAINS", "bank.example")
    provider = FakeProvider(json.dumps({
        "title": "Open banking page",
        "objective": "Open the account page",
        "actions": [{"op": "navigate", "url": "https://bank.example/login"}],
    }))
    plan = await BrowserPlanner(provider=provider).plan("Open the account page")
    assert plan["requires_owner_approval"] is True
    assert plan["execution_started"] is False
