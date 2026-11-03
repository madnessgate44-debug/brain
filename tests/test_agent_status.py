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


def test_scheduled_detects_cron_only(status, tmp_path):
    scheduled = status.scheduled_workflows(_repo(tmp_path))
    assert "watcher-daily.yml" in scheduled
    assert "shadow-audit.yml" not in scheduled


def test_session_is_reported_as_an_open_gap_not_a_pass(status, tmp_path):
    report = status.build(_repo(tmp_path), commits=0)
    by = {a["agent"]: a for a in report["agents"]}
    assert by["session"]["has_scheduled_loop"] is False
    assert "session" in report["open_gaps"]
    assert "session" not in report["missing_expected"]  # known gap, not a regression


def test_missing_expected_flags_a_scheduled_agent_that_lost_its_loop(status, tmp_path):
    repo = _repo(tmp_path)
    # Shadow's only workflow is unscheduled, so it is expected-scheduled but has no cron.
    report = status.build(repo, commits=0)
    assert "shadow" in report["missing_expected"]


def test_render_names_the_open_gap(status, tmp_path):
    text = status.render(status.build(_repo(tmp_path), commits=0))
    assert "session" in text
    assert "W4" in text
