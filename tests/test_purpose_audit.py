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


@pytest.fixture(autouse=True)
def _no_owner_scope(monkeypatch):
    """Run the audit with no owner scope and no token unless a test sets one.

    Under Actions the audit sees `GITHUB_REPOSITORY` and `GITHUB_TOKEN`; these tests are about
    reading the evidence files, so they pin the local (no-scope, no-verification) behaviour and
    the owner-scope and verification tests opt in by setting the variables themselves.
    """
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("BRAIN_GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


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


def _runner_tree(pa, tmp_path: Path, runner_text: str, total: int = 9) -> dict:
    """A company tree whose agent_runner.py is exactly `runner_text`, then run the depth check."""
    company = tmp_path / "brain" / "company"
    company.mkdir(parents=True)
    keys = ["developer"] + [f"role_{c}" for c in "abcdefgh"[: total - 1]]
    (company / "roles.py").write_text(
        "".join(f'    SpecialistRole(\n        key="{k}",\n    ),\n' for k in keys),
        encoding="utf-8",
    )
    (company / "agent_runner.py").write_text(runner_text, encoding="utf-8")
    return next(d for d in pa.depth_findings(tmp_path / "brain") if "loop covers" in d["finding"])


def test_depth_ignores_a_comment_mention_of_the_general_loop(pa, tmp_path):
    """W3: the old check used `"run_openhands_role" in text`, so a *comment* about the loop
    reported 9 of 9 roles looping while no role reached it. The check must read code, not text.
    """
    f = _runner_tree(pa, tmp_path, "# run_openhands_role was deleted; roles now run single-shot\npass\n")
    assert f["status"] == "PARTIAL"
    assert "0 of 9" in f["finding"]


def test_depth_ignores_a_docstring_mention_of_the_general_loop(pa, tmp_path):
    """W3: a docstring naming the loop is a string, not a call — it must not count as coverage."""
    f = _runner_tree(pa, tmp_path, '"""Roles reach run_openhands_role in the wired branch."""\npass\n')
    assert f["status"] == "PARTIAL"
    assert "0 of 9" in f["finding"]


def test_depth_ignores_a_comment_mention_of_the_developer_loop(pa, tmp_path):
    """W3: the developer branch is credited only when `run_openhands_developer` is *called*."""
    f = _runner_tree(
        pa,
        tmp_path,
        'if role_key == "developer":\n'
        "    # run_openhands_developer was removed; this role is single-shot now\n"
        "    await self.provider.complete(s, u)\n",
    )
    assert f["status"] == "PARTIAL"
    assert "0 of 9" in f["finding"]


def test_depth_ignores_a_bare_import_of_the_general_loop(pa, tmp_path):
    """W3: an import names the symbol but never calls it — coverage requires the call."""
    f = _runner_tree(pa, tmp_path, "from brain.company.openhands_role import run_openhands_role\n")
    assert f["status"] == "PARTIAL"
    assert "0 of 9" in f["finding"]


def test_depth_general_loop_covers_every_role_except_the_developer(pa, tmp_path):
    """The general loop covers the eight non-developer roles; the developer needs its own call.

    Crediting the developer to the general loop would let deleting the developer branch still
    read as full coverage (W3).
    """
    f = _runner_tree(pa, tmp_path, 'if role_key != "developer":\n    await run_openhands_role(x)\n')
    assert f["status"] == "PARTIAL"
    assert "8 of 9" in f["finding"]
    assert "developer" not in f["evidence"][0]


def test_depth_counts_all_roles_when_both_loops_are_called(pa, tmp_path):
    f = _runner_tree(
        pa,
        tmp_path,
        'if role_key == "developer":\n    await run_openhands_developer(x)\n'
        'if role_key != "developer":\n    await run_openhands_role(x)\n',
    )
    assert f["status"] == "OK"
    assert "9 of 9" in f["finding"]


def test_call_offsets_reads_calls_not_mentions(pa):
    """The tokenizer is the fix's core: it sees `f(` and drops comments and strings."""
    text = (
        "# run_openhands_role() in a comment\n"
        'x = "run_openhands_role() in a string"\n'
        "from m import run_openhands_role\n"
        "run_openhands_role(1)\n"
    )
    offsets = pa._call_offsets(text)
    assert len(offsets["run_openhands_role"]) == 1
    assert pa._call_offsets("def broken(:\n") == {}


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


def test_evidence_link_reads_a_real_conversation_link(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\nStatus: LIVE — conversation started\n\n"
        "- app_conversation_id: abc\n- link: https://app.all-hands.dev/canvas/conversations/abc\n",
        encoding="utf-8",
    )
    assert pa.evidence_link(p) == "https://app.all-hands.dev/canvas/conversations/abc"


def test_evidence_link_is_empty_for_a_dry_run(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\nStatus: DRY RUN — no conversation started\n\n"
        "- app_conversation_id: (none)\n- link: (none)\n",
        encoding="utf-8",
    )
    assert pa.evidence_link(p) == ""


def test_pull_request_link_reads_a_github_pr(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Company workflow loop\n\n- pr: https://github.com/owner/repo/pull/218\n",
        encoding="utf-8",
    )
    assert pa.pull_request_link(p) == "https://github.com/owner/repo/pull/218"


def test_pull_request_link_rejects_a_conversation_link(pa, tmp_path):
    """A conversation link proves the loop started, not that it produced a PR."""
    p = tmp_path / "e.md"
    p.write_text(
        "# Session agent loop\n\n"
        "- link: https://app.all-hands.dev/canvas/conversations/abc\n",
        encoding="utf-8",
    )
    assert pa.pull_request_link(p) == ""


def test_pull_request_link_rejects_a_non_pull_github_url(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# x\n\n- pr: https://github.com/owner/repo/actions/runs/1\n",
        encoding="utf-8",
    )
    assert pa.pull_request_link(p) == ""


def test_issue_link_reads_a_github_issue(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Company workflow loop\n\n- issue: https://github.com/owner/repo/issues/208\n",
        encoding="utf-8",
    )
    assert pa.issue_link(p) == "https://github.com/owner/repo/issues/208"


def test_issue_link_rejects_a_pull_request_url(pa, tmp_path):
    """The issue field must name an issue, not the pull request it produced."""
    p = tmp_path / "e.md"
    p.write_text("- issue: https://github.com/owner/repo/pull/218\n", encoding="utf-8")
    assert pa.issue_link(p) == ""


def test_run_link_reads_a_workflow_run(pa, tmp_path):
    p = tmp_path / "e.md"
    p.write_text(
        "# Company workflow loop\n\n"
        "- workflow run: https://github.com/owner/repo/actions/runs/38148411690\n",
        encoding="utf-8",
    )
    assert pa.run_link(p) == "https://github.com/owner/repo/actions/runs/38148411690"


def test_run_link_rejects_an_issue_or_pull_request_url(pa, tmp_path):
    """The run field must name the run, not the issue or the pull request it connects."""
    p = tmp_path / "e.md"
    p.write_text("- workflow run: https://github.com/owner/repo/issues/208\n", encoding="utf-8")
    assert pa.run_link(p) == ""
    p.write_text("- workflow run: https://github.com/owner/repo/pull/218\n", encoding="utf-8")
    assert pa.run_link(p) == ""


def test_depth_rejects_a_dry_run_as_live_evidence(pa, tmp_path):
    """W3: a dry run in the evidence dir is a presence, not a proof."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-1.md",
              "# Session agent loop\n\nStatus: DRY RUN — no conversation started\n\n"
              "- app_conversation_id: (none)\n- link: (none)\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "MISSING"


def test_depth_is_partial_when_only_a_conversation_link_is_committed(pa, tmp_path):
    """W3: the finding names an issue -> PR run; a conversation link alone is not that."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "session-loop-2.md",
              "# Session agent loop\n\nStatus: LIVE — conversation started\n\n"
              "- app_conversation_id: conv-9\n"
              "- link: https://app.all-hands.dev/canvas/conversations/conv-9\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("conversation only" in e for e in f["evidence"])
    # the evidence must name the conversation URL, not a blank link
    assert any("conversations/conv-9" in e for e in f["evidence"])


def test_depth_is_partial_when_only_a_pull_request_link_is_committed(pa, tmp_path):
    """W3: the finding names an *issue* -> PR run, so a bare PR link is only one step."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "pr-only.md", "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("pull request only" in e for e in f["evidence"])


def test_depth_is_partial_when_issue_and_pr_have_no_run_between_them(pa, tmp_path):
    """W3: the finding names an issue -> PR *run*; issue+PR with no run is not that path.

    A file holding only an issue and a pull request proves two URLs, not a run that took one
    to the other. This is the false pass the earlier `issue + pr -> OK` rule left open.
    """
    _company_tree(tmp_path)
    _evidence(tmp_path, "no-run.md",
              "- issue: https://github.com/owner/repo/issues/208\n"
              "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("incomplete issue -> run -> pull request path" in e for e in f["evidence"])


def test_depth_passes_with_an_issue_a_run_and_a_pull_request(pa, tmp_path):
    _company_tree(tmp_path)
    _evidence(tmp_path, "company-loop.md",
              "# Company workflow loop\n\n"
              "- issue: https://github.com/owner/repo/issues/208\n"
              "- workflow run: https://github.com/owner/repo/actions/runs/38148411690\n"
              "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("issues/208" in e for e in f["evidence"])
    assert any("actions/runs/38148411690" in e for e in f["evidence"])
    assert any("pull/218" in e for e in f["evidence"])


def test_depth_does_not_pass_on_an_issue_and_a_pr_in_separate_files(pa, tmp_path):
    """W3: the finding names *a* run; a proof split across two files is not one run's path.

    An issue named by one evidence file and a pull request named by an unrelated file must
    not add up to OK — that would pass while no single run is proven to have gone issue -> PR.
    """
    _company_tree(tmp_path)
    _evidence(tmp_path, "a-issue.md", "- issue: https://github.com/owner/repo/issues/1\n")
    _evidence(tmp_path, "b-pr.md", "- pr: https://github.com/owner/repo/pull/9\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("issue only" in e for e in f["evidence"])
    assert any("pull request only" in e for e in f["evidence"])


def test_depth_is_partial_when_only_an_issue_link_is_committed(pa, tmp_path):
    _company_tree(tmp_path)
    _evidence(tmp_path, "issue-only.md", "- issue: https://github.com/owner/repo/issues/1\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("issue only" in e for e in f["evidence"])


def test_depth_still_ok_when_a_complete_file_coexists_with_partial_ones(pa, tmp_path):
    """A complete run's file passes even if other evidence files hold only one step."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "conversation-only.md", "- link: https://app.all-hands.dev/canvas/conversations/x\n")
    _evidence(tmp_path, "company-loop.md",
              "- issue: https://github.com/owner/repo/issues/208\n"
              "- workflow run: https://github.com/owner/repo/actions/runs/38148411690\n"
              "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("issues/208" in e and "pull/218" in e for e in f["evidence"])


def test_repo_of_reads_the_slug_of_a_github_issue_run_or_pr(pa):
    assert pa._repo_of("https://github.com/owner/repo/issues/208") == "owner/repo"
    assert pa._repo_of("https://github.com/owner/repo/pull/218") == "owner/repo"
    assert pa._repo_of("https://github.com/owner/repo/actions/runs/1") == "owner/repo"
    assert pa._repo_of("https://app.all-hands.dev/canvas/conversations/x") == ""
    assert pa._repo_of("") == ""


def test_depth_does_not_pass_on_an_issue_and_a_pr_in_different_repositories(pa, tmp_path):
    """W3: one run is one repository. An issue in repo A and a PR in repo B is not a path.

    The gateway allowlists a single owner and the run reports one target repository, so an
    issue, the run, and the pull request it produced always share an `owner/repo`. Links from
    different repositories are unrelated items and must not report OK.
    """
    _company_tree(tmp_path)
    _evidence(tmp_path, "mixed.md",
              "- issue: https://github.com/owner/repo/issues/1\n"
              "- workflow run: https://github.com/owner/repo/actions/runs/5\n"
              "- pr: https://github.com/other/repo/pull/2\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("different repositories" in e for e in f["evidence"])


def test_depth_passes_on_an_issue_a_run_and_a_pr_in_one_repository(pa, tmp_path):
    """The same three links in one repository is the proof the finding names."""
    _company_tree(tmp_path)
    _evidence(tmp_path, "company-loop.md",
              "- issue: https://github.com/owner/repo/issues/208\n"
              "- workflow run: https://github.com/owner/repo/actions/runs/38148411690\n"
              "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"


# --- owner scope: the proof must be a run THIS repository performed (W3) -------------
#
# A file whose issue, run, and pull request all name one repository passes `_same_repository`,
# but nothing required that repository to be the one Brain writes to. Brain writes to a single
# owner (`github_gateway.py:47`; `brain-task-runner.yml:50`), so a well-formed proof naming a
# foreign owner is a run this app did not perform — the same W3 shape one level deeper.

def _company_proof(tmp_path: Path, repo: str) -> None:
    _evidence(tmp_path, "company-loop.md",
              f"- issue: https://github.com/{repo}/issues/208\n"
              f"- workflow run: https://github.com/{repo}/actions/runs/38148411690\n"
              f"- pr: https://github.com/{repo}/pull/218\n")


def test_owner_scope_is_read_from_github_repository(pa, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    assert pa._owner_scope() == "owner"
    monkeypatch.delenv("GITHUB_REPOSITORY")
    monkeypatch.setenv("BRAIN_GITHUB_OWNER", "brain-owner")
    assert pa._owner_scope() == "brain-owner"
    monkeypatch.delenv("BRAIN_GITHUB_OWNER")
    assert pa._owner_scope() == ""


def test_depth_passes_when_the_proof_is_this_repository(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    _company_tree(tmp_path)
    _company_proof(tmp_path, "owner/repo")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"


def test_depth_rejects_a_well_formed_proof_from_a_foreign_repository(pa, tmp_path, monkeypatch):
    """W3: the residual false pass — three links that agree, but name someone else's repo."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    _company_tree(tmp_path)
    _company_proof(tmp_path, "someone-else/other")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("not this repository's owner" in e for e in f["evidence"])
    assert any("someone-else/other" in e for e in f["evidence"])


def test_depth_stays_lenient_without_an_owner_scope(pa, tmp_path):
    """A local run has no owner scope, so a self-consistent proof still passes."""
    _company_tree(tmp_path)
    _company_proof(tmp_path, "someone-else/other")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"


def test_depth_ignores_a_foreign_proof_when_a_real_one_exists(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    _company_tree(tmp_path)
    _company_proof(tmp_path, "someone-else/other")
    _evidence(tmp_path, "real-loop.md",
              "- issue: https://github.com/owner/repo/issues/208\n"
              "- workflow run: https://github.com/owner/repo/actions/runs/38148411690\n"
              "- pr: https://github.com/owner/repo/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert any("real-loop.md" in e for e in f["evidence"])


# --- the proof must be verified against GitHub, not merely well-formed (W3) -----------
#
# A fabricated `issues/1` + `runs/1` + `pull/1` triple is well-formed and in scope, so every
# earlier check passes it. These tests fake the API (`pa._gh_get`) so they are hermetic and
# never touch the network, and assert the finding rejects a proof the API does not confirm.

def _with_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")


def test_gh_get_returns_status_and_none_on_http_error(pa, monkeypatch):
    """A 404 is a definitive absence; a request that cannot be made is status 0."""
    def fake_urlopen(req, timeout=20):
        raise pa.urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(pa.urllib.request, "urlopen", fake_urlopen)
    body, status = pa._gh_get("/repos/o/r/issues/1")
    assert body is None and status == 404

    def boom(req, timeout=20):
        raise OSError("network down")
    monkeypatch.setattr(pa.urllib.request, "urlopen", boom)
    body, status = pa._gh_get("/repos/o/r/issues/1")
    assert body is None and status == 0


def test_verified_connection_accepts_the_run_whose_comment_names_the_pr(pa, monkeypatch):
    def fake(path):
        if "actions/runs" in path:
            return {"event": "issues", "status": "completed"}, 200
        return [{"body": "Pull request: https://github.com/o/r/pull/218"}], 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    assert pa._verified_connection(
        "https://github.com/o/r/issues/208",
        "https://github.com/o/r/actions/runs/38148411690",
        "https://github.com/o/r/pull/218",
    )


def test_verified_connection_rejects_a_run_that_did_not_execute_the_company_workflow(pa, monkeypatch):
    def fake(path):
        if "actions/runs" in path:
            return {"event": "push", "status": "completed"}, 200
        return [{"body": "Pull request: https://github.com/o/r/pull/218"}], 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    assert not pa._verified_connection(
        "https://github.com/o/r/issues/208",
        "https://github.com/o/r/actions/runs/1",
        "https://github.com/o/r/pull/218",
    )


def test_verified_connection_rejects_a_missing_run(pa, monkeypatch):
    monkeypatch.setattr(pa, "_gh_get", lambda path: (None, 404))
    assert not pa._verified_connection(
        "https://github.com/o/r/issues/208",
        "https://github.com/o/r/actions/runs/1",
        "https://github.com/o/r/pull/218",
    )


def test_verified_connection_rejects_a_comment_that_names_a_different_pr(pa, monkeypatch):
    def fake(path):
        if "actions/runs" in path:
            return {"event": "issues", "status": "completed"}, 200
        return [{"body": "Pull request: https://github.com/o/r/pull/999"}], 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    assert not pa._verified_connection(
        "https://github.com/o/r/issues/208",
        "https://github.com/o/r/actions/runs/38148411690",
        "https://github.com/o/r/pull/218",
    )


def test_verified_connection_is_lenient_when_the_comments_cannot_be_read(pa, monkeypatch):
    """An unreadable comment list is inconclusive, not a rejection (status 0)."""
    def fake(path):
        if "actions/runs" in path:
            return {"event": "issues", "status": "completed"}, 200
        return None, 0
    monkeypatch.setattr(pa, "_gh_get", fake)
    assert pa._verified_connection(
        "https://github.com/o/r/issues/208",
        "https://github.com/o/r/actions/runs/38148411690",
        "https://github.com/o/r/pull/218",
    )


def test_depth_rejects_a_fabricated_triple_when_verifying(pa, tmp_path, monkeypatch):
    """W3: the residual false pass — a well-formed, in-scope triple for a run that never ran."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    monkeypatch.setattr(pa, "_gh_get", lambda path: (None, 404))
    _company_tree(tmp_path)
    _evidence(tmp_path, "fake.md",
              "- issue: https://github.com/madnessgate44-debug/brain/issues/1\n"
              "- workflow run: https://github.com/madnessgate44-debug/brain/actions/runs/1\n"
              "- pr: https://github.com/madnessgate44-debug/brain/pull/1\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "PARTIAL"
    assert any("does not confirm the run connects" in e for e in f["evidence"])


def test_depth_passes_a_proof_the_api_confirms(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)

    def fake(path):
        if "actions/runs" in path:
            return {"event": "issues", "status": "completed"}, 200
        return [{"body": "Pull request: https://github.com/madnessgate44-debug/brain/pull/218"}], 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    _company_tree(tmp_path)
    _evidence(tmp_path, "real.md",
              "- issue: https://github.com/madnessgate44-debug/brain/issues/208\n"
              "- workflow run: https://github.com/madnessgate44-debug/brain/actions/runs/38148411690\n"
              "- pr: https://github.com/madnessgate44-debug/brain/pull/218\n")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"


def test_depth_skips_verification_without_a_token(pa, tmp_path, monkeypatch):
    """No token (a local run) must not fabricate a failure: the finding stays OK."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    calls = []
    monkeypatch.setattr(pa, "_gh_get", lambda path: calls.append(path) or (None, 404))
    _company_tree(tmp_path)
    _company_proof(tmp_path, "madnessgate44-debug/brain")
    f = next(d for d in pa.depth_findings(tmp_path / "brain") if "live issue" in d["finding"])
    assert f["status"] == "OK"
    assert calls == [], "without a token the check must not call the API"


# --- the scheduled session loop's proof (W3) -----------------------------------------
#
# `live-run-evidence` requires an issue, and the session loop is cron-triggered, so its own
# `- pr:` line was read by nothing. These tests pin the finding that reads it.

_CONV = "https://app.all-hands.dev/canvas/conversations/e166ab9ce3864fa89ded6f01dd480097"
_SESSION_RUN = "https://github.com/madnessgate44-debug/brain/actions/runs/42477372401"
_SESSION_PR = "https://github.com/madnessgate44-debug/brain/pull/307"


def _session_evidence(tmp_path, body: str) -> None:
    _evidence(tmp_path, "session-loop.md", body)


def _session_finding(pa, tmp_path):
    return next(d for d in pa.depth_findings(tmp_path / "brain") if "session loop" in d["finding"])


def _with_cloud(monkeypatch, pa, numbers=None, conclusive=False):
    monkeypatch.setattr(pa, "_cloud_pull_requests", lambda conv: (numbers, conclusive))


def test_conversation_id_reads_plain_and_dashed_ids(pa):
    assert pa._conversation_id(_CONV) == "e166ab9ce3864fa89ded6f01dd480097"
    dashed = "https://app.all-hands.dev/canvas/conversations/e166ab9c-e386-4fa8-9ded-6f01dd480097"
    assert pa._conversation_id(dashed) == "e166ab9ce3864fa89ded6f01dd480097"
    assert pa._conversation_id("https://example.com/x") == ""


def test_session_finding_is_missing_with_no_evidence(pa, tmp_path):
    _company_tree(tmp_path)
    f = _session_finding(pa, tmp_path)
    assert f["status"] == "MISSING"


def test_session_finding_rejects_a_conversation_only_file(pa, tmp_path, monkeypatch):
    """The false pass this finding exists to catch: a conversation link is not a pull request."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)
    _company_tree(tmp_path)
    _session_evidence(tmp_path, f"- link: {_CONV}\n")
    f = _session_finding(pa, tmp_path)
    assert f["status"] == "PARTIAL"
    assert any("conversation only" in e for e in f["evidence"])


def test_session_finding_passes_a_verified_run_and_pull_request(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)

    def fake(path):
        if path.endswith("/pulls/307"):
            return {"created_at": "2026-11-09T10:00:00Z"}, 200
        return {"name": "Session agent loop", "status": "completed",
                "run_started_at": "2026-11-08T11:48:44Z"}, 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n- pr: {_SESSION_PR}\n")
    f = _session_finding(pa, tmp_path)
    assert f["status"] == "OK"
    assert any("pull request" in e for e in f["evidence"])


def test_session_finding_rejects_a_pull_request_older_than_the_run(pa, tmp_path, monkeypatch):
    """A pull request that existed before the run cannot be that run's output."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)

    def fake(path):
        if path.endswith("/pulls/307"):
            return {"created_at": "2026-10-01T00:00:00Z"}, 200
        return {"name": "Session agent loop", "status": "completed",
                "run_started_at": "2026-11-08T11:48:44Z"}, 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n- pr: {_SESSION_PR}\n")
    assert _session_finding(pa, tmp_path)["status"] == "PARTIAL"


def test_session_finding_rejects_a_run_of_another_workflow(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)

    def fake(path):
        if path.endswith("/pulls/307"):
            return {"created_at": "2026-11-09T10:00:00Z"}, 200
        return {"name": "Brain CI", "status": "completed",
                "run_started_at": "2026-11-08T11:48:44Z"}, 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n- pr: {_SESSION_PR}\n")
    assert _session_finding(pa, tmp_path)["status"] == "PARTIAL"


def test_session_finding_rejects_a_pull_request_the_conversation_did_not_produce(
        pa, tmp_path, monkeypatch):
    """The Cloud API is the authority on which pull request a conversation produced."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa, numbers={999}, conclusive=True)

    def fake(path):
        if path.endswith("/pulls/307"):
            return {"created_at": "2026-11-09T10:00:00Z"}, 200
        return {"name": "Session agent loop", "status": "completed",
                "run_started_at": "2026-11-08T11:48:44Z"}, 200
    monkeypatch.setattr(pa, "_gh_get", fake)
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n- pr: {_SESSION_PR}\n")
    assert _session_finding(pa, tmp_path)["status"] == "PARTIAL"


def test_session_finding_rejects_links_from_different_repositories(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)
    monkeypatch.setattr(pa, "_gh_get", lambda path: (None, 404))
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n"
                      "- pr: https://github.com/other/repo/pull/1\n")
    assert _session_finding(pa, tmp_path)["status"] == "PARTIAL"


def test_session_finding_rejects_a_proof_from_a_foreign_owner(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    _with_token(monkeypatch)
    _with_cloud(monkeypatch, pa)
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n"
                      "- workflow run: https://github.com/other/repo/actions/runs/1\n"
                      "- pr: https://github.com/other/repo/pull/1\n")
    assert _session_finding(pa, tmp_path)["status"] == "PARTIAL"


def test_session_finding_does_not_call_the_api_without_a_token(pa, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "madnessgate44-debug/brain")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    _with_cloud(monkeypatch, pa)
    calls = []
    monkeypatch.setattr(pa, "_gh_get", lambda path: calls.append(path) or (None, 404))
    _company_tree(tmp_path)
    _session_evidence(tmp_path,
                      f"- link: {_CONV}\n- workflow run: {_SESSION_RUN}\n- pr: {_SESSION_PR}\n")
    assert _session_finding(pa, tmp_path)["status"] == "OK"
    assert calls == []
