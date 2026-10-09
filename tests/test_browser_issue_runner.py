"""Tests for the owner-controlled GitHub issue browser entrypoint."""

import pytest

from scripts.run_browser_issue import parse_issue_payload


def event_for(body, login="madnessgate44-debug"):
    return {
        "issue": {
            "user": {"login": login},
            "body": body,
        }
    }


def valid_body():
    return """/brain browser
```json
{
  "title": "Inspect public example page",
  "objective": "Read the public landing page title",
  "allowed_domains": ["example.com"],
  "actions": [
    {"op": "navigate", "url": "https://example.com/"},
    {"op": "inspect", "max_chars": 500}
  ],
  "owner_approved": true
}
```
"""


def test_parses_owner_authored_browser_task():
    payload = parse_issue_payload(event_for(valid_body()), "madnessgate44-debug")
    assert payload["title"] == "Inspect public example page"
    assert payload["allowed_domains"] == ["example.com"]
    assert [action["op"] for action in payload["actions"]] == ["navigate", "inspect"]


def test_rejects_issue_from_non_owner():
    with pytest.raises(ValueError, match="repository owner"):
        parse_issue_payload(event_for(valid_body(), login="someone-else"), "madnessgate44-debug")


def test_requires_exactly_one_json_block():
    with pytest.raises(ValueError, match="exactly one"):
        parse_issue_payload(event_for("/brain browser\nNo JSON here"), "madnessgate44-debug")


def test_accepts_public_web_wildcard_domain_scope():
    body = valid_body().replace('"example.com"', '"*"')
    payload = parse_issue_payload(event_for(body), "madnessgate44-debug")
    assert payload["allowed_domains"] == ["*"]


def test_requires_explicit_owner_approval():
    body = valid_body().replace('"owner_approved": true', '"owner_approved": false')
    with pytest.raises(ValueError, match="owner_approved"):
        parse_issue_payload(event_for(body), "madnessgate44-debug")


def test_rejects_unrecognized_fields():
    body = valid_body().replace('"owner_approved": true', '"owner_approved": true, "password": "never"')
    with pytest.raises(ValueError, match="Unsupported"):
        parse_issue_payload(event_for(body), "madnessgate44-debug")


def test_rejects_unsupported_browser_operations():
    body = valid_body().replace('"op": "inspect"', '"op": "shell"')
    with pytest.raises(ValueError, match="unsupported op"):
        parse_issue_payload(event_for(body), "madnessgate44-debug")
