"""Tests for Brain's free-first public-web research issue runner."""

import pytest

from scripts.run_browser_research_issue import actions_require_approval, parse_research_payload


def event_for(body, login="madnessgate44-debug"):
    return {"issue": {"user": {"login": login}, "body": body}, "sender": {"login": login}}


def valid_body():
    fence = chr(96) * 3
    return (
        "/brain browse\n"
        + fence + "json\n"
        + '{\n'
        + '  "title": "Inspect Playwright documentation",\n'
        + '  "objective": "Summarize the official guidance on browser retries",\n'
        + '  "start_url": "https://playwright.dev/docs/test-retries",\n'
        + '  "allowed_domains": ["playwright.dev"]\n'
        + '}\n'
        + fence
    )


def test_parses_owner_authored_research_request():
    payload = parse_research_payload(event_for(valid_body()), "madnessgate44-debug")
    assert payload["title"] == "Inspect Playwright documentation"
    assert payload["start_url"] == "https://playwright.dev/docs/test-retries"
    assert payload["allowed_domains"] == ["playwright.dev"]


def test_defaults_domain_allowlist_to_start_url_host():
    body = valid_body().replace(',\n  "allowed_domains": ["playwright.dev"]', "")
    payload = parse_research_payload(event_for(body), "madnessgate44-debug")
    assert payload["allowed_domains"] == ["playwright.dev"]


def test_rejects_non_owner_issue():
    with pytest.raises(ValueError, match="repository owner"):
        parse_research_payload(event_for(valid_body(), login="someone-else"), "madnessgate44-debug")


def test_rejects_non_owner_editor_of_owner_authored_issue():
    event = event_for(valid_body())
    event["sender"] = {"login": "untrusted-collaborator"}
    with pytest.raises(ValueError, match="trigger or edit"):
        parse_research_payload(event, "madnessgate44-debug")


def test_requires_exactly_one_json_block():
    with pytest.raises(ValueError, match="exactly one"):
        parse_research_payload(event_for("/brain browse\nNo JSON here"), "madnessgate44-debug")


def test_rejects_unsupported_fields():
    body = valid_body().replace('"allowed_domains": ["playwright.dev"]', '"password": "never"')
    with pytest.raises(ValueError, match="Unsupported"):
        parse_research_payload(event_for(body), "madnessgate44-debug")


def test_start_url_must_be_in_allowlist():
    body = valid_body().replace('"playwright.dev"', '"example.com"')
    with pytest.raises(ValueError, match="start_url host"):
        parse_research_payload(event_for(body), "madnessgate44-debug")


def test_rejects_embedded_credentials_and_non_http_urls():
    body = valid_body().replace(
        "https://playwright.dev/docs/test-retries",
        "https://user:pass@playwright.dev/",
    )
    with pytest.raises(ValueError, match="without embedded credentials"):
        parse_research_payload(event_for(body), "madnessgate44-debug")
    body = valid_body().replace(
        "https://playwright.dev/docs/test-retries",
        "file:///etc/passwd",
    )
    with pytest.raises(ValueError, match="HTTP"):
        parse_research_payload(event_for(body), "madnessgate44-debug")


def test_only_mutating_action_plans_require_owner_approval():
    assert actions_require_approval([{"op": "navigate"}, {"op": "inspect"}]) is False
    assert actions_require_approval([{"op": "click", "selector": "a"}]) is True
    assert actions_require_approval([{"op": "select", "selector": "select", "value": "x"}]) is True


@pytest.mark.asyncio
async def test_mutating_plan_is_returned_for_review_without_starting_browser(monkeypatch, tmp_path):
    import scripts.run_browser_research_issue as runner

    class FakePlanner:
        async def plan(self, objective):
            return {
                "title": "Proposed website change",
                "objective": objective,
                "actions": [
                    {"op": "navigate", "url": "https://example.com/"},
                    {"op": "click", "selector": "a"},
                ],
            }

    def browser_must_not_start(*args, **kwargs):
        raise AssertionError("Mutating plans must not start the browser.")

    monkeypatch.setattr(runner, "BrowserPlanner", FakePlanner)
    monkeypatch.setattr(runner, "BrowserWorker", browser_must_not_start)
    payload = {
        "title": "Review before changing",
        "objective": "Inspect the page and click the link",
        "start_url": "https://example.com/",
        "allowed_domains": ["example.com"],
    }
    result = await runner.execute_research(payload, tmp_path)
    assert result["status"] == "requires_owner_approval"
    report = (tmp_path / "browser-execution-report.json").read_text(encoding="utf-8")
    assert '"completed_actions": 0' in report
