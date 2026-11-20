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


def _git_commit(repo: Path, message: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "add", "-A"], cwd=repo, capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    subprocess.run(
        ["git", "commit", "-qm", message], cwd=repo, capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"},
    )


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


def test_full_history_is_not_flagged_as_truncated(status, tmp_path):
    repo = _git_repo(tmp_path, docs_only=1, code=9)
    report = status.build(repo, commits=60)
    assert report["history_truncated"] is False
    assert "truncated" not in status.render(report).lower()


def _clean_git_repo(path: Path, docs_only: int, code: int) -> Path:
    """A repo where all three agents are scheduled, so only the ratio can fail the gate."""
    repo = _git_repo(path, docs_only=docs_only, code=code)
    wf = repo / ".github" / "workflows"
    for name, run in (
        ("session-agent-loop.yml", "python3 scripts/start_session_loop.py"),
        ("shadow-audit.yml", "python3 shadow/shadow.py"),
        ("watcher-daily.yml", "python3 watcher/knowledge/tools/purpose_audit.py"),
    ):
        (wf / name).write_text(
            f"on:\n  schedule:\n    - cron: '0 5 * * *'\njobs:\n  x:\n    steps:\n"
            f"      - run: {run}\n",
            encoding="utf-8",
        )
    _git_commit(repo, "schedules")
    return repo


def test_shallow_clone_cannot_pass_the_ratchet(status, tmp_path):
    """W3: a 92% report-only breach read as 0/1 (0%) on a shallow clone and passed the gate.

    The ratio must be computed over the requested window; when the checkout cannot show that
    window the finding is unmeasurable, and an unmeasurable finding must fail, not pass.
    """
    import subprocess

    src = _clean_git_repo(tmp_path / "src", docs_only=12, code=1)  # 12/13 = 92%
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(shallow)],
        capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    full = status.build(src, commits=60)
    assert full["report_only_over_limit"] is True   # the real breach
    assert full["missing_expected"] == []           # nothing else can fail this repo

    cut = status.build(shallow, commits=60)
    assert cut["commits_with_files"] < 60           # the sample is truncated
    assert cut["missing_expected"] == []            # so truncation is the only failure left
    assert cut["report_only_over_limit"] is False   # the old code's false pass
    assert cut["history_truncated"] is True
    text = status.render(cut)
    assert "FAIL" in text and "fetch-depth" in text


def test_truncated_history_exits_non_zero(status, tmp_path, monkeypatch):
    """The gate reads the exit code: a truncated sample must fail it, not just print a line.

    The repo has every agent scheduled, so a non-zero exit here can only come from the
    truncation — the old code exited 0 on this exact tree.
    """
    import subprocess

    src = _clean_git_repo(tmp_path / "src", docs_only=2, code=2)
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(shallow)],
        capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    monkeypatch.setattr("sys.argv", ["agent_status.py", "--repo", str(src), "--commits", "60"])
    assert status.main() == 0  # full history, healthy ratio
    monkeypatch.setattr("sys.argv", ["agent_status.py", "--repo", str(shallow), "--commits", "60"])
    assert status.main() == 1  # same tree, truncated window


def test_zero_commits_means_not_measured_not_truncated(status, tmp_path):
    """`--commits 0` opts out of the ratio; it must not be reported as a truncation failure."""
    report = status.build(_repo(tmp_path), commits=0)
    assert report["history_truncated"] is False
    assert report["commits_with_files"] == 0


def test_every_ci_job_that_reads_the_ratio_checks_out_full_history():
    """The gate is only as good as the history it reads.

    Three loops ran it on a 1-commit checkout and the ratio read `0/1 (0%)`. Scoped to CI jobs
    that gate this repository (push/pull_request) and read the ratio: `agent_status.py` directly,
    or the full suite, which includes `test_shadow_purpose_gate.py`'s assertion that the real
    repo passes its own ratio. Jobs that run pytest inside a throwaway clone of another repo, or
    a single test file, do not read this history and are not covered.
    """
    import re

    import yaml

    root = Path(__file__).resolve().parents[1]
    full_suite = re.compile(r"^\s*(?:python3? -m )?pytest(?:\s+-[a-zA-Z]+)*\s*$")
    shallow = []
    for wf in sorted((root / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        triggers = doc.get("on") or doc.get(True) or {}
        if not {"push", "pull_request"} & set(triggers if isinstance(triggers, dict) else []):
            continue
        for job, spec in (doc.get("jobs") or {}).items():
            steps = spec.get("steps") or []
            lines = [ln for s in steps for ln in str(s.get("run", "")).splitlines()]
            reads_ratio = any("agent_status.py" in ln or full_suite.match(ln) for ln in lines)
            if not reads_ratio:
                continue
            depths = [
                (s.get("with") or {}).get("fetch-depth")
                for s in steps
                if str(s.get("uses", "")).startswith("actions/checkout")
            ]
            if not depths or any(d != 0 for d in depths):
                shallow.append(f"{wf.name}:{job} checkout={depths}")

    assert not shallow, "these CI jobs read the W1 ratio without full history: " + "; ".join(shallow)
