"""Tests for the friction detector (owner frustration + churn, read from the record)."""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "friction.py"
)


@pytest.fixture(scope="module")
def fr():
    spec = importlib.util.spec_from_file_location("watcher_friction", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frustration_detects_real_complaint(fr):
    msgs = [{"time": "2026-11-03T10:00:00Z", "text": "you are pretending and hallucinating, no progress"}]
    f = fr.frustration_findings(msgs)[0]
    assert f["status"] == "PARTIAL"
    assert any("pretend" in e.lower() or "hallucinat" in e.lower() for e in f["evidence"])


def test_frustration_ignores_negated_mention(fr):
    """'I do not pretend to know the diagnosis' is not an accusation."""
    msgs = [{"time": "2026-11-03T10:00:00Z", "text": "I do not pretend to know the diagnosis."}]
    f = fr.frustration_findings(msgs)[0]
    assert "0 of 1" in f["finding"]


def test_frustration_word_boundary_no_false_positive(fr):
    """'jobs' must not match the signal 'bs'."""
    msgs = [{"time": "2026-11-03T10:00:00Z", "text": "we finished all the jobs today"}]
    f = fr.frustration_findings(msgs)[0]
    assert "0 of 1" in f["finding"]


def test_stale_transcript_is_reported(fr):
    msgs = [{"time": "2026-11-01T10:00:00Z", "text": "hello"}]
    f = fr.frustration_findings(msgs)[0]
    assert f["status"] == "PARTIAL"
    assert any("stale" in e for e in f["evidence"])


def test_missing_transcript_is_missing_not_ok(fr):
    f = fr.frustration_findings([])[0]
    assert f["status"] == "MISSING"


def test_back_and_forth_flags_a_repeated_topic(fr):
    msgs = [
        {"time": "2026-11-01T00:00:00Z", "text": "you are not looping"},
        {"time": "2026-11-02T00:00:00Z", "text": "still not looping, start the loop"},
    ]
    f = fr.back_and_forth_findings(msgs)[0]
    assert f["status"] == "PARTIAL"
    assert "loop" in f["finding"]


def test_collect_reads_the_real_record(fr):
    findings = fr.collect()
    assert findings
    for f in findings:
        assert f["status"] in {"OK", "PARTIAL", "MISSING"}
        assert f["evidence"]


def test_render_marks_status(fr):
    text = fr.render([{"finding": "x", "status": "PARTIAL", "evidence": ["e"]}], "2026-11-03")
    assert "[~] **x**" in text
    assert "# Friction — 2026-11-03" in text
