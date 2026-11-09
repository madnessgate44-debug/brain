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


def _company_tree(tmp_path: Path, *, loop_roles: int = 1, total: int = 3, deletions: bool = True,
                  general_loop: bool = False, unplanned: bool = False):
    company = tmp_path / "brain" / "company"
    company.mkdir(parents=True)
    roles = "".join(
        f'    SpecialistRole(\n        key="role{n}",\n    ),\n'
        for n in "abcdefghij"[:total]
    )
    (company / "roles.py").write_text(roles, encoding="utf-8")
    branches = "".join(
        f'    if role_key == "role{n}":\n        run_openhands_developer()\n'
        for n in "abcdefghij"[:loop_roles]
    )
    if general_loop:
        branches += '    if role_key != "developer":\n        run_openhands_role()\n'
    (company / "agent_runner.py").write_text(branches + "    await self.provider.complete(s, u)\n", encoding="utf-8")
    dev = "TemporaryDirectory()\n_MAX_FILES = 30\n_MAX_FILE_BYTES = 200000\n"
    if deletions:
        dev += 'raise AgentOutputError("does not support deletions")\n'
    else:
        dev += 'changed.append({"path": relative, "deleted": True})\n'
    if unplanned:
        dev += 'raise AgentOutputError(f"OpenHands created an unplanned file: {relative!r}")\n'
    (company / "openhands_developer.py").write_text(dev, encoding="utf-8")


def test_depth_flags_partial_loop_coverage(pa, tmp_path):
    _company_tree(tmp_path, loop_roles=1, total=9)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "loop covers" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert "1 of 9" in f["finding"]


def test_depth_flags_patch_contract(pa, tmp_path):
    _company_tree(tmp_path, unplanned=True)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "Patch contract" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("deletions forbidden" in e for e in f["evidence"])
    assert any("unplanned new files rejected" in e for e in f["evidence"])


def test_depth_passes_when_contract_allows_deletions_and_new_files(pa, tmp_path):
    _company_tree(tmp_path, deletions=False, unplanned=False)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "Patch contract" in d["finding"])
    assert f["status"] == "OK"
    assert any("deletions allowed" in e for e in f["evidence"])
    assert any("unplanned new files allowed" in e for e in f["evidence"])


def test_depth_flags_missing_live_evidence(pa, tmp_path):
    _company_tree(tmp_path)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "MISSING"


def test_depth_passes_when_every_role_loops(pa, tmp_path):
    _company_tree(tmp_path, loop_roles=3, total=3)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "loop covers" in d["finding"])
    assert f["status"] == "OK"


def test_depth_counts_all_roles_when_general_loop_is_wired(pa, tmp_path):
    # Only the developer has an explicit branch, but the general loop covers the rest.
    _company_tree(tmp_path, loop_roles=1, total=9, general_loop=True)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "loop covers" in d["finding"])
    assert f["status"] == "OK"
    assert "9 of 9" in f["finding"]
    assert "0 run single-shot" in f["finding"]


def test_depth_stays_partial_without_the_general_loop(pa, tmp_path):
    _company_tree(tmp_path, loop_roles=1, total=9, general_loop=False)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "loop covers" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert "1 of 9" in f["finding"]


def test_depth_flags_a_role_with_no_skill(pa, tmp_path):
    """Finding a missing skill is the Watcher's job (W7)."""
    _company_tree(tmp_path, total=3)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "skill file" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert "0 of 3" in f["finding"]
    assert any("rolea" in e for e in f["evidence"])


def test_depth_passes_when_every_role_has_a_skill(pa, tmp_path):
    _company_tree(tmp_path, total=3)
    skills = tmp_path / "brain" / "company" / "skills"
    skills.mkdir()
    for n in "abc":
        (skills / f"role{n}.md").write_text("# skill", encoding="utf-8")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "skill file" in d["finding"])
    assert f["status"] == "OK"
    assert "3 of 3" in f["finding"]


def test_depth_flags_missing_skill_router(pa, tmp_path):
    _company_tree(tmp_path)
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "skill router" in d["finding"])
    assert f["status"] == "MISSING"
