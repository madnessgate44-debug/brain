"""Tests for scripts/daily_report.py — the daily report composer and rotation.

No network: the fan-out is monkeypatched. The point is the report shape the issue
requires (self-audit, per-repo plan progress, cursor, one question) and the honest
handling of missing inputs (a repo without a plan is reported blocked, never faked).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "daily_report.py"


def load_module():
    spec = importlib.util.spec_from_file_location("daily_report", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["daily_report"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return load_module()


PLAN = """# Production plan — demo

Goal: make the demo sellable.

| id | item | status | evidence |
|---|---|---|---|
| D1 | ship it | done | `src/app.py` |
| D2 | add auth | in-progress | issue #1 |
| D3 | add payment | todo | issue #2 |
"""


def _tree(tmp_path: Path, plan_text: str | None = PLAN) -> Path:
    audits = tmp_path / "docs" / "audits"
    (audits / "plans").mkdir(parents=True)
    if plan_text is not None:
        (audits / "plans" / "demo.md").write_text(plan_text, encoding="utf-8")
    (audits / "repo-queue.json").write_text(
        json.dumps(
            {
                "repos": [
                    {"rank": 1, "name": "demo", "repo": "o/demo"},
                    {"rank": 2, "name": "second", "repo": "o/second"},
                    {"rank": 3, "name": "third", "repo": "o/third"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (audits / "cursor.json").write_text(
        json.dumps({"last_repo": None, "history": []}), encoding="utf-8"
    )
    return tmp_path


def test_parse_plan_reads_goal_and_items(mod):
    plan = mod.parse_plan(PLAN)
    assert plan["goal"] == "make the demo sellable."
    assert [i["id"] for i in plan["items"]] == ["D1", "D2", "D3"]
    assert [i["status"] for i in plan["items"]] == ["done", "in-progress", "todo"]


def test_parse_plan_skips_rows_with_unknown_status(mod):
    text = "Goal: x\n\n| id | item | status | evidence |\n|---|---|---|---|\n| Z | nope | whatever | - |\n"
    assert mod.parse_plan(text)["items"] == []


def test_plan_progress_picks_first_unfinished(mod):
    prog = mod.plan_progress(mod.parse_plan(PLAN)["items"])
    assert prog == {
        "done": 1,
        "total": 3,
        "pct": 33,
        "next": {"id": "D2", "item": "add auth", "status": "in-progress", "evidence": "issue #1"},
    }


def test_select_repos_starts_at_top_when_cursor_empty(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": None}, 2)
    assert [r["name"] for r in selected] == ["demo", "second"]


def test_select_repos_resumes_after_cursor(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": "demo"}, 1)
    assert [r["name"] for r in selected] == ["second"]


def test_select_repos_wraps_around(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": "third"}, 1)
    assert [r["name"] for r in selected] == ["demo"]


def test_next_after_reports_following_repo(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    assert mod.next_after(queue, queue[:2]) == "third"


def test_write_cursor_advances_and_records_history(mod, tmp_path):
    root = _tree(tmp_path)
    mod.write_cursor(root, [{"name": "demo"}, {"name": "second"}], "2026-11-08T00:00:00Z")
    cur = mod.load_cursor(root)
    assert cur["last_repo"] == "second"
    assert cur["history"][-1] == {"utc": "2026-11-08T00:00:00Z", "repos": ["demo", "second"]}


def test_compose_has_all_four_required_sections(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": None}, 1)
    report = mod.compose(
        when_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
        audit={"purpose_checked": 3, "purpose_ok": 3, "depth_gaps": [], "report_only_pct": 0.0},
        queue=queue,
        cursor={"last_repo": None},
        selected=selected,
        nxt="second",
        root=root,
        question="Proceed?",
    )
    assert "## Daily report — 2026-11-08" in report
    assert "### 1. Brain self-audit" in report
    assert "### 2. Repos audited today" in report
    assert "### 3. Repo queue" in report
    assert "### 4. Question for the owner" in report
    assert "next in rotation: `second`" in report
    assert "- Proceed?" in report
    assert "AI agent (OpenHands) on behalf of the owner" in report


def test_compose_reports_repo_without_plan_as_blocked(mod, tmp_path):
    root = _tree(tmp_path, plan_text=None)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": None}, 1)
    report = mod.compose(
        when_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
        audit={},
        queue=queue,
        cursor={"last_repo": None},
        selected=selected,
        nxt="second",
        root=root,
        question="Proceed?",
    )
    assert "no production plan" in report
    assert "[B]" in report


def test_compose_reports_missing_queue_honestly(mod, tmp_path):
    (tmp_path / "docs" / "audits").mkdir(parents=True)
    report = mod.compose(
        when_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
        audit={},
        queue=[],
        cursor={"last_repo": None},
        selected=[],
        nxt=None,
        root=tmp_path,
        question="Proceed?",
    )
    assert "no repo queue found" in report
    assert "next in rotation: `none`" in report


def test_self_audit_surfaces_tool_failure_as_blocked(mod, monkeypatch, tmp_path):
    def boom(cmd, cwd):
        return None, "exit 1"

    monkeypatch.setattr(mod, "_run_json", boom)
    audit = mod.self_audit(tmp_path)
    assert audit["purpose_error"] == "exit 1"
    assert audit["status_error"] == "exit 1"


def test_main_dry_run_posts_nothing(mod, tmp_path, capsys):
    root = _tree(tmp_path)
    rc = mod.main(["--repo-dir", str(root), "--dry-run", "--repos", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "## Daily report" in out
    # the cursor must not advance on a dry run
    assert mod.load_cursor(root)["last_repo"] is None


def test_compose_embeds_cursor_marker(mod, tmp_path):
    root = _tree(tmp_path)
    queue = mod.load_queue(root)
    selected = mod.select_repos(queue, {"last_repo": None}, 2)
    report = mod.compose(
        when_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
        audit={},
        queue=queue,
        cursor={"last_repo": None},
        selected=selected,
        nxt="third",
        root=root,
        question="Proceed?",
    )
    assert f"{mod.CURSOR_MARKER}second -->" in report


def test_read_remote_cursor_reads_newest_marker(mod, monkeypatch):
    comments = [
        {"body": "old\n<!-- brain-daily-cursor: Amina -->"},
        {"body": "new\n<!-- brain-daily-cursor: Firstborn -->"},
        {"body": "no marker here"},
    ]
    monkeypatch.setattr(mod, "_github_comments", lambda: comments)
    assert mod.read_remote_cursor() == "Firstborn"


def test_read_remote_cursor_none_when_absent(mod, monkeypatch):
    monkeypatch.setattr(mod, "_github_comments", lambda: [{"body": "plain"}])
    assert mod.read_remote_cursor() is None


def test_effective_cursor_prefers_remote(mod, monkeypatch, tmp_path):
    root = _tree(tmp_path)
    mod.write_cursor(root, [{"name": "demo"}], "2026-11-08T00:00:00Z")
    monkeypatch.setattr(
        mod, "_github_comments", lambda: [{"body": "<!-- brain-daily-cursor: third -->"}]
    )
    assert mod.effective_cursor(root)["last_repo"] == "third"


def test_effective_cursor_falls_back_to_file(mod, monkeypatch, tmp_path):
    root = _tree(tmp_path)
    mod.write_cursor(root, [{"name": "demo"}], "2026-11-08T00:00:00Z")
    monkeypatch.setattr(mod, "_github_comments", lambda: [])
    assert mod.effective_cursor(root)["last_repo"] == "demo"
