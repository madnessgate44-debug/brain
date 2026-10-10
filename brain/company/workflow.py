"""Deterministic workflow policy for Brain's software-company pipeline.

This module governs order, required inputs, evidence, and gate decisions. It does not
pretend that a role has run merely because a prompt exists; callers must record each
role's actual output and any external execution evidence.
"""

from dataclasses import dataclass
from typing import Any

from brain.company.roles import MANDATORY_RELEASE_GATES, ROLE_BY_KEY, WORKFLOW_ORDER


class WorkflowPolicyError(ValueError):
    """Raised when a workflow stage is attempted without required evidence."""


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    blockers: tuple[str, ...]
    rationale: str


def missing_inputs(role_key: str, evidence: dict[str, Any]) -> tuple[str, ...]:
    """Return the required evidence keys absent or empty for a role."""
    if role_key not in ROLE_BY_KEY:
        raise WorkflowPolicyError(f"Unknown specialist role: {role_key}")
    role = ROLE_BY_KEY[role_key]
    return tuple(
        key for key in role.required_inputs
        if key not in evidence or evidence[key] is None or evidence[key] == ""
    )


def validate_stage_entry(role_key: str, evidence: dict[str, Any]) -> None:
    """Reject a stage when prerequisites have not been recorded."""
    missing = missing_inputs(role_key, evidence)
    if missing:
        raise WorkflowPolicyError(
            f"Cannot start {role_key}; missing required evidence: {', '.join(missing)}"
        )


def evaluate_release_gate(evidence: dict[str, Any]) -> GateDecision:
    """Require explicit positive decisions and real QA evidence before release."""
    blockers: list[str] = []
    for key in MANDATORY_RELEASE_GATES:
        value = evidence.get(key)
        if value is None or value == "":
            blockers.append(f"Missing required gate evidence: {key}")
            continue
        if isinstance(value, dict):
            status = str(value.get("status", "")).strip().upper()
            if status not in {"PASS", "APPROVED"}:
                blockers.append(f"{key} did not pass")
        elif isinstance(value, str):
            if value.strip().upper() not in {"PASS", "APPROVED"}:
                blockers.append(f"{key} did not pass")
        else:
            blockers.append(f"{key} has no recognized decision format")

    test_results = evidence.get("test_results")
    if not isinstance(test_results, dict):
        blockers.append("QA evidence must be a structured result from the real check runner")
    else:
        if test_results.get("executed") is not True:
            blockers.append("QA evidence does not confirm tests were actually executed")
        if str(test_results.get("status", "")).strip().upper() != "PASS":
            blockers.append("QA execution result did not pass")
        if not isinstance(test_results.get("run_url"), str) or not test_results["run_url"].startswith("https://"):
            blockers.append("QA evidence is missing a verifiable HTTPS workflow run URL")

    review = evidence.get("review_decision")
    if isinstance(review, dict) and review.get("reviewer_role") == "developer":
        blockers.append("The developer cannot approve their own implementation")

    return GateDecision(
        passed=not blockers,
        blockers=tuple(blockers),
        rationale=(
            "All mandatory independent gates passed."
            if not blockers else
            "Release blocked until every mandatory gate has explicit passing evidence."
        ),
    )


def next_role(completed_roles: list[str], evidence: dict[str, Any]) -> str | None:
    """Return the next role whose prerequisites are available, or None when blocked/done."""
    for role_key in WORKFLOW_ORDER:
        if role_key in completed_roles:
            continue
        if missing_inputs(role_key, evidence):
            return None
        return role_key
    return None
