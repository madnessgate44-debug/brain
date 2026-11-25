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


# --- gate: the fit-for-purpose floor (fix #1 of the 2026-11-07 audit) ----------------

def test_every_depth_finding_has_a_stable_id(pa, tmp_path):
    _company_tree(tmp_path)
    ids = [d.get("id") for d in pa.depth_findings(tmp_path / "brain")]
    assert all(ids), "every depth finding needs an id, or the gate cannot track it"
    assert len(ids) == len(set(ids)), "depth finding ids must be unique"


def test_gate_passes_when_nothing_regressed(pa, tmp_path):
    _company_tree(tmp_path)
    report = pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests")
    baseline = pa.baseline_from(report)
    assert pa.gate_findings(report, baseline) == []


def test_gate_fails_on_a_regression(pa, tmp_path):
    _company_tree(tmp_path)
    report = pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests")
    baseline = pa.baseline_from(report)
    baseline["depth"]["patch-contract"] = "OK"  # pretend it used to be OK
    failed = pa.gate_findings(report, baseline)
    assert [f["id"] for f in failed] == ["patch-contract"]
    assert "OK -> PARTIAL" in failed[0]["why"]


def test_gate_treats_new_findings_as_non_regressions(pa, tmp_path):
    _company_tree(tmp_path)
    report = pa.audit(tmp_path / "brain", _purpose(tmp_path), tmp_path / "tests")
    assert pa.gate_findings(report, {"depth": {}}) == []


def test_gate_reports_a_finding_with_no_id(pa):
    report = {"depth": [{"finding": "mystery", "status": "OK"}]}
    failed = pa.gate_findings(report, {"depth": {}})
    assert failed and failed[0]["why"] == "no stable id"


def test_render_gate_says_ok_when_clean(pa):
    assert pa.render_gate([], {"depth": {"a": "OK"}}).startswith("purpose gate: OK")


def test_render_gate_names_each_regression(pa):
    text = pa.render_gate([{"id": "x", "finding": "X broke", "why": "OK -> MISSING"}], {"depth": {}})
    assert "FAIL" in text and "x: X broke (OK -> MISSING)" in text

def _evidence(tmp_path: Path, name: str, body: str) -> None:
    d = tmp_path / "watcher" / "knowledge" / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_evidence_trace_reads_a_real_conversation_link(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\nStatus: LIVE — conversation started\n\n"
        "- app_conversation_id: abc\n- link: https://app.all-hands.dev/canvas/conversations/abc\n",
        encoding="utf-8",
    )
    assert pa.evidence_trace(p)["link"] == "https://app.all-hands.dev/canvas/conversations/abc"


def test_evidence_trace_is_empty_for_a_dry_run(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\nStatus: DRY RUN — no conversation started\n\n"
        "- app_conversation_id: (none)\n- link: (none)\n",
        encoding="utf-8",
    )
    assert not any(pa.evidence_trace(p).values())


def test_evidence_trace_reads_an_issue_and_the_pull_request_that_closes_it(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\nStatus: LIVE — issue carried to a pull request\n\n"
        "- issue: https://github.com/o/r/issues/7\n"
        "- pull_request: https://github.com/o/r/pull/8\n",
        encoding="utf-8",
    )
    trace = pa.evidence_trace(p)
    assert trace["issue"] == "https://github.com/o/r/issues/7"
    assert trace["pull_request"] == "https://github.com/o/r/pull/8"


def test_evidence_trace_rejects_an_issue_and_pr_on_different_repositories(pa, tmp_path):
    """A PR on another repo does not close this repo's issue."""
    p = tmp_path / "e.md"
    p.write_text(
        "- issue: https://github.com/o/r/issues/7\n"
        "- pull_request: https://github.com/other/repo/pull/8\n",
        encoding="utf-8",
    )
    trace = pa.evidence_trace(p)
    assert trace["issue"] == "" and trace["pull_request"] == ""


def test_depth_rejects_a_dry_run_as_live_evidence(pa, tmp_path):
    """W3: a dry run in the evidence dir is a presence, not a proof."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-1.md",
              "# Session agent loop\n\nStatus: DRY RUN — no conversation started\n\n"
              "- app_conversation_id: (none)\n- link: (none)\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "MISSING"


def test_depth_refuses_a_started_conversation_as_proof_of_an_issue_to_pr_run(pa, tmp_path):
    """W3: the old check passed on a conversation link. A started conversation is presence."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-2.md",
              "# Session agent loop\n\nStatus: LIVE — conversation started\n\n"
              "- app_conversation_id: conv-9\n"
              "- link: https://app.all-hands.dev/canvas/conversations/conv-9\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("conv-9" in e and "conversation only" in e for e in f["evidence"])


