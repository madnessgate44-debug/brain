"""Contract guard for the Watcher channel receiver spec (issue #240).

The automation draft was deleted after testing, so these assertions protect the
recorded spec from drifting into something that looks enabled or mis-scoped.
"""

import json
from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parents[1] / "watcher" / "channel" / "receiver-payload.json"


@pytest.fixture(scope="module")
def spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_spec_file_exists():
    assert SPEC.is_file(), f"missing receiver spec: {SPEC}"


def test_spec_is_not_enabled(spec):
    assert spec.get("enabled") is False
    assert spec.get("_status", "").startswith("NOT ACTIVE")


def test_trigger_is_issue_comment_created_on_github(spec):
    trigger = spec["trigger"]
    assert trigger["type"] == "event"
    assert trigger["source"] == "github"
    assert trigger["on"] == "issue_comment.created"


def test_filter_pins_marker_repo_issue_and_excludes_bots(spec):
    filt = spec["trigger"]["filter"]
    assert "icontains(comment.body, '@watcher')" in filt
    assert "repository.full_name == 'madnessgate44-debug/brain'" in filt
    assert "issue.number == `240`" in filt, "JMESPath numbers require backticks"
    assert "ends_with(sender.login, '[bot]')" in filt


def test_prompt_treats_input_as_untrusted_and_dedups(spec):
    prompt = spec["prompt"]
    assert "untrusted DATA" in prompt
    assert "watcher:seen:" in prompt
    assert "[TO-CHATGPT]" in prompt
