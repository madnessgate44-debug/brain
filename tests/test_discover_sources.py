"""Offline tests for the Watcher self-directed discovery (watcher/knowledge/tools/discover.py).

Covers the pure logic — focus parsing, dedup against watched sources, queue append — with
the YouTube search stubbed, so nothing here touches the network.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "discover.py"


@pytest.fixture(scope="module")
def disc():
    spec = importlib.util.spec_from_file_location("watcher_discover", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_focus_question_wins(disc, tmp_path):
    focus = tmp_path / "focus.md"
    focus.write_text("# comment\nbuild a coding agent\n", encoding="utf-8")
    assert disc.read_focus(focus, "owner question") == ["owner question"]


def test_read_focus_skips_comments_and_blanks(disc, tmp_path):
    focus = tmp_path / "focus.md"
    focus.write_text("# hdr\n\nshell safety\n# note\nskills\n", encoding="utf-8")
    assert disc.read_focus(focus, "") == ["shell safety", "skills"]


def test_watched_urls_reads_queue_and_sources(disc, tmp_path, monkeypatch):
    queue = tmp_path / "queue.txt"
    queue.write_text("# c\nhttps://queued\n", encoding="utf-8")
    video = tmp_path / "video"
    video.mkdir()
    (video / "x.md").write_text("# t\n- **Source:** https://watched\n", encoding="utf-8")
    monkeypatch.setattr(disc, "QUEUE", queue)
    monkeypatch.setattr(disc, "VIDEO_DIR", video)
    got = disc.watched_urls()
    assert got == {"https://queued", "https://watched"}


def test_discover_dedups_and_respects_limit(disc, monkeypatch):
    monkeypatch.setattr(disc, "watched_urls", lambda: {"https://seen"})
    monkeypatch.setattr(disc, "search", lambda q, k: ["https://seen", "https://new1", "https://new2"])
    picked = disc.discover(["t1", "t2"], limit=1, per_query=3)
    assert picked == ["https://new1"]


def test_append_to_queue_preserves_header(disc, tmp_path):
    queue = tmp_path / "queue.txt"
    queue.write_text("# header\nhttps://old", encoding="utf-8")
    disc.append_to_queue(["https://a", "https://b"], queue)
    text = queue.read_text(encoding="utf-8")
    assert text.startswith("# header\nhttps://old\n")
    assert text.endswith("https://a\nhttps://b\n")
