"""Tests for scripts/start_session_loop.py — the session agent's loop starter."""

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "scripts" / "start_session_loop.py"


@pytest.fixture(scope="module")
def starter():
    spec = importlib.util.spec_from_file_location("start_session_loop", _MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_targets_repo_and_branch(starter):
    payload = starter.build_payload("do the task", "owner/repo", "main", "title")
    assert payload["selected_repository"] == "owner/repo"
    assert payload["selected_branch"] == "main"
    assert payload["title"] == "title"
    assert payload["initial_message"]["content"][0]["text"] == "do the task"


def test_parse_start_task_reads_id_and_conversation(starter):
    start_id, conv = starter.parse_start_task({"id": "start-1", "app_conversation_id": "conv-9"})
    assert (start_id, conv) == ("start-1", "conv-9")


def test_parse_start_task_handles_missing_conversation(starter):
    start_id, conv = starter.parse_start_task({"id": "start-1"})
    assert start_id == "start-1" and conv == ""


def test_dry_run_writes_evidence_without_a_conversation(starter, tmp_path):
    dest = starter.write_evidence(tmp_path, "owner/repo", "main", "", "", dry=True)
    text = dest.read_text(encoding="utf-8")
    assert "DRY RUN" in text
    assert "app_conversation_id: (none)" in text


def test_live_evidence_records_the_link(starter, tmp_path):
    dest = starter.write_evidence(
        tmp_path, "owner/repo", "main", "conv-1", "https://x/y", dry=False
    )
    text = dest.read_text(encoding="utf-8")
    assert "LIVE" in text
    assert "https://x/y" in text


def test_first_reads_a_list_response(starter):
    """V1 `?ids=` endpoints return a JSON list; a missing id comes back as [null]."""
    assert starter._first([{"id": "a"}, {"id": "b"}]) == {"id": "a"}
    assert starter._first([None]) == {}
    assert starter._first([]) == {}


def test_first_reads_a_wrapped_items_response(starter):
    assert starter._first({"items": [{"id": "a"}]}) == {"id": "a"}
    assert starter._first({"id": "a"}) == {"id": "a"}
    assert starter._first(None) == {}


def test_wait_for_ready_accepts_a_list_start_task(starter, monkeypatch):
    """Regression: the live run crashed on `list.get` before writing evidence."""
    monkeypatch.setattr(starter, "_get", lambda url, key, **kw: [{"app_conversation_id": "conv-7"}])
    assert starter.wait_for_ready("start-1", "key") == "conv-7"


def test_ui_url_accepts_a_list_record(starter, monkeypatch):
    monkeypatch.setattr(
        starter, "_get", lambda url, key, **kw: [{"conversation_ui_url": "https://u/v"}]
    )
    assert starter.ui_url("conv-7", "key") == "https://u/v"
    monkeypatch.setattr(starter, "_get", lambda url, key, **kw: [None])
    assert starter.ui_url("conv-7", "key").endswith("/canvas/conversations/conv-7")


def test_started_but_not_ready_still_writes_evidence(starter, monkeypatch, tmp_path):
    """A started conversation must not be invisible, but with no link it is not a live proof."""
    monkeypatch.setenv(starter.KEY_ENV, "key")
    monkeypatch.setattr(starter, "_post", lambda url, body, key, **kw: {"id": "start-1"})
    monkeypatch.setattr(
        starter, "wait_for_ready", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("not ready"))
    )
    task = tmp_path / "task.md"
    task.write_text("do it", encoding="utf-8")
    out = tmp_path / "ev"
    monkeypatch.setattr(
        sys, "argv", ["start_session_loop.py", "--task-file", str(task), "--out", str(out)]
    )
    assert starter.main() == 1
    text = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "not yet resolved" in text
    assert "link: (none)" in text
