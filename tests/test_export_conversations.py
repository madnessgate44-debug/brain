"""Offline tests for the conversation exporter's pure helpers (no API, no network).

The network paths (list_conversations / pull_events) are exercised by the scheduled
watcher-session-log.yml workflow; these tests cover the logic that classifies owner
text vs automation templates and redacts secrets.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("export_conversations", ROOT / "scripts" / "export_conversations.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def _user_event(text):
    return {"source": "user", "llm_message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def test_owner_text_returns_verbatim_words():
    ev = _user_event("delete everything in thisrepo")
    assert ex.owner_text(ev) == "delete everything in thisrepo"


def test_owner_text_preserves_garbled_speech():
    raw = "why there is something in a sandbox it should be published on main and working"
    assert ex.owner_text(_user_event(raw)) == raw


def test_owner_text_rejects_automation_templates():
    for tmpl in ("## Cloned Repositories\n\nfoo", "You are requested to fix issue #240",
                 "[Stop hook feedback] x", "Read the attached WATCHER.md in full"):
        assert ex.owner_text(_user_event(tmpl)) is None


def test_owner_text_ignores_non_user_sources():
    assert ex.owner_text({"source": "environment", "llm_message": {"role": "user", "content": "x"}}) is None
    assert ex.owner_text({"source": "user"}) is None


def test_is_automation_conversation():
    assert ex.is_automation_conversation({"title": "Openhands loop — 2026-11-01 12:02:01 UTC"})
    assert ex.is_automation_conversation({"title": "GitHub Issue #240: Watcher is alive"})
    assert not ex.is_automation_conversation({"title": "Watcher"})


def test_redact_removes_real_secret_shapes():
    assert ex.redact("token gAAAAA" + "A" * 30) == "token [REDACTED-FERNET]"
    assert ex.redact("key sk-" + "a" * 30) == "key [REDACTED-OPENAI]"
    assert ex.redact("ghp_" + "b" * 30) == "[REDACTED-GITHUB]"
    assert "AIza" not in ex.redact("x AIza" + "c" * 35 + " y")
    # A token embedded in a git URL is redacted (the GitHub-token rule fires first).
    red = ex.redact("https://ghp_" + "d" * 30 + "@github.com/x")
    assert "ghp_" not in red and red.endswith("@github.com/x")


def test_redact_leaves_plain_doc_text_alone():
    # Documentation that merely names a pattern must survive (no false redaction).
    assert ex.redact("starts with `gAAAAA`") == "starts with `gAAAAA`"


def test_text_of_flattens_blocks():
    assert ex.text_of([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert ex.text_of("plain") == "plain"
