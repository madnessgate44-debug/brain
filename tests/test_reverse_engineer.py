"""Offline tests for the Watcher reverse-engineering tool (watcher/knowledge/tools/reverse.py).

Covers the pure logic — repo parsing, file selection, and the honest no-key scaffold —
with the network stubbed. No clone, no execution, no model.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "reverse.py"


@pytest.fixture(scope="module")
def rev():
    spec = importlib.util.spec_from_file_location("watcher_reverse", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_repo_accepts_owner_repo_and_urls(rev):
    assert rev.parse_repo("madnessgate44-debug/brain") == "madnessgate44-debug/brain"
    assert rev.parse_repo("https://github.com/aider-ai/aider") == "aider-ai/aider"
    assert rev.parse_repo("https://github.com/aider-ai/aider.git") == "aider-ai/aider"


def test_pick_files_prefers_notable_shallow(rev):
    paths = ["deep/nested/thing.py", "README.md", "src/agent/loop.ts", "assets/logo.png"]
    picked = rev.pick_files(paths, 3)
    assert "README.md" in picked
    assert "src/agent/loop.ts" in picked
    assert "assets/logo.png" not in picked  # not source or docs


def test_pick_files_respects_limit(rev):
    assert len(rev.pick_files([f"src/f{i}.py" for i in range(50)], 5)) == 5


def test_scaffold_without_key_invents_nothing(rev):
    meta = {"html_url": "https://github.com/x/y", "language": "Python", "stargazers_count": 1, "license": None}
    md = rev.build_dissection("x/y", meta, {"README.md": "# hi"}, None)
    for s in rev.SECTIONS:
        assert f"## {s}" in md
    assert "TODO" in md and "no model route" in md
    assert "## Files read" in md and "`README.md`" in md


def test_scaffold_records_repo_metadata(rev):
    meta = {"html_url": "https://github.com/x/y", "language": "Go", "stargazers_count": 9,
            "license": {"spdx_id": "MIT"}}
    md = rev.build_dissection("x/y", meta, {}, None)
    assert "**Language:** Go" in md
    assert "**Stars:** 9" in md
    assert "**License:** MIT" in md
