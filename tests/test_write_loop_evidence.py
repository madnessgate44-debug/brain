"""Tests for scripts/write_loop_evidence.py — the producer of the live-run proof.

The depth finding "Committed evidence of a live issue -> PR run" is OK only when one file names
the issue, the workflow run, and the pull request. Before this producer existed, the only writer
(`start_session_loop.py`) emitted a conversation link, which the finding rejects, so the sole
conforming file was typed by hand — an artifact, not a producer (W3).

The round-trip test is the important one: it runs the writer and then the real checker, so the
two cannot drift.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PRODUCER = _ROOT / "scripts" / "write_loop_evidence.py"
_CHECKER = _ROOT / "watcher" / "knowledge" / "tools" / "purpose_audit.py"

ISSUE = "https://github.com/madnessgate44-debug/brain/issues/208"
RUN = "https://github.com/madnessgate44-debug/brain/actions/runs/38148411690"
PR = "https://github.com/madnessgate44-debug/brain/pull/218"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def producer():
    return _load(_PRODUCER, "write_loop_evidence")


@pytest.fixture(scope="module")
def pa():
    return _load(_CHECKER, "watcher_purpose_audit")


def test_writer_emits_the_three_links(producer, tmp_path):
    dest = producer.write_evidence(ISSUE, RUN, PR, tmp_path, stamp="20261119-120000")
    body = dest.read_text(encoding="utf-8")
    assert f"- issue: {ISSUE}" in body
    assert f"- workflow run: {RUN}" in body
    assert f"- pr: {PR}" in body
    assert "Status: LIVE" in body
    assert dest.name == "company-loop-20261119-120000-issue208-pr218.md"


def test_written_file_satisfies_the_checker(producer, pa, tmp_path):
    """Round trip: the producer's output is what the check accepts, with no hand editing."""
    dest = producer.write_evidence(ISSUE, RUN, PR, tmp_path)
    proof = pa._run_proof(dest)
    assert proof["issue"] == ISSUE
    assert proof["run"] == RUN
    assert proof["pr"] == PR
    assert pa._same_repository(proof)


def test_written_file_turns_the_depth_finding_ok(producer, tmp_path, pa):
    """The finding reads OK from a tree whose only evidence file this producer wrote."""
    (tmp_path / "brain" / "company").mkdir(parents=True)
    (tmp_path / "brain" / "company" / "roles.py").write_text(
        '    SpecialistRole(\n        key="developer",\n    ),\n', encoding="utf-8")
    (tmp_path / "brain" / "company" / "agent_runner.py").write_text(
        '    if role_key == "developer":\n        run_openhands_developer()\n', encoding="utf-8")
    (tmp_path / "brain" / "company" / "openhands_developer.py").write_text(
        "TemporaryDirectory()\n_MAX_FILES = 30\n_MAX_FILE_BYTES = 200000\n", encoding="utf-8")
    producer.write_evidence(ISSUE, RUN, PR, tmp_path / "watcher" / "knowledge" / "evidence")

    finding = next(d for d in pa.depth_findings(tmp_path / "brain") if d["id"] == "live-run-evidence")
    assert finding["status"] == "OK", finding["evidence"]
    assert any(ISSUE in e and RUN in e and PR in e for e in finding["evidence"])


def test_writer_rejects_a_conversation_link_as_the_pull_request(producer, tmp_path):
    """The old writer's only output must not pass: a conversation is not a pull request."""
    with pytest.raises(ValueError, match="pull request"):
        producer.write_evidence(
            ISSUE, RUN, "https://app.all-hands.dev/canvas/conversations/abc", tmp_path)
    assert not list(tmp_path.glob("*.md"))


def test_writer_rejects_links_in_different_repositories(producer, tmp_path):
    with pytest.raises(ValueError, match="one repository"):
        producer.write_evidence(
            ISSUE, "https://github.com/other/repo/actions/runs/38148411690", PR, tmp_path)
    assert not list(tmp_path.glob("*.md"))


@pytest.mark.parametrize("bad", [
    "https://github.com/madnessgate44-debug/brain/issues/",
    "https://github.com/madnessgate44-debug/brain/issues/abc",
    "http://github.com/madnessgate44-debug/brain/issues/208",
    "https://gitlab.com/madnessgate44-debug/brain/issues/208",
    "",
])
def test_writer_rejects_a_malformed_issue_url(producer, tmp_path, bad):
    with pytest.raises(ValueError, match="issue"):
        producer.write_evidence(bad, RUN, PR, tmp_path)


def test_cli_exits_nonzero_and_writes_nothing_on_a_bad_link(producer, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["write_loop_evidence.py", "--issue", ISSUE, "--run", RUN,
         "--pr", "https://example.com/not-a-pr", "--out", str(tmp_path)],
    )
    assert producer.main() == 1
    assert "::error::" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.md"))
