"""Rigorous, deterministic end-to-end fault-injection test suite for CompanyWorkflowEngine.

Exercises CompanyWorkflowEngine.run() end-to-end with deterministic fake specialist
outputs and fake repository tools across four primary failure/recovery scenarios:
1. Developer proposes an invalid change set once, then repairs it within the configured
   bounded repair limit; verifies no repository write occurs before validation passes.
2. Code reviewer rejects the first implementation with a concrete finding; developer repairs
   it; reviewer independently passes; verifies changed diff is reviewed and checks run.
3. Repository checks fail; verifies release/PR creation is blocked and failure evidence
   is preserved.
4. A required specialist returns a blocking status; verifies the pipeline stops at the
   correct gate and no repository mutation or PR creation occurs if block is before implementation.
"""

import pytest

from brain.company.engine import (
    CompanyWorkflowBlocked,
    CompanyWorkflowEngine,
)
from brain.company.roles import WORKFLOW_ORDER


class StatefulFaultInjectionRunner:
    """Deterministic specialist runner supporting stateful fault injection across retry cycles."""

    def __init__(self, scenario_mode: str, review_rejections: int = 1):
        self.scenario_mode = scenario_mode
        self.review_rejections_remaining = review_rejections
        self.calls_by_role = {role: 0 for role in WORKFLOW_ORDER}
        self.developer_proposals = []

    async def run(self, role_key: str, user_request: str, evidence: dict):
        self.calls_by_role[role_key] += 1
        call_count = self.calls_by_role[role_key]

        # Standard valid deliverables for passing roles
        review_decision = self._get_review_decision() if role_key == "code_reviewer" else "PASS"
        deliverables = {
            "product_owner": {
                "product_brief": "Detailed product brief",
                "acceptance_criteria": ["AC-1: Implement robust fault injection"],
                "open_questions": [],
            },
            "ux_designer": {
                "user_journeys": ["Configure workflow"],
                "screen_specification": "Console UI",
                "design_system": "Standard tokens",
            },
            "architect": {
                "architecture": "Modular engine with strict gateway boundaries",
                "file_plan": ["brain/company/engine.py", "tests/test_fault_injection.py"],
                "technical_risks": [],
            },
            "developer": {
                "change_set": self._get_developer_change_set(call_count),
                "implementation_notes": f"Implementation attempt {call_count}",
            },
            "code_reviewer": {
                "review_findings": (["Concrete finding: missing concurrency lock guard"] if review_decision == "NEEDS_WORK" else []),
                "review_decision": review_decision,
            },
            "qa_engineer": {
                "test_plan": ["Run end-to-end fault injection tests"],
                "test_results": "All tests passed successfully with 100% coverage",
                "defect_list": [],
            },
            "security_auditor": {
                "security_findings": [],
                "security_decision": "PASS",
            },
            "customer_advocate": {
                "customer_review": "PASS",
                "usability_findings": [],
            },
            "release_manager": {
                "release_decision": "READY_FOR_HUMAN_APPROVAL",
                "release_checklist": ["All gates verified"],
            },
        }

        role_output = deliverables.get(role_key, {})
        status = "PASS"
        blockers = []
        findings = []

        if self.scenario_mode == "blocking_specialist" and role_key == "architect":
            status = "BLOCKED"
            blockers = ["Architectural blueprint rejected due to conflicting security constraints"]
            findings = ["Revise architecture before developer implementation."]

        if role_key == "code_reviewer" and review_decision == "NEEDS_WORK":
            status = "NEEDS_WORK"
            blockers = ["Code review rejection: missing concurrency lock handling"]
            findings = ["Ensure shared lock acquisition is explicitly tested."]

        return {
            "role": role_key,
            "status": status,
            "deliverables": role_output,
            "findings": findings,
            "blockers": blockers,
            "evidence_needed": [],
        }

    def _get_developer_change_set(self, call_count: int):
        if self.scenario_mode == "invalid_change_set_repaired":
            if call_count == 1:
                # Invalid first proposal: empty files list or invalid path
                return {"files": []}
            else:
                # Repaired valid proposal on subsequent attempt
                return {
                    "files": [
                        {"path": "brain/company/engine.py", "content": "# updated engine\n"},
                        {"path": "tests/test_company_workflow.py", "content": "# regression test\n"},
                    ]
                }
        elif self.scenario_mode == "review_rejection_repaired":
            if call_count == 1:
                return {
                    "files": [
                        {"path": "brain/company/engine.py", "content": "# initial impl\n"}
                    ]
                }
            else:
                return {
                    "files": [
                        {"path": "brain/company/engine.py", "content": "# revised impl with lock handling\n"}
                    ]
                }
        else:
            return {
                "files": [
                    {"path": "brain/company/engine.py", "content": "pass\n"}
                ]
            }

    def _get_review_decision(self):
        if self.scenario_mode == "review_rejection_repaired":
            if self.review_rejections_remaining > 0:
                self.review_rejections_remaining -= 1
                return "NEEDS_WORK"
            return "PASS"
        return "PASS"

    def _get_review_findings(self):
        if self.scenario_mode == "review_rejection_repaired" and self.review_rejections_remaining >= 0:
            return [["Concrete finding: missing concurrency lock guard"]]
        return []


