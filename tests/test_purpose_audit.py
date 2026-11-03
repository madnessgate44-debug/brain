"""Offline tests for the purpose audit (watcher/knowledge/tools/purpose_audit.py).

The audit compares code to the app's purpose and separates production code from test-only
matches. These tests use a tiny fake tree so nothing here depends on brain's real layout.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "purpose_audit.py"


@pytest.fixture(scope="module")
def pa():
    spec = importlib.util.spec_from_file_location("watcher_purpose_audit", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path: Path):
    (tmp_path / "brain").mkdir()
    (tmp_path / "brain" / "real.py").write_text("WORKFLOW_ORDER = ()\n", encoding="utf-8")
    (tmp_path / "brain" / "tests").mkdir()
    (tmp_path / "brain" / "tests" / "test_x.py").write_text("TerminalTool()\n", encoding="utf-8")


def _purpose(tmp_path: Path) -> Path:
    p = tmp_path / "purpose.md"
    p.write_text(
        "# purpose\n\n"
        "Implemented claim\tWORKFLOW_ORDER\tbrain/\n"
        "Test-only claim\tTerminalTool\tbrain/\n"
        "Missing claim\tNoSuchThingAnywhere\tbrain/\n",
        encoding="utf-8",
    )
    return p


def test_parse_claims_reads_tab_separated(pa, tmp_path):
    claims = pa.parse_claims(_purpose(tmp_path))
    assert claims[0] == ("Implemented claim", "WORKFLOW_ORDER", "brain/")
    assert len(claims) == 3


def test_audit_classifies_ok_untested_missing(pa, tmp_path):
    _tree(tmp_path)
    report = pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests")
    by = {r["claim"]: r["status"] for r in report["results"]}
    assert by["Implemented claim"] == "OK"
    assert by["Test-only claim"] == "UNTESTED"
    assert by["Missing claim"] == "MISSING"
    assert report["ok"] == 1


def test_ok_evidence_points_at_production_code(pa, tmp_path):
    _tree(tmp_path)
    report = pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests")
    ok = next(r for r in report["results"] if r["status"] == "OK")
    assert ok["evidence"] and ok["evidence"][0].startswith("brain/real.py:")


def test_render_marks_each_status(pa, tmp_path):
    _tree(tmp_path)
    text = pa.render(pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests"))
    assert "[x] **Implemented claim**" in text
    assert "[~] **Test-only claim**" in text
    assert "[ ] **Missing claim**" in text
