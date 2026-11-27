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


# --- record the issue -> PR trace (W3: a started conversation is not the proof) ----------

ISSUE = "https://github.com/o/r/issues/7"
PULL = "https://github.com/o/r/pull/8"
RUN = "https://github.com/o/r/actions/runs/9"


def _loop_tree(tmp_path: Path) -> Path:
    """The smallest tree the depth check will scan: one role, one loop, one evidence dir."""
    company = tmp_path / "brain" / "company"
    company.mkdir(parents=True)
    (company / "roles.py").write_text('SpecialistRole(\n    key="developer",\n)\n', encoding="utf-8")
    (company / "agent_runner.py").write_text(
        'if role_key == "developer":\n    run_openhands_developer()\n', encoding="utf-8"
    )
    (company / "openhands_developer.py").write_text(
        "_MAX_FILES = 30\n_MAX_FILE_BYTES = 200000\n", encoding="utf-8"
    )
    return tmp_path / "brain"


def _live_finding(starter, root: Path) -> dict:
    audit = starter._load_audit()
    return next(d for d in audit.depth_findings(root) if "live issue" in d["finding"])


def test_record_trace_turns_the_depth_finding_ok(starter, tmp_path):
    """Writer and checker must not drift: record with the writer, then run the real check."""
    root = _loop_tree(tmp_path)
    ev = starter.write_evidence(tmp_path / "watcher" / "knowledge" / "evidence", "o/r", "main",
                                "conv-1", "https://app.all-hands.dev/canvas/conversations/conv-1",
                                dry=False)
    assert _live_finding(starter, root)["status"] == "PARTIAL"
    starter.record_trace(ev, ISSUE, PULL, RUN)
    finding = _live_finding(starter, root)
    assert finding["status"] == "OK"
    assert any(ISSUE in e and PULL in e for e in finding["evidence"])


def test_record_trace_keeps_the_run_links_and_marks_the_status(starter, tmp_path):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    starter.record_trace(ev, ISSUE, PULL, RUN)
    text = ev.read_text(encoding="utf-8")
    assert "Status: LIVE — issue carried to a pull request" in text
    assert "- app_conversation_id: conv-1" in text
    assert "- link: https://u/v" in text
    assert text.count("- issue:") == 1 and text.count("- pull_request:") == 1
    assert "- run: " + RUN in text


def test_record_trace_takes_the_run_from_the_actions_environment(starter, monkeypatch, tmp_path):
    """The writer must be able to satisfy its own check without a hand-typed run."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "9")
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    starter.record_trace(ev, ISSUE, PULL)
    assert "- run: " + RUN in ev.read_text(encoding="utf-8")


def test_record_trace_refuses_a_trace_with_no_run(starter, monkeypatch, tmp_path):
    """An issue -> PR pair alone is not proof that a run produced it (W3)."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    original = ev.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        starter.record_trace(ev, ISSUE, PULL)
    assert ev.read_text(encoding="utf-8") == original


def test_record_trace_is_idempotent(starter, tmp_path):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    starter.record_trace(ev, ISSUE, PULL, RUN)
    first = ev.read_text(encoding="utf-8")
    starter.record_trace(ev, ISSUE, PULL, RUN)
    assert ev.read_text(encoding="utf-8") == first


def test_record_trace_leaves_one_blank_line_under_the_status(starter, tmp_path):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    starter.record_trace(ev, ISSUE, PULL, RUN)
    lines = ev.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# Session agent loop")
    assert lines[1].startswith("Status:")
    assert lines[2] == "" and lines[3].startswith("- repository:")


def test_record_trace_refuses_a_pr_on_another_repository(starter, tmp_path):
    """A pull request on a different repository does not close this repository's issue."""
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    original = ev.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        starter.record_trace(ev, ISSUE, "https://github.com/other/repo/pull/8")
    assert ev.read_text(encoding="utf-8") == original


def test_record_trace_refuses_a_conversation_url_as_the_pull_request(starter, tmp_path):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    original = ev.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        starter.record_trace(ev, ISSUE, "https://app.all-hands.dev/canvas/conversations/conv-1")
    assert ev.read_text(encoding="utf-8") == original


def test_record_cli_requires_both_links(starter, monkeypatch, tmp_path):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    monkeypatch.setattr(sys, "argv", ["start_session_loop.py", "--record", str(ev), "--issue", ISSUE])
    assert starter.main() == 2
    assert "- issue:" not in ev.read_text(encoding="utf-8")


def test_record_cli_writes_the_trace(starter, monkeypatch, tmp_path, capsys):
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    monkeypatch.setattr(sys, "argv", ["start_session_loop.py", "--record", str(ev),
                                      "--issue", ISSUE, "--pull-request", PULL, "--run", RUN])
    assert starter.main() == 0
    assert "trace recorded" in capsys.readouterr().out
    assert "- pull_request: " + PULL in ev.read_text(encoding="utf-8")
    assert "- run: " + RUN in ev.read_text(encoding="utf-8")


def test_record_cli_exits_2_when_the_trace_has_no_run(starter, monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    ev = starter.write_evidence(tmp_path, "o/r", "main", "conv-1", "https://u/v", dry=False)
    monkeypatch.setattr(sys, "argv", ["start_session_loop.py", "--record", str(ev),
                                      "--issue", ISSUE, "--pull-request", PULL])
    assert starter.main() == 2
    assert "actions/runs" in capsys.readouterr().err
