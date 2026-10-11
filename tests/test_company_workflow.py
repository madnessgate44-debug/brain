"""Policy tests for the software-company workflow."""

import pytest

from brain.company.roles import ROLE_CATALOG, ROLE_BY_KEY, WORKFLOW_ORDER
from brain.company.run_issue_workflow import parse_issue_body
from brain.company.diagnostics import failure_report
from brain.company.engine import CompanyWorkflowBlocked, CompanyWorkflowEngine, validate_change_set_scope
from brain.company.workflow import (
    WorkflowPolicyError,
    evaluate_release_gate,
    missing_inputs,
    validate_stage_entry,
)


def test_company_workflow_has_independent_specialist_roles():
    keys = set(WORKFLOW_ORDER)
    assert {
        "product_owner", "ux_designer", "architect", "developer",
        "code_reviewer", "qa_engineer", "security_auditor",
        "customer_advocate", "release_manager",
    } <= keys
    assert ROLE_BY_KEY["code_reviewer"].must_be_independent_of == ("developer",)
    assert ROLE_BY_KEY["security_auditor"].must_be_independent_of == ("developer",)


def test_stage_cannot_start_without_required_evidence():
    assert missing_inputs("ux_designer", {"product_brief": "brief"}) == (
        "acceptance_criteria",
    )
    with pytest.raises(WorkflowPolicyError, match="missing required evidence"):
        validate_stage_entry("developer", {"acceptance_criteria": "AC-1"})


def test_release_is_blocked_when_gates_are_missing():
    decision = evaluate_release_gate({})
    assert decision.passed is False
    assert len(decision.blockers) >= 4


def test_release_requires_executed_tests_and_independent_review():
    evidence = {
        "review_decision": {"status": "PASS", "reviewer_role": "developer"},
        "test_results": {"status": "PASS", "executed": False},
        "security_decision": {"status": "PASS"},
        "customer_review": {"status": "PASS"},
    }
    decision = evaluate_release_gate(evidence)
    assert decision.passed is False
    assert any("actually executed" in blocker for blocker in decision.blockers)
    assert any("cannot approve their own" in blocker for blocker in decision.blockers)


def test_release_passes_only_when_all_mandatory_gates_pass_with_evidence():
    evidence = {
        "review_decision": {"status": "PASS", "decision": "APPROVED", "reviewer_role": "code_reviewer"},
        "test_results": {"status": "PASS", "executed": True, "run_url": "https://example.test/run/1"},
        "security_decision": {"status": "PASS", "decision": "PASS"},
        "customer_review": {"status": "PASS", "decision": "PASS"},
    }
    decision = evaluate_release_gate(evidence)
    assert decision.passed is True
    assert decision.blockers == ()



@pytest.mark.parametrize("body", [
    "Objective: Fix the intake parser.\nRepository: madnessgate44-debug/brain\n/brain simulate",
    "/brain simulate\nObjective: Fix the intake parser.\nRepository: madnessgate44-debug/brain",
    "Repository: madnessgate44-debug/brain\n/brain simulate Fix the intake parser.",
])
def test_issue_parser_preserves_objective_regardless_of_command_position(body):
    repository, objective = parse_issue_body(body)
    assert repository == "madnessgate44-debug/brain"
    assert "Fix the intake parser." in objective
    assert "/brain simulate" not in objective


@pytest.mark.parametrize("body", [
    "/brain simulate\nRepository: madnessgate44-debug/brain",
    "Repository: madnessgate44-debug/brain\n/brain simulate",
    "/brain simulate\nObjective:   \nRepository: madnessgate44-debug/brain",
])
def test_issue_parser_rejects_empty_objective_without_defaulting(body):
    with pytest.raises(RuntimeError, match="Empty mission objective"):
        parse_issue_body(body)


def test_product_owner_contract_does_not_require_future_stage_evidence():
    from brain.company.agent_runner import SpecialistAgentRunner
    import inspect
    source = inspect.getsource(SpecialistAgentRunner.run)
    assert "Do not demand implementation" in source
    assert "preserve unresolved details in open_questions" in source


