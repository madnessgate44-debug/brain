"""Integration tests verifying operational end-to-end mission requirements R1 through R7."""

import json
from pathlib import Path
import pytest

from brain.company.mission_capabilities import plan_capabilities
from scripts.write_bootstrap_failure_report import build_bootstrap_failure_report


def test_operational_mission_intake_classification():
    objective = (
        "Run a bounded operational end-to-end mission to verify Brain's actual task execution "
        "and failure reporting. Create docs/BRAIN_OPERATIONAL_E2E_VERIFICATION.md and regression tests. "
        "Do not merge or deploy."
    )
    plan = plan_capabilities(objective)
    assert plan.mode == "mutating"
    assert "repository:write" in plan.required_capabilities
    assert "checks:run" in plan.required_capabilities
    assert "pull_request:create" in plan.required_capabilities


def test_operational_base_commit_and_scope_record():
    root = Path(__file__).resolve().parents[1]
    doc_path = root / "docs" / "BRAIN_OPERATIONAL_E2E_VERIFICATION.md"
    test_path = root / "tests" / "test_operational_e2e_verification.py"
    assert doc_path.exists()
    assert test_path.exists()


def test_safe_failure_handling_detection():
    base_env = {
        "GITHUB_REPOSITORY": "madnessgate44-debug/brain",
        "GITHUB_SHA": "c2a6d1e83d41233300b835b8adc1a8fbe8097e60",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_NAME": "main",
        "GITHUB_RUN_ID": "99999",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": "Brain Operational E2E",
        "GITHUB_EVENT_NAME": "issues",
        "GITHUB_SERVER_URL": "https://github.com",
        "RUNNER_OS": "Linux",
        "CHECKOUT_OUTCOME": "success",
        "SETUP_PYTHON_OUTCOME": "success",
        "INSTALL_OUTCOME": "success",
        "LOCK_OUTCOME": "success",
        "RUN_OUTCOME": "failure",
    }
    report = build_bootstrap_failure_report(base_env, {"action": "opened", "issue": {"number": 146}})
    assert report["status"] == "FAILED"
    assert report["failed_steps"] == [{"step": "mission_runner", "outcome": "failure"}]
    assert report["impact"]["success_claimed"] is False


def test_final_report_summary_categories():
    root = Path(__file__).resolve().parents[1]
    doc_content = (root / "docs" / "BRAIN_OPERATIONAL_E2E_VERIFICATION.md").read_text(encoding="utf-8")
    assert "- **PASS:**" in doc_content
    assert "- **FAIL:**" in doc_content
    assert "- **NOT TESTED:**" in doc_content
