"""R6: Shadow runs a real tool loop (gather evidence, then judge), offline-tested."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "shadow" / "shadow.py"


@pytest.fixture(scope="module")
def shadow():
    spec = importlib.util.spec_from_file_location("shadow_under_test", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_tool_call(shadow):
    assert shadow._parse_tool_call('TOOL: read_file {"path": "a.py", "ref": "HEAD"}') == (
        "read_file", {"path": "a.py", "ref": "HEAD"},
    )
    assert shadow._parse_tool_call('TOOL: read_log {"pr": 12}') == ("read_log", {"pr": 12})
    assert shadow._parse_tool_call("VERDICT: VERIFIED") is None
    assert shadow._parse_tool_call("just prose") is None


def test_is_verdict(shadow):
    assert shadow._is_verdict("VERDICT: VERIFIED\nFINDINGS:")
    assert not shadow._is_verdict("TOOL: search {}")


def test_run_tool_unknown(shadow):
    assert "unknown tool" in shadow._run_tool("nope", {})


def test_audit_runs_a_tool_then_returns_verdict(shadow, monkeypatch, tmp_path):
    """The loop must call the tool the model asked for, then return the final verdict."""
    calls = []

    def fake_generate(prompt, timeout=90):
        # First reply asks for a tool; the prompt on the second call must carry the tool result.
        if "TOOL RESULT" not in prompt:
            return "gemini-2.5-flash", 'TOOL: read_file {"path": "shadow/report.py", "ref": "HEAD"}'
        calls.append(prompt)
        return "gemini-2.5-flash", "VERDICT: VERIFIED\nFINDINGS:\n- x — CONFIRMED — y\nWEAKEST POINT: z\nFIX: none"

    monkeypatch.setattr(shadow, "generate", fake_generate)
    monkeypatch.setattr(shadow, "live_evidence", lambda pr=None, issue=None: "EVIDENCE")
    monkeypatch.setattr(shadow, "_run_tool", lambda name, args: f"CONTENT OF {args.get('path')}")

    log = tmp_path / "audit-log.md"
    monkeypatch.setattr(shadow, "LOG", str(log))

    verdict = shadow.audit("PR #1: something", pr=1)

    assert verdict.startswith("VERDICT: VERIFIED")
    assert calls, "the tool result was not fed back to the model"
    assert "CONTENT OF shadow/report.py" in calls[0]
    assert "tools:" in log.read_text(encoding="utf-8")


def test_audit_stops_at_max_steps(shadow, monkeypatch, tmp_path):
    """A model that only ever asks for tools must not loop forever."""
    monkeypatch.setattr(shadow, "generate", lambda prompt, timeout=90: ("m", 'TOOL: search {"pattern": "x"}'))
    monkeypatch.setattr(shadow, "live_evidence", lambda pr=None, issue=None: "E")
    monkeypatch.setattr(shadow, "_run_tool", lambda name, args: "r")
    monkeypatch.setattr(shadow, "LOG", str(tmp_path / "log.md"))

    shadow.audit("subject")

    assert shadow._MAX_STEPS == 4