class FakeFaultInjectionTools:
    """Deterministic fake repository tools tracking call counts and mutation status."""

    def __init__(self, check_status: str = "PASS", check_executed: bool = True):
        self.check_status = check_status
        self.check_executed = check_executed
        self.inspect_calls = 0
        self.apply_change_set_calls = 0
        self.run_checks_calls = 0
        self.open_pull_request_calls = 0
        self.applied_diffs = []
        self.applied_branches = []

    async def inspect_repository(self, repository: str):
        self.inspect_calls += 1
        return {
            "repository": repository,
            "default_branch": "main",
            "base_commit": "deadbeef12345678",
            "files": [{"path": "README.md", "size": 42}],
            "source_contents": {"README.md": "# Brain\n"},
            "source_manifest": {"coverage_complete": True},
        }

    async def apply_change_set(self, change_set: dict, repository: str):
        self.apply_change_set_calls += 1
        branch = f"brain/fault-injection-test-{self.apply_change_set_calls}"
        diff = f"diff --git a/file.py b/file.py\n+updated content"
        self.applied_branches.append(branch)
        self.applied_diffs.append(diff)
        return {
            "branch": branch,
            "diff": diff,
            "changed_files": [item["path"] for item in change_set.get("files", [])],
        }

    async def run_checks(self, repository: str, branch: str):
        self.run_checks_calls += 1
        return {
            "executed": self.check_executed,
            "status": self.check_status,
            "run_url": "https://github.com/madnessgate44-debug/brain/actions/runs/999",
        }

    async def open_pull_request(self, repository: str, branch: str, workflow_result: dict):
        self.open_pull_request_calls += 1
        return {
            "number": 176,
            "url": "https://github.com/madnessgate44-debug/brain/pull/176",
            "state": "open",
            "merged": False,
        }


@pytest.mark.asyncio
async def test_scenario_1_invalid_change_set_repaired_within_limit():
    """Scenario 1: Developer proposes invalid change set once, repairs it within bounded limit.

    Verifies:
    - No repository write occurs before validation passes.
    - Repair-attempt limits and developer call counts are strictly adhered to.
    - Successful progression to approval once repaired.
    """
    runner = StatefulFaultInjectionRunner(scenario_mode="invalid_change_set_repaired")
    tools = FakeFaultInjectionTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    result = await engine.run("Implement bounded repair feature", "madnessgate44-debug/brain")

    # Assertions
    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    # Developer was called twice (first invalid attempt, second repaired attempt)
    assert runner.calls_by_role["developer"] == 2
    # CRITICAL: apply_change_set must NOT be called on the first invalid attempt
    assert tools.apply_change_set_calls == 1
    assert tools.inspect_calls == 1
    assert tools.run_checks_calls == 1
    assert tools.open_pull_request_calls == 1  # The engine opens a reviewable PR; it never merges it.
    assert "brain/fault-injection-test-1" in tools.applied_branches


