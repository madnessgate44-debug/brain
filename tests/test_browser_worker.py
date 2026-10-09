"""Tests for browser worker."""

import pytest
from brain.runtime.workers.browser_worker import validate_browser_actions, BrowserPolicyError


def test_validate_browser_actions_valid():
    actions = [
        {"op": "goto", "url": "https://chatgpt.com"},
        {"op": "click", "selector": "#submit"}
    ]
    validated = validate_browser_actions(actions)
    assert len(validated) == 2


def test_validate_browser_actions_invalid_domain():
    actions = [
        {"op": "goto", "url": "https://evil.com"}
    ]
    with pytest.raises(BrowserPolicyError):
        validate_browser_actions(actions)
