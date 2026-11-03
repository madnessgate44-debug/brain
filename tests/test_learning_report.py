"""Tests for the Watcher learning report (open issues + action plans, generated on its own)."""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "watcher" / "knowledge" / "tools" / "learning_report.py"
)


@pytest.fixture(scope="module")
def lr():
    spec = importlib.util.spec_from_file_location("watcher_learning_report", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_collects_open_items_with_plans(lr):
    data = lr.collect()
    assert data["items"], "there must be open issues to plan for"
    for item in data["items"]:
        for field in ("issue", "impact", "fix", "owner", "first_step", "check"):
            assert item.get(field), f"{field} missing on {item['issue']!r}"


def test_every_item_has_a_concrete_first_step_not_a_placeholder(lr):
    for item in lr.collect()["items"]:
        assert len(item["first_step"]) > 20
        assert "TODO" not in item["first_step"]


def test_known_gap_maps_to_its_specific_remedy(lr):
    plan = lr._remedy("Patch contract bounds what the agent may change")
    assert "deletion" in plan["fix"].lower()
    assert plan["check"].startswith("purpose_audit.py")


def test_unknown_gap_falls_back_but_still_has_a_plan(lr):
    plan = lr._remedy("Some brand new finding nobody mapped")
    assert plan["fix"] and plan["first_step"] and plan["check"]


def test_render_contains_every_plan_field(lr):
    text = lr.render(lr.collect(), "2026-11-03")
    assert "# Watcher learning report — 2026-11-03" in text
    assert "How I intend to fix it" in text
    assert "Done when" in text
    assert "Generated automatically" in text


def test_report_is_wired_into_the_scheduled_learning_loop(lr):
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
          / "watcher-learning.yml").read_text(encoding="utf-8")
    assert "learning_report.py" in wf
    assert "schedule:" in wf


def test_report_shows_videos_watched_with_lesson_and_action(lr):
    data = lr.collect()
    assert data["watched"], "the report must show what the Watcher watched"
    for w in data["watched"]:
        assert w["url"].startswith("http")
        assert w["transcript"].endswith(".txt")
        assert w["learned"] and w["learned"] != "(no summary written)"
        assert w["action"] and w["action"] != "(no action written)"


def test_render_lists_watched_videos_section(lr):
    text = lr.render(lr.collect(), "2026-11-03")
    assert "## Videos the Watcher watched" in text
    assert "What he learned" in text
    assert "What he will do about it" in text


def test_render_says_none_when_no_lessons_exist(lr, tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "watched_sources", lambda *a, **k: [])
    text = lr.render({"items": [], "watched": []}, "2026-11-03")
    assert "**None yet.**" in text
    assert "gap, not a pass" in text


def test_open_weaknesses_skips_closed(lr):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "WEAKNESSES.md"
        ledger.write_text(
            "## W1 — open one\n- **Belongs to:** both.\n- **Check:** a metric\n\n"
            "## W2 — done one\n- **Belongs to:** all three.\n- **Check:** x\n- CLOSED 2026-01-01\n",
            encoding="utf-8",
        )
        items = lr.open_weaknesses(ledger)
    titles = [i["issue"] for i in items]
    assert any("open one" in t for t in titles)
    assert not any("done one" in t for t in titles)
