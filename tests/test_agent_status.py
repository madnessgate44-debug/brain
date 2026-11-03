"""Tests for scripts/agent_status.py — the W1/W4 check over the three agents."""

import importlib.util
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "scripts" / "agent_status.py"


@pytest.fixture(scope="module")
def status():
    spec = importlib.util.spec_from_file_location("agent_status", _MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> Path:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "watcher-daily.yml").write_text("on:\n  schedule:\n    - cron: '0 6 * * *'\n", encoding="utf-8")
    (wf / "shadow-audit.yml").write_text("on:\n  pull_request:\n", encoding="utf-8")
    return tmp_path


def test_classifies_workflows_by_name(status, tmp_path):
    owned = status.classify_workflows(_repo(tmp_path))
    assert "watcher-daily.yml" in owned["watcher"]
    assert "shadow-audit.yml" in owned["shadow"]
    assert owned["session"] == []


def test_session_workflow_is_assigned_to_session_not_watcher(status, tmp_path):
    repo = _repo(tmp_path)
    # A session workflow that also touches watcher paths must land on the session agent only.
    (repo / ".github" / "workflows" / "session-agent-loop.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 5 * * *'\njobs:\n  x:\n    steps:\n"
        "      - run: python3 scripts/start_session_loop.py\n"
        "      - run: python3 watcher/knowledge/tools/purpose_audit.py\n",
        encoding="utf-8",
    )
    owned = status.classify_workflows(repo)
    assert "session-agent-loop.yml" in owned["session"]
    assert "session-agent-loop.yml" not in owned["watcher"]


def test_scheduled_detects_cron_only(status, tmp_path):
    scheduled = status.scheduled_workflows(_repo(tmp_path))
    assert "watcher-daily.yml" in scheduled
    assert "shadow-audit.yml" not in scheduled


def test_session_loop_passes_when_its_workflow_is_scheduled(status, tmp_path):
    repo = _repo(tmp_path)
    (repo / ".github" / "workflows" / "session-agent-loop.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 5 * * *'\njobs:\n  x:\n    steps:\n"
        "      - run: python3 scripts/start_session_loop.py\n",
        encoding="utf-8",
    )
    report = status.build(repo, commits=0)
    by = {a["agent"]: a for a in report["agents"]}
    assert by["session"]["has_scheduled_loop"] is True
    assert "session" not in report["open_gaps"]


def test_missing_expected_flags_a_scheduled_agent_that_lost_its_loop(status, tmp_path):
    repo = _repo(tmp_path)
    # Shadow's only workflow is unscheduled, so it is expected-scheduled but has no cron.
    report = status.build(repo, commits=0)
    assert "shadow" in report["missing_expected"]


def test_render_names_the_open_gap(status, tmp_path):
    text = status.render(status.build(_repo(tmp_path), commits=0))
    assert "session" in text
    assert "W4" in text
