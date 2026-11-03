"""Offline tests for the Watcher lesson builder (watcher/knowledge/tools/learn.py).

These cover the pure logic — section parsing, the honest no-key scaffold, and the lesson
shape — so the module is exercised on every PR without a model, network, or key. Live
model behaviour is proven separately by the learning-loop workflow.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "learn.py"


@pytest.fixture(scope="module")
def learn():
    spec = importlib.util.spec_from_file_location("watcher_learn", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRANSCRIPT = "[00:00] hello\n[00:05] a retire step keeps a queue from growing forever\n"


def test_slugify(learn):
    assert learn.slugify("Why Backlogs Keep Growing!") == "why-backlogs-keep-growing"
    assert learn.slugify("") == "lesson"


def test_extract_sections_splits_headings(learn):
    md = "## What this teaches\nthe idea\n\n## Diagnosis\nSYMPTOM: x\n"
    got = learn.extract_sections(md)
    assert got["What this teaches"] == "the idea"
    assert got["Diagnosis"] == "SYMPTOM: x"


def test_scaffold_without_key_invents_nothing(learn):
    """No model route -> every section is an explicit TODO, transcript preserved."""
    md = learn.build_lesson(TRANSCRIPT, "Test", "src", "", None)
    for section in learn.SECTIONS:
        assert f"## {section}" in md
    assert "TODO" in md
    assert "no model route" in md
    # The transcript is always kept as the evidence.
    assert TRANSCRIPT.strip() in md
    # Nothing is asserted as a finding.
    assert "ROOT CAUSE" not in md


def test_lesson_records_source_and_question(learn):
    md = learn.build_lesson(TRANSCRIPT, "Backlog lesson", "https://example/v", "why?", None)
    assert "- **Source:** https://example/v" in md
    assert "Question for this source:** why?" in md


def test_sections_include_job_and_north_star(learn):
    """The six lesson parts exist, including which job it serves."""
    assert "Which job it serves" in learn.SECTIONS
    assert "Diagnosis" in learn.SECTIONS
    assert "How to teach it" in learn.SECTIONS
