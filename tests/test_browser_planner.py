"""Tests for browser planner."""

import pytest
from unittest.mock import AsyncMock, patch

from brain.runtime.workers.browser_planner import BrowserPlanner, BrowserPlanningError
from brain.company.llm_provider import ModelProviderError


@pytest.mark.asyncio
async def test_browser_planner_success():
    planner = BrowserPlanner()
    with patch.object(planner, '_provider') as mock_provider:
        mock_provider.complete = AsyncMock(return_value="""{
            "title": "Search OpenAI",
            "objective": "Go to openai.com and search",
            "actions": [
                {"op": "goto", "url": "https://openai.com"},
                {"op": "click", "selector": "button"}
            ]
        }""")
        result = await planner.plan("Go to openai.com and search")
        assert result["title"] == "Search OpenAI"
        assert len(result["actions"]) == 2


@pytest.mark.asyncio
async def test_browser_planner_invalid_json():
    planner = BrowserPlanner()
    with patch.object(planner, '_provider') as mock_provider:
        mock_provider.complete = AsyncMock(return_value="not json")
        with pytest.raises(BrowserPlanningError):
            await planner.plan("fail")
