"""Policy tests for the software-company workflow."""

import pytest

from brain.company.roles import ROLE_CATALOG, ROLE_BY_KEY, WORKFLOW_ORDER
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
        "security_decision": {"status": "PASS", "reviewer_role": "security_auditor"},
        "customer_review": {"status": "PASS", "reviewer_role": "customer_advocate"},
    }
    decision = evaluate_release_gate(evidence)
    assert decision.passed is False
    assert any("actually executed" in blocker for blocker in decision.blockers)
    assert any("cannot approve their own" in blocker for blocker in decision.blockers)


def test_release_passes_only_when_all_mandatory_gates_pass_with_evidence():
    evidence = {
        "review_decision": {"status": "APPROVED", "reviewer_role": "code_reviewer"},
        "test_results": {"status": "PASS", "executed": True, "run_url": "https://example.test/run/1"},
        "security_decision": {"status": "PASS", "reviewer_role": "security_auditor"},
        "customer_review": {"status": "PASS", "reviewer_role": "customer_advocate"},
    }
    decision = evaluate_release_gate(evidence)
    assert decision.passed is True
    assert decision.blockers == ()



@pytest.mark.parametrize(
    "test_results",
    [
        "PASS",
        {"status": "PASS", "executed": True},
        {"status": "FAIL", "executed": True, "run_url": "https://example.test/run/1"},
    ],
)
def test_release_rejects_unverifiable_or_nonpassing_test_results(test_results):
    decision = evaluate_release_gate({
        "review_decision": {"status": "PASS", "reviewer_role": "code_reviewer"},
        "test_results": test_results,
        "security_decision": {"status": "PASS"},
        "customer_review": {"status": "PASS"},
    })

    assert decision.passed is False
    assert any("QA" in blocker for blocker in decision.blockers)



def test_release_rejects_gate_decisions_without_the_required_independent_role():
    decision = evaluate_release_gate({
        "review_decision": "PASS",
        "test_results": {"status": "PASS", "executed": True, "run_url": "https://example.test/run/1"},
        "security_decision": {"status": "PASS"},
        "customer_review": {"status": "PASS"},
    })

    assert decision.passed is False
    assert any("independent reviewer" in blocker for blocker in decision.blockers)
    assert any("security_auditor" in blocker for blocker in decision.blockers)
    assert any("customer_advocate" in blocker for blocker in decision.blockers)
