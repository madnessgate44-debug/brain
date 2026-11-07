"""Tests for scripts/start_session_loop.py — the session agent's loop starter."""

import importlib.util
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
    dest = starter.write_evidence(tmp_path, "owner/repo", "main", "conv-1", "https://x/y", dry=False)
    text = dest.read_text(encoding="utf-8")
    assert "started" in text
    assert "https://x/y" in text
