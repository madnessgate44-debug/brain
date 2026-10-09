"""Regression tests for Brain's bounded browser worker."""

from contextlib import asynccontextmanager

import pytest

from brain.runtime.workers.browser_worker import (
    BrowserPolicyError,
    BrowserWorker,
    browser_dispatch_payload,
    domain_matches,
    is_allowed_url,
    is_restricted_consumer_ai_url,
    sign_browser_dispatch,
    validate_browser_actions,
    verify_browser_dispatch,
)


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    async def inner_text(self):
        return "Example page content"

    async def click(self, **kwargs):
        if self.selector == "button#missing":
            raise RuntimeError("selector not found")
        self.page.actions.append(("click", self.selector))

    async def fill(self, text, **kwargs):
        self.page.actions.append(("type", self.selector, text))

    async def press_sequentially(self, text, **kwargs):
        self.page.actions.append(("type-sequential", self.selector, text))

    async def press(self, key, **kwargs):
        self.page.actions.append(("press", self.selector, key))

    async def wait_for(self, **kwargs):
        self.page.actions.append(("wait_for", self.selector, kwargs.get("state")))


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []

    async def goto(self, url, **kwargs):
        self.url = url
        self.actions.append(("navigate", url))
        return None

    async def title(self):
        return "Example"

    def locator(self, selector):
        return FakeLocator(self, selector)

    async def screenshot(self, **kwargs):
        return b"fake-png"


def fake_session_factory(page):
    @asynccontextmanager
    async def session():
        yield page
    return session


def test_action_validation_rejects_unknown_and_oversized_sequences():
    with pytest.raises(BrowserPolicyError):
        validate_browser_actions([{"op": "shell", "command": "id"}])
    with pytest.raises(BrowserPolicyError):
        validate_browser_actions([{"op": "inspect"}] * 26)
    with pytest.raises(BrowserPolicyError):
        validate_browser_actions([{"op": "type", "selector": "#prompt", "text": 3}])


def test_domain_matching_requires_exact_or_subdomain_rule():
    assert domain_matches("chatgpt.com", "chatgpt.com")
    assert domain_matches("auth.openai.com", "*.openai.com")
    assert not domain_matches("openai.com", "*.openai.com")
    assert not domain_matches("evilchatgpt.com", "chatgpt.com")
    assert domain_matches("anything.example", "*")


def test_url_policy_rejects_non_http_credentials_and_unapproved_domains():
    assert not is_allowed_url("file:///etc/passwd", ["example.com"])
    assert not is_allowed_url("https://user:pass@example.com", ["example.com"])
    assert not is_allowed_url("https://example.com.evil.invalid", ["example.com"])
    assert not is_allowed_url("http://localhost:8000", ["localhost"])
    assert not is_allowed_url("https://example.com", [])


def test_consumer_ai_host_detection_is_narrow():
    assert is_restricted_consumer_ai_url("https://chatgpt.com/")
    assert is_restricted_consumer_ai_url("https://chat.openai.com/")
    assert is_restricted_consumer_ai_url("https://gemini.google.com/app")
    assert not is_restricted_consumer_ai_url("https://openai.com/policies/terms-of-use")
    assert not is_restricted_consumer_ai_url("https://example.com/")


def test_browser_dispatch_signature_is_bound_to_mission_and_actions():
    secret = "this-is-a-long-test-control-secret"
    payload = browser_dispatch_payload(
        "mission-1", "ChatGPT task", "Send an approved prompt",
        [{"op": "navigate", "url": "https://chatgpt.com/"}], False,
    )
    signature = sign_browser_dispatch(secret, payload)
    assert verify_browser_dispatch(secret, payload, signature)
    changed = {**payload, "mission_id": "mission-2"}
    assert not verify_browser_dispatch(secret, changed, signature)
    assert not verify_browser_dispatch(secret, payload, "wrong")


@pytest.mark.asyncio
async def test_worker_runs_actions_in_order_and_returns_evidence(monkeypatch):
    page = FakePage()
    worker = BrowserWorker(
        allowed_domains=["example.com"],
        page_session_factory=fake_session_factory(page),
    )
    monkeypatch.setattr(
        "brain.runtime.workers.browser_worker.is_allowed_url",
        lambda url, domains: url == "https://example.com/",
    )
    result = await worker.execute([
        {"op": "navigate", "url": "https://example.com/"},
        {"op": "inspect", "max_chars": 100},
        {"op": "click", "selector": "button#continue"},
    ], owner_approved=True)

    assert result["status"] == "succeeded"
    assert result["completed_actions"] == 3
    assert result["results"][1]["result"]["text"] == "Example page content"
    assert page.actions[-1] == ("click", "button#continue")


@pytest.mark.asyncio
async def test_worker_refuses_automated_interaction_with_consumer_ai_chat(monkeypatch):
    page = FakePage()
    page.url = "https://chatgpt.com/"
    worker = BrowserWorker(
        allowed_domains=["chatgpt.com", "*.chatgpt.com"],
        page_session_factory=fake_session_factory(page),
    )
    result = await worker.execute([{"op": "inspect"}])
    assert result["status"] == "failed"
    assert result["results"][0]["error"] == "BrowserPolicyError"
    assert "provider-supported integration" in result["results"][0]["message"]
    assert page.actions == []


@pytest.mark.asyncio
async def test_worker_rejects_mutating_actions_without_owner_approval():
    worker = BrowserWorker(allowed_domains=["example.com"], page_session_factory=fake_session_factory(FakePage()))
    with pytest.raises(BrowserPolicyError, match="owner approval"):
        await worker.execute([{"op": "type", "selector": "#prompt", "text": "hello"}])


@pytest.mark.asyncio
async def test_worker_stops_after_first_action_failure(monkeypatch):
    page = FakePage()
    worker = BrowserWorker(
        allowed_domains=["example.com"],
        page_session_factory=fake_session_factory(page),
    )
    monkeypatch.setattr(
        "brain.runtime.workers.browser_worker.is_allowed_url",
        lambda url, domains: url == "https://example.com/",
    )
    result = await worker.execute([
        {"op": "navigate", "url": "https://example.com/"},
        {"op": "click", "selector": "button#missing"},
        {"op": "inspect"},
    ], owner_approved=True)
    assert result["status"] == "failed"
    assert result["completed_actions"] == 1
    assert len(result["results"]) == 2