def test_failure_report_preserves_sanitized_stage_evidence_and_known_non_mutation():
    error = CompanyWorkflowBlocked("product_owner did not pass", stage_evidence={
        "stopped_at": "product_owner", "repository_mutation_started": False,
        "tests_started": False,
        "timeline": [{"role": "product_owner", "status": "BLOCKED", "blockers": ["needs evidence"]}],
        "role_outputs": {"product_owner": {"blockers": ["needs evidence"]}},
    })
    report = failure_report(error, mission={"repository": "madnessgate44-debug/brain"}, events=[])
    assert report["stage_evidence"]["stopped_at"] == "product_owner"
    assert report["stage_evidence"]["role_outputs"]["product_owner"]["blockers"] == ["needs evidence"]
    assert report["impact"]["repository_mutation_status"] == "NOT_STARTED"
    assert report["impact"]["tests_status"] == "NOT_STARTED"


@pytest.mark.parametrize("request_text", [
    "A documentation-only change does NOT satisfy the task.",
    "A docs-only report does not satisfy acceptance.",
])
def test_explicitly_disallowed_documentation_only_change_set_is_rejected(request_text):
    change_set = {"files": [{"path": "docs/BRAIN_RELIABILITY_MISSION_REPORT.md", "content": "# Report"}]}
    errors = validate_change_set_scope(change_set, request_text)
    assert errors
    assert "documentation-only change does not satisfy" in errors[0]


def test_explicit_implementation_requirement_accepts_code_and_regression_tests():
    change_set = {"files": [
        {"path": "brain/company/engine.py", "content": "implementation"},
        {"path": "tests/test_company_workflow.py", "content": "regression test"},
        {"path": "docs/reliability.md", "content": "report"},
    ]}
    assert validate_change_set_scope(
        change_set,
        "A documentation-only change does NOT satisfy the task; add implementation and regression tests.",
    ) == ()


def test_documentation_only_change_remains_allowed_when_requested():
    change_set = {"files": [{"path": "docs/acceptance.md", "content": "# Acceptance"}]}
    assert validate_change_set_scope(
        change_set,
        "Create a documentation-only acceptance report.",
    ) == ()


@pytest.mark.asyncio
async def test_engine_blocks_docs_only_proposal_before_any_repository_write():
    class FakeRunner:
        def __init__(self):
            self.developer_calls = 0

        async def run(self, role_key, user_request, evidence):
            if role_key == "developer":
                self.developer_calls += 1
                return {
                    "status": "PASS",
                    "findings": [],
                    "blockers": [],
                    "evidence_needed": [],
                    "deliverables": {
                        "change_set": {
                            "files": [{
                                "path": "docs/BRAIN_RELIABILITY_MISSION_REPORT.md",
                                "content": "# Report only",
                            }]
                        }
                    },
                }
            deliverables = {
                "product_owner": {
                    "product_brief": "Reliability fix",
                    "acceptance_criteria": ["Implementation change and regression test required"],
                },
                "ux_designer": {"ux_notes": "Not applicable to backend gate"},
                "architect": {"architecture_decisions": ["Preserve current architecture"]},
            }.get(role_key, {})
            return {
                "status": "PASS",
                "findings": [],
                "blockers": [],
                "evidence_needed": [],
                "deliverables": deliverables,
            }

    class FakeTools:
        def __init__(self):
            self.apply_calls = 0

        async def inspect_repository(self, repository):
            return {
                "repository": repository,
                "default_branch": "main",
                "base_commit": "base-sha",
                "files": [],
                "source_contents": {},
                "source_manifest": {"coverage_complete": True},
            }

        async def apply_change_set(self, change_set, repository):
            self.apply_calls += 1
            return {"branch": "unexpected", "diff": "unexpected", "changed_files": []}

        async def run_checks(self, repository, branch):
            return {"executed": True, "status": "PASS", "run_url": "https://example.test/run"}

        async def open_pull_request(self, repository, branch, workflow_result):
            return {"url": "https://example.test/pull/1", "number": 1}

    runner = FakeRunner()
    tools = FakeTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)
    objective = (
        "Fix verified defects and add regression tests. A documentation-only change, "
        "generic checklist, unverified claims, or a run that stops without explicit "
        "diagnosis does NOT satisfy the task."
    )

    with pytest.raises(CompanyWorkflowBlocked, match="remained invalid after repair limit"):
        await engine.run(objective, "madnessgate44-debug/brain")

    assert runner.developer_calls == 3
    assert tools.apply_calls == 0
