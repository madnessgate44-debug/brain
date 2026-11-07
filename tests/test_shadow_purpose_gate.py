"""The daily fit-for-purpose gate Shadow runs (fix #1 of the 2026-11-07 audit).

Shadow owns this gate, so these tests exercise Shadow's wrapper (shadow/report.py) and the
workflow that schedules it, not the audit tool itself (tests/test_purpose_audit.py covers that).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = _ROOT / "shadow" / "report.py"


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("shadow_report_under_test", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_purpose_gate_passes_on_the_real_repo(report):
    passed, line = report.purpose_gate()
    assert passed, f"the repo regressed against its own locked baseline: {line}"
    assert line.startswith("purpose gate: OK")


def test_agent_status_gate_passes_on_the_real_repo(report):
    passed, line = report.agent_status_gate()
    assert passed, f"the W1 ratchet is red: {line}"
    assert "Report-only commits:" in line


def test_daily_gate_runs_both_halves(report):
    passed, lines = report.daily_gate()
    assert passed
    assert any(line.startswith("fit-for-purpose:") for line in lines)
    assert any(line.startswith("W1 report-only:") for line in lines)


def test_purpose_gate_fails_honestly_when_the_tool_is_absent(report, monkeypatch, tmp_path):
    monkeypatch.setattr(report, "ROOT", str(tmp_path))
    passed, line = report.purpose_gate()
    assert passed is False
    assert "absent" in line


def test_report_surfaces_the_gate_verdict(report, monkeypatch):
    monkeypatch.setenv("SHADOW_DRY_RUN", "1")
    monkeypatch.setattr(report, "_open_prs", lambda: [])
    monkeypatch.setattr(report, "_registry_summary", lambda: "0 rows")
    body = report.report()
    assert "Fit-for-purpose gate: PASS" in body


def test_workflow_runs_the_gate_daily(report):
    wf = (_ROOT / ".github" / "workflows" / "shadow-report.yml").read_text(encoding="utf-8")
    assert "report.py --gate" in wf
    assert '"0 7 * * *"' in wf, "the gate must run on a daily cron"
    assert "gate:" in wf, "the gate must be its own job so a regression turns the run red"


def test_workflow_checks_out_full_history_for_the_ratio(report):
    """A shallow clone would make the W1 ratio read a 1-commit history and go falsely red."""
    wf = (_ROOT / ".github" / "workflows" / "shadow-report.yml").read_text(encoding="utf-8")
    assert wf.count("fetch-depth: 0") >= 2, "both the gate and report jobs read git history"
