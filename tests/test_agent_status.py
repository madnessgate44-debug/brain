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


def _git_repo(tmp_path: Path, docs_only: int, code: int) -> Path:
    import subprocess

    repo = _repo(tmp_path)
    def git(*a):
        subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})
    git("init", "-q")
    for i in range(code):
        (repo / f"c{i}.py").write_text("x=1\n", encoding="utf-8")
        git("add", "-A"); git("commit", "-qm", f"code {i}")
    for i in range(docs_only):
        (repo / f"d{i}.md").write_text("x\n", encoding="utf-8")
        git("add", "-A"); git("commit", "-qm", f"doc {i}")
    return repo


def test_report_only_ratio_and_gate(status, tmp_path):
    repo = _git_repo(tmp_path, docs_only=8, code=2)  # 8/10 = 80%
    report = status.build(repo, commits=60)
    assert report["report_only"] == 8 and report["commits_with_files"] == 10
    assert report["report_only_pct"] == 80.0
    assert report["report_only_over_limit"] is True  # 80% > 40% ratchet


def test_gate_passes_below_the_ratchet(status, tmp_path):
    repo = _git_repo(tmp_path, docs_only=1, code=9)  # 10%
    report = status.build(repo, commits=60)
    assert report["report_only_over_limit"] is False


def test_render_shows_the_fail_line(status, tmp_path):
    repo = _git_repo(tmp_path, docs_only=8, code=2)
    text = status.render(status.build(repo, commits=60))
    assert "FAIL" in text and "ratchet" in text