def test_depth_passes_with_a_real_issue_to_pr_trace(pa, tmp_path):
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-3.md",
              "# Session agent loop\n\nStatus: LIVE — issue carried to a pull request\n\n"
              "- app_conversation_id: conv-9\n"
              "- link: https://app.all-hands.dev/canvas/conversations/conv-9\n"
              "- issue: https://github.com/o/r/issues/7\n"
              "- pull_request: https://github.com/o/r/pull/8\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("issues/7" in e and "pull/8" in e for e in f["evidence"])


# --- the trace is checked against GitHub, not only matched as text (W3) ---------------

TRACE = {"issue": "https://github.com/o/r/issues/7",
         "pull_request": "https://github.com/o/r/pull/8"}


def _gh(issue=None, pull=None):
    """A fake GitHub: `None` for a path means HTTP 404."""
    def fetch(path: str):
        if "/issues/" in path:
            return issue if issue is not None else {"__http__": 404}
        return pull if pull is not None else {"__http__": 404}
    return fetch


def test_verify_trace_accepts_an_issue_the_pull_request_references(pa):
    state, why = pa.verify_trace(
        TRACE, _gh({"number": 7, "title": "bug"}, {"number": 8, "body": "Closes #7"})
    )
    assert state == "verified"
    assert "#7" in why and "#8" in why


def test_verify_trace_rejects_a_missing_issue(pa):
    state, why = pa.verify_trace(TRACE, _gh(None, {"number": 8, "body": "Closes #7"}))
    assert state == "missing"
    assert "issue o/r#7 does not exist" in why


def test_verify_trace_rejects_a_missing_pull_request(pa):
    state, why = pa.verify_trace(TRACE, _gh({"number": 7}, None))
    assert state == "missing"
    assert "pull request o/r#8 does not exist" in why


def test_verify_trace_rejects_a_pull_request_that_never_names_the_issue(pa):
    state, why = pa.verify_trace(TRACE, _gh({"number": 7}, {"number": 8, "body": "unrelated"}))
    assert state == "missing"
    assert "does not reference issue #7" in why


def test_verify_trace_rejects_a_pull_request_used_as_the_issue(pa):
    state, why = pa.verify_trace(
        TRACE, _gh({"number": 7, "pull_request": {"url": "u"}}, {"number": 8, "body": "Closes #7"})
    )
    assert state == "missing"
    assert "is a pull request, not an issue" in why


def test_verify_trace_is_unverified_when_github_is_not_read(pa):
    """No token is not a refutation: it stays unverified rather than passing or failing."""
    state, _ = pa.verify_trace(TRACE, lambda path: None)
    assert state == "unverified"


def test_depth_does_not_count_a_fabricated_trace(pa, tmp_path):
    """W3: a well-formed pair of URLs is text. If GitHub has no such issue, it is not proof."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-4.md",
              "# Session agent loop\n\nStatus: LIVE — issue carried to a pull request\n\n"
              "- issue: https://github.com/o/r/issues/7\n"
              "- pull_request: https://github.com/o/r/pull/8\n")
    found = pa.depth_findings(tmp_path / "brain", _gh())
    f = next(d for d in found if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("does not exist" in e for e in f["evidence"])


def test_depth_counts_a_trace_github_confirms(pa, tmp_path):
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-5.md",
              "# Session agent loop\n\nStatus: LIVE — issue carried to a pull request\n\n"
              "- issue: https://github.com/o/r/issues/7\n"
              "- pull_request: https://github.com/o/r/pull/8\n")
    fetch = _gh({"number": 7, "title": "bug"}, {"number": 8, "body": "Closes #7"})
    found = pa.depth_findings(tmp_path / "brain", fetch)
    f = next(d for d in found if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("references it" in e for e in f["evidence"])


def test_depth_says_so_when_the_trace_is_not_checked(pa, tmp_path):
    """Offline (no fetcher) the finding still passes, but the evidence line admits it."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-6.md",
              "# Session agent loop\n\n- issue: https://github.com/o/r/issues/7\n"
              "- pull_request: https://github.com/o/r/pull/8\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("not checked" in e for e in f["evidence"])
