"""End-to-end stress specialist fault-injection tests for CompanyWorkflowEngine."""

import pytest
from typing import Any

from brain.company.engine import (
    CompanyWorkflowBlocked,
    CompanyWorkflowEngine,
    validate_change_set,
)
from brain.company.roles import WORKFLOW_ORDER


class StressTestAgentRunner:
    """Configurable agent runner for simulating specialist behaviors and fault injections."""

    def __init__(
        self,
        *,
        developer_invalid_once: bool = False,
        reviewer_reject_once: bool = False,
        blocking_role: str | None = None,
        blocking_status: str = "NEEDS_WORK",
    ):
        self.calls = []
        self.review_evidence = []
        self.developer_call_count = 0
        self.reviewer_call_count = 0
        self.developer_invalid_once = developer_invalid_once
        self.reviewer_reject_once = reviewer_reject_once
        self.blocking_role = blocking_role
        self.blocking_status = blocking_status

    async def run(self, role_key: str, user_request: str, evidence: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(role_key)
        
        status = "PASS"
        blockers = []
        findings = []

        if self.blocking_role and role_key == self.blocking_role:
            status = self.blocking_status
            blockers = [f"{role_key} decision is blocked due to fault injection"]
            findings = [f"Critical issue found by {role_key}"]

        deliverables: dict[str, Any] = {}

        if role_key == "product_owner":
            deliverables = {
                "product_brief": "Stress test product brief",
                "acceptance_criteria": ["AC-1: Fault injection resilience"],
                "open_questions": [],
            }
        elif role_key == "ux_designer":
            deliverables = {
                "user_journeys": ["Complete stress workflow"],
                "screen_specification": "Clean layout",
                "design_system": "Tokens",
            }
        elif role_key == "architect":
            deliverables = {
                "architecture": "Service + repository",
                "file_plan": ["brain/stress_feature.py"],
                "technical_risks": [],
            }
        elif role_key == "developer":
            self.developer_call_count += 1
            if self.developer_invalid_once and self.developer_call_count == 1:
                deliverables = {
                    "change_set": {"files": []},
                    "implementation_notes": "Attempting invalid change set",
                }
            else:
                deliverables = {
                    "change_set": {
                        "files": [{"path": "brain/stress_feature.py", "content": "# stress feature implementation\n"}]
                    },
                    "implementation_notes": "Implemented feature successfully",
                }
        elif role_key == "code_reviewer":
            self.reviewer_call_count += 1
            if self.reviewer_reject_once and self.reviewer_call_count == 1:
                status = "NEEDS_WORK"
                blockers = ["Missing unit tests for edge cases"]
                findings = ["Concrete finding: add tests for error handling"]
                deliverables = {
                    "review_findings": findings,
                    "review_decision": "NEEDS_WORK",
                }
            else:
                deliverables = {
                    "review_findings": [],
                    "review_decision": "PASS",
                }
        elif role_key == "qa_engineer":
            deliverables = {
                "test_plan": ["Run stress test suite"],
                "test_results": "All tests passed successfully",
                "defect_list": [],
            }
        elif role_key == "security_auditor":
            deliverables = {
                "security_findings": [],
                "security_decision": "PASS",
            }
        elif role_key == "customer_advocate":
            deliverables = {
                "customer_review": "PASS",
                "usability_findings": [],
            }
        elif role_key == "release_manager":
            deliverables = {
                "release_decision": "READY_FOR_HUMAN_APPROVAL",
                "release_checklist": ["Verify gates and PR"],
            }

        return {
            "role": role_key,
            "status": status,
            "deliverables": deliverables,
            "findings": findings,
            "blockers": blockers,
            "evidence_needed": [],
        }


class StressTestTools:
    """Configurable repository tools double for stress fault-injection tests."""

    def __init__(self, *, check_status: str = "PASS", check_executed: bool = True):
        self.apply_count = 0
        self.check_count = 0
        self.pr_count = 0
        self.check_status = check_status
        self.check_executed = check_executed
        self.applied_change_sets = []
        self.check_calls = []

    async def inspect_repository(self, repository: str) -> dict[str, Any]:
        return {
            "repository": repository,
            "default_branch": "main",
            "base_commit": "feedface",
            "files": [{"path": "README.md", "size": 42}],
            "source_contents": {"README.md": "# Stress Repo\n"},
        }

    async def apply_change_set(self, change_set: dict[str, Any], repository: str) -> dict[str, Any]:
        self.apply_count += 1
        self.applied_change_sets.append(change_set)
        return {
            "branch": f"brain/stress-feature-{self.apply_count}",
            "diff": f"diff --git a/brain/stress_feature.py b/brain/stress_feature.py\n+# attempt {self.apply_count}",
            "changed_files": [item["path"] for item in change_set.get("files", [])],
        }

    async def run_checks(self, repository: str, branch: str) -> dict[str, Any]:
        self.check_count += 1
        self.check_calls.append({"repository": repository, "branch": branch})
        return {
            "executed": self.check_executed,
            "status": self.check_status,
            "run_url": "https://github.com/example/stress-repo/actions/runs/999",
        }

    async def open_pull_request(self, repository: str, branch: str, workflow_result: dict[str, Any]) -> dict[str, Any]:
        self.pr_count += 1
        return {
            "number": 101,
            "url": f"https://github.com/{repository}/pull/101",
            "state": "open",
            "merged": False,
        }


@pytest.mark.asyncio
async def test_developer_invalid_change_set_repaired_within_limit():
    """Scenario 1: Developer proposes an invalid change set once, then repairs it within limit.
    Verify no repository write occurs before validation passes.
    """
    runner = StressTestAgentRunner(developer_invalid_once=True)
    tools = StressTestTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    result = await engine.run("Implement stress feature with repair validation", "owner/stress-repo")

    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert runner.developer_call_count == 2
    assert tools.apply_count == 1
    assert len(tools.applied_change_sets) == 1
    assert tools.applied_change_sets[0]["files"][0]["path"] == "brain/stress_feature.py"

    timeline_roles = [item["role"] for item in result["timeline"]]
    assert timeline_roles.index("product_owner") < timeline_roles.index("ux_designer")
    assert timeline_roles.index("ux_designer") < timeline_roles.index("architect")
    assert timeline_roles.index("architect") < timeline_roles.index("developer_preflight")
    assert timeline_roles.index("developer_preflight") < timeline_roles.index("developer")
    assert "product_owner" in timeline_roles
    assert "architect" in timeline_roles
    assert "developer" in timeline_roles
    assert "code_reviewer" in timeline_roles
    assert "qa_engineer" in timeline_roles
    assert "security_auditor" in timeline_roles
    assert "customer_advocate" in timeline_roles
    assert "release_manager" in timeline_roles


@pytest.mark.asyncio
async def test_code_reviewer_rejects_then_developer_repairs_then_reviewer_passes():
    """Scenario 2: Code reviewer rejects first implementation with concrete finding;
    developer repairs it; reviewer independently passes; verify changed diff is reviewed and checks run.
    """
    runner = StressTestAgentRunner(reviewer_reject_once=True)
    tools = StressTestTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    result = await engine.run("Implement feature with code review feedback cycle", "owner/stress-repo")

    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert tools.apply_count == 2
    assert tools.check_count == 1
    assert len(runner.review_evidence) == 2
    assert runner.review_evidence[0]["actual_diff"] != runner.review_evidence[1]["actual_diff"]
    assert runner.review_evidence[0]["branch"] == "brain/stress-feature-1"
    assert runner.review_evidence[1]["branch"] == "brain/stress-feature-2"
    assert runner.review_evidence[1]["changed_files"] == ["brain/stress_feature.py"]
    assert tools.check_calls == [{
        "repository": "owner/stress-repo",
        "branch": "brain/stress-feature-2",
    }]
    assert result["test_evidence"]["status"] == "PASS"
    assert result["test_evidence"]["executed"] is True
    assert tools.pr_count == 1
    assert result["pull_request"]["number"] == 101


@pytest.mark.asyncio
async def test_repository_checks_fail_blocks_release_and_preserves_evidence():
    """Scenario 3: Repository checks fail; verify release/PR creation is blocked and failure evidence is preserved."""
    runner = StressTestAgentRunner()
    tools = StressTestTools(check_status="FAIL", check_executed=True)
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=2)

    with pytest.raises(
        CompanyWorkflowBlocked,
        match="Repository checks failed; release is blocked",
    ) as exc_info:
        await engine.run("Implement feature with failing test suite", "owner/stress-repo")

    evidence = exc_info.value.stage_evidence
    assert evidence["stopped_at"] == "repository_checks"
    assert evidence["test_evidence"] == {
        "executed": True,
        "status": "FAIL",
        "run_url": "https://github.com/example/stress-repo/actions/runs/999",
    }
    assert evidence["branch"] == "brain/stress-feature-1"
    assert evidence["changed_files"] == ["brain/stress_feature.py"]
    assert "diff --git" in evidence["actual_diff"]
    assert evidence["repository_mutation_started"] is True
    assert evidence["tests_started"] is True
    assert evidence["release_blocked"] is True
    assert evidence["pull_request_created"] is False
    assert tools.pr_count == 0


@pytest.mark.asyncio
async def test_required_specialist_blocking_stops_pipeline_before_mutation():
    """Scenario 4: A required specialist returns a blocking status before implementation;
    verify pipeline stops at correct gate and no repository mutation or PR creation occurs.
    """
    for blocked_role in ["product_owner", "ux_designer", "architect"]:
        runner = StressTestAgentRunner(blocking_role=blocked_role)
        tools = StressTestTools()
        engine = CompanyWorkflowEngine(runner, tools)

        with pytest.raises(CompanyWorkflowBlocked) as exc_info:
            await engine.run("Implement feature with early specialist block", "owner/stress-repo")

        evidence = exc_info.value.stage_evidence
        assert evidence.get("stopped_at") == blocked_role
        assert evidence.get("repository_mutation_started") is False
        assert evidence.get("tests_started") is False
        assert tools.apply_count == 0
        assert tools.pr_count == 0