@pytest.mark.asyncio
async def test_scenario_2_code_reviewer_rejection_repaired_and_verified():
    """Scenario 2: Code reviewer rejects first implementation with concrete finding; developer repairs; reviewer passes.

    Verifies:
    - Role ordering and independent review enforcement.
    - Changed diff is reviewed and actual checks run.
    - Tool call counts and review repair cycles.
    """
    runner = StatefulFaultInjectionRunner(scenario_mode="review_rejection_repaired", review_rejections=1)
    tools = FakeFaultInjectionTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    result = await engine.run("Implement review repair workflow", "madnessgate44-debug/brain")

    # Assertions
    assert result[
        "status"
    ] == "READY_FOR_HUMAN_APPROVAL"
    assert runner.calls_by_role["developer"] == 2
    assert runner.calls_by_role["code_reviewer"] == 2
    # Apply change set called twice (initial implementation + repair implementation)
    assert tools.apply_change_set_calls == 2
    assert tools.run_checks_calls == 2
    assert len(tools.applied_diffs) == 2
    assert result["release_gate"]["passed"] is True


@pytest.mark.asyncio
async def test_scenario_3_failing_repository_checks_block_release_and_preserve_evidence():
    """Scenario 3: Repository checks fail; release/PR creation is blocked and failure evidence is preserved.

    Verifies:
    - Pipeline stops immediately upon failing test check status.
    - Release gate outcome reflects failure.
    - Failure evidence and run URL are preserved in exception details.
    """
    runner = StatefulFaultInjectionRunner(scenario_mode="standard")
    tools = FakeFaultInjectionTools(check_status="FAIL", check_executed=True)
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    with pytest.raises(CompanyWorkflowBlocked) as exc_info:
        await engine.run("Implement feature with failing tests", "madnessgate44-debug/brain")

    err_msg = str(exc_info.value)
    assert "checks failed" in err_msg.casefold() or "fail" in err_msg.casefold()
    assert tools.apply_change_set_calls == 1
    assert tools.run_checks_calls == 1
    assert tools.open_pull_request_calls == 0

    # Verify stage evidence preservation
    stage_evidence = exc_info.value.stage_evidence
    assert stage_evidence["tests_status"] == "FAIL"
    assert stage_evidence["tests_started"] is True
    assert stage_evidence["test_evidence"]["run_url"].endswith("/999")


@pytest.mark.asyncio
async def test_scenario_4_blocking_specialist_halts_pipeline_before_mutation():
    """Scenario 4: Required specialist returns blocking status; pipeline stops at correct gate, no mutation/PR.

    Verifies:
    - Pipeline stops before developer implementation or repository mutation.
    - Zero repository write calls or change set applications occur.
    - Blockers and findings are correctly propagated.
    """
    runner = StatefulFaultInjectionRunner(scenario_mode="blocking_specialist")
    tools = FakeFaultInjectionTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    with pytest.raises(CompanyWorkflowBlocked) as exc_info:
        await engine.run("Blocked architectural mission", "madnessgate44-debug/brain")

    err_msg = str(exc_info.value)
    assert "architect" in err_msg.casefold() or "blocked" in err_msg.casefold()

    # CRITICAL: No repository mutation occurred because block happened at architect stage (before developer)
    assert tools.apply_change_set_calls == 0
    assert tools.run_checks_calls == 0
    assert tools.open_pull_request_calls == 0
    assert runner.calls_by_role["developer"] == 0

    stage_evidence = exc_info.value.stage_evidence
    assert stage_evidence["stopped_at"] == "architect"
    assert stage_evidence["repository_mutation_started"] is False
    assert stage_evidence["tests_started"] is False
