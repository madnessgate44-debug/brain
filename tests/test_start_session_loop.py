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
    dest = starter.write_evidence(tmp_path, "owner/repo", "main", "conv-1", "https://x/y", dry=False)
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
    monkeypatch.setattr(starter, "_get", lambda url, key, **kw: [{"conversation_ui_url": "https://u/v"}])
    assert starter.ui_url("conv-7", "key") == "https://u/v"
    monkeypatch.setattr(starter, "_get", lambda url, key, **kw: [None])
    assert starter.ui_url("conv-7", "key").endswith("/canvas/conversations/conv-7")


def test_started_but_not_ready_still_writes_evidence(starter, monkeypatch, tmp_path):
    """A started conversation must not be invisible, but with no link it is not a live proof."""
    monkeypatch.setenv(starter.KEY_ENV, "key")
    monkeypatch.setattr(starter, "_post", lambda url, body, key, **kw: {"id": "start-1"})
    monkeypatch.setattr(starter, "wait_for_ready",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("not ready")))
    task = tmp_path / "task.md"
    task.write_text("do it", encoding="utf-8")
    out = tmp_path / "ev"
    monkeypatch.setattr(sys, "argv",
                        ["start_session_loop.py", "--task-file", str(task), "--out", str(out)])
    assert starter.main() == 1
    text = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "not yet resolved" in text
    assert "link: (none)" in text


# --- the proof is produced, not typed (W3) -------------------------------------------

_PR = "https://github.com/madnessgate44-debug/brain/pull/307"
_RUN = "https://github.com/madnessgate44-debug/brain/actions/runs/42477372401"
_CONV = "https://app.all-hands.dev/canvas/conversations/e166ab9ce3864fa89ded6f01dd480097"


def _live_evidence(starter, tmp_path, *, run: str = "") -> Path:
    dest = starter.write_evidence(tmp_path / "ev", "madnessgate44-debug/brain", "main",
                                  "e166ab9ce3864fa89ded6f01dd480097", _CONV, dry=False)
    if run:
        dest.write_text(dest.read_text(encoding="utf-8") + f"- workflow run: {run}\n",
                        encoding="utf-8")
    return dest


def test_run_url_from_env_derives_the_actions_run(starter):
    env = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "42"}
    assert starter.run_url_from_env(env) == "https://github.com/owner/repo/actions/runs/42"


def test_run_url_from_env_is_empty_outside_actions(starter):
    assert starter.run_url_from_env({}) == ""


def test_record_pull_request_writes_links_the_checker_accepts(starter, tmp_path, monkeypatch):
    """The producer and the check cannot drift: the checker reads back what this wrote."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    dest = _live_evidence(starter, tmp_path, run=_RUN)
    starter.record_pull_request(dest, _PR)
    checker = starter._checker()
    assert checker.pull_request_link(dest) == _PR
    assert checker.run_link(dest) == _RUN  # the run the workflow wrote is preserved
    assert checker.evidence_link(dest) == _CONV


def test_record_pull_request_replaces_a_previous_pull_request(starter, tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    dest = _live_evidence(starter, tmp_path)
    starter.record_pull_request(dest, _PR)
    starter.record_pull_request(dest, "https://github.com/madnessgate44-debug/brain/pull/308")
    text = dest.read_text(encoding="utf-8")
    assert text.count("- pr:") == 1
    assert "pull/307" not in text


def test_record_pull_request_rejects_a_non_pull_request_url(starter, tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    dest = _live_evidence(starter, tmp_path)
    with pytest.raises(ValueError, match="not a GitHub pull request URL"):
        starter.record_pull_request(dest, _CONV)


def test_record_pull_request_rejects_a_file_with_no_conversation(starter, tmp_path):
    dry = starter.write_evidence(tmp_path / "ev", "owner/repo", "main", "", "", dry=True)
    with pytest.raises(ValueError, match="no conversation link"):
        starter.record_pull_request(dry, _PR)


def test_record_pr_cli_fails_loudly_on_a_bad_url(starter, tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    dest = _live_evidence(starter, tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["start_session_loop.py", "--record-pr", str(dest), "--pr", "not-a-url"])
    assert starter.main() == 1
    assert "- pr:" not in dest.read_text(encoding="utf-8")


def test_write_evidence_records_the_run_inside_actions(starter, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "42477372401")
    dest = starter.write_evidence(tmp_path, "owner/repo", "main", "conv-1", _CONV, dry=False)
    assert starter._checker().run_link(dest) == "https://github.com/owner/repo/actions/runs/42477372401"
