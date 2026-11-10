"""Tests for scripts/report_to_channels.py — the multi-channel report fan-out.

No network: the transport is monkeypatched. The point is the honest result table —
an unconfigured channel is reported as skipped, never as posted.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "report_to_channels.py"


def load_module():
    spec = importlib.util.spec_from_file_location("report_to_channels", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["report_to_channels"] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return load_module()


def test_github_skipped_without_token(mod, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    r = mod.post_github("body")
    assert r.status == "skipped"


def test_swarmchat_skipped_without_config(mod, monkeypatch):
    monkeypatch.delenv("SWARMCHAT_SERVER", raising=False)
    monkeypatch.delenv("SWARMCHAT_TOKEN", raising=False)
    out = mod.post_swarmchat("body", ("#reports",))
    assert out and all(r.status == "skipped" for r in out)


def test_swarmchat_posts_to_each_channel(mod, monkeypatch):
    monkeypatch.setenv("SWARMCHAT_SERVER", "http://127.0.0.1:12000")
    monkeypatch.setenv("SWARMCHAT_TOKEN", "x")
    calls = []

    def fake(url, body, headers):
        calls.append((url, body))
        return 200, "{}"

    monkeypatch.setattr(mod, "_post_json", fake)
    out = mod.post_swarmchat("hello", ("#reports", "#audits"))
    assert [r.status for r in out] == ["posted", "posted"]
    assert all(url.endswith("/v1/send") for url, _ in calls)
    assert {body["chat"] for _, body in calls} == {"#reports", "#audits"}


def test_swarmchat_clips_long_report(mod, monkeypatch):
    monkeypatch.setenv("SWARMCHAT_SERVER", "http://127.0.0.1:12000")
    monkeypatch.setenv("SWARMCHAT_TOKEN", "x")
    sent = {}

    def fake(url, body, headers):
        sent["text"] = body["text"]
        return 200, "{}"

    monkeypatch.setattr(mod, "_post_json", fake)
    mod.post_swarmchat("A" * 50_000, ("#reports",))
    assert len(sent["text"]) <= mod.SWARM_MAX_TEXT


def test_render_reports_each_result(mod):
    rows = mod.render(
        [
            mod.Result("github", "posted", "HTTP 201"),
            mod.Result("swarmchat #reports", "skipped", "not set"),
        ]
    )
    assert "| github | posted | HTTP 201 |" in rows
    assert "| swarmchat #reports | skipped | not set |" in rows


def test_main_fails_when_nothing_posted(mod, monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("SWARMCHAT_SERVER", raising=False)
    monkeypatch.delenv("SWARMCHAT_TOKEN", raising=False)
    body = tmp_path / "r.md"
    body.write_text("report", encoding="utf-8")
    rc = mod.main(["--body", str(body)])
    assert rc == 1
    assert "skipped" in capsys.readouterr().out


def test_main_rejects_empty_report(mod, tmp_path):
    body = tmp_path / "empty.md"
    body.write_text("   \n", encoding="utf-8")
    assert mod.main(["--body", str(body)]) == 2
