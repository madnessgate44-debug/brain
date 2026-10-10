"""Tests for the company workflow orchestration and real-evidence gates."""

import pytest

from brain.company.engine import CompanyWorkflowBlocked, CompanyWorkflowEngine


class FakeAgentRunner:
    def __init__(self, review_statuses=None):
        self.calls = []
        self.review_statuses = list(review_statuses or ["PASS"])

    async def run(self, role_key, user_request, evidence):
        self.calls.append(role_key)
        statuses = {
            "product_owner": {
                "product_brief": "A concise product brief",
                "acceptance_criteria": ["AC-1"],
                "open_questions": [],
            },
            "ux_designer": {
                "user_journeys": ["Open app", "Complete task"],
                "screen_specification": "Mobile-first screen spec",
                "design_system": "Accessible design tokens",
            },
            "architect": {
                "architecture": "API + service + repository",
                "file_plan": ["brain/feature.py"],
                "technical_risks": [],
            },
            "developer": {
                "change_set": {"files": [{"path": "brain/feature.py", "content": "pass\n"}]},
                "implementation_notes": "Implemented AC-1",
            },
            "code_reviewer": {
                "review_findings": [],
                "review_decision": "PASS",
            },
            "qa_engineer": {
                "test_plan": ["Run tests"],
                "test_results": "Tool run passed",
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
                "release_checklist": ["Review PR"],
            },
        }
        status = "PASS"
        if role_key == "code_reviewer":
            status = self.review_statuses.pop(0) if self.review_statuses else "PASS"
        return {
            "role": role_key,
            "status": status,
            "deliverables": statuses[role_key],
            "findings": ["Fix the issue"] if status != "PASS" else [],
            "blockers": [] if status == "PASS" else ["review issue"],
            "evidence_needed": [],
        }


class FakeTools:
    def __init__(self, test_status="PASS", executed=True):
        self.test_status = test_status
        self.executed = executed
        self.apply_count = 0

    async def inspect_repository(self, repository):
        return {
            "repository": repository,
            "default_branch": "main",
            "files": [{"path": "README.md", "size": 100}],
            "source_contents": {"README.md": "Existing project"},
        }

    async def apply_change_set(self, change_set, repository):
        self.apply_count += 1
        return {
            "branch": "brain/feature-test",
            "diff": "diff --git a/brain/feature.py b/brain/feature.py\n+pass",
            "changed_files": ["brain/feature.py"],
        }

    async def run_checks(self, repository, branch):
        return {
            "executed": self.executed,
            "status": self.test_status,
            "run_url": "https://github.com/example/repo/actions/runs/123",
        }

    async def open_pull_request(self, repository, branch, workflow_result):
        return {
            "number": 12,
            "url": "https://github.com/example/repo/pull/12",
            "state": "open",
            "merged": False,
        }


class InvalidFirstChangeSetRunner(FakeAgentRunner):
    """Simulate a model returning an empty patch before correcting itself."""

    def __init__(self, always_invalid=False):
        super().__init__()
        self.developer_calls = 0
        self.always_invalid = always_invalid

    async def run(self, role_key, user_request, evidence):
        output = await super().run(role_key, user_request, evidence)
        if role_key == "developer":
            self.developer_calls += 1
            if self.always_invalid or self.developer_calls == 1:
                output["deliverables"]["change_set"] = {"files": []}
        return output


@pytest.mark.asyncio
async def test_engine_repairs_invalid_change_set_before_writing():
    runner = InvalidFirstChangeSetRunner()
    tools = FakeTools()
    result = await CompanyWorkflowEngine(runner, tools, max_repair_cycles=1).run(
        "Build a small feature", "owner/repository"
    )
    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert runner.developer_calls == 2
    assert tools.apply_count == 1


@pytest.mark.asyncio
async def test_engine_stops_before_writing_when_change_set_stays_invalid():
    runner = InvalidFirstChangeSetRunner(always_invalid=True)
    tools = FakeTools()
    with pytest.raises(CompanyWorkflowBlocked, match="remained invalid after repair limit"):
        await CompanyWorkflowEngine(runner, tools, max_repair_cycles=1).run(
            "Build a small feature", "owner/repository"
        )
    assert runner.developer_calls == 2
    assert tools.apply_count == 0


@pytest.mark.asyncio
async def test_engine_runs_specialists_and_stops_at_human_approval():
    runner = FakeAgentRunner()
    tools = FakeTools()
    engine = CompanyWorkflowEngine(runner, tools)

    result = await engine.run("Build a small feature", "owner/repository")

    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert result["next_action"].startswith("Human review required")
    assert "code_reviewer" in runner.calls
    assert "qa_engineer" in runner.calls
    assert result["release_gate"]["passed"] is True


@pytest.mark.asyncio
async def test_engine_blocks_when_real_checks_fail():
    engine = CompanyWorkflowEngine(FakeAgentRunner(), FakeTools(test_status="FAIL"))
    with pytest.raises(CompanyWorkflowBlocked, match="checks failed"):
        await engine.run("Build a small feature", "owner/repository")


@pytest.mark.asyncio
async def test_engine_blocks_when_checks_were_not_executed():
    engine = CompanyWorkflowEngine(FakeAgentRunner(), FakeTools(executed=False))
    with pytest.raises(CompanyWorkflowBlocked, match="actual test execution"):
        await engine.run("Build a small feature", "owner/repository")


@pytest.mark.asyncio
async def test_engine_retries_review_failure_only_within_limit():
    runner = FakeAgentRunner(review_statuses=["NEEDS_WORK", "PASS"])
    tools = FakeTools()
    engine = CompanyWorkflowEngine(runner, tools, max_repair_cycles=1)

    result = await engine.run("Build a small feature", "owner/repository")

    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert tools.apply_count == 2


@pytest.mark.asyncio
async def test_engine_blocks_review_failure_after_repair_limit():
    runner = FakeAgentRunner(review_statuses=["NEEDS_WORK", "NEEDS_WORK"])
    engine = CompanyWorkflowEngine(runner, FakeTools(), max_repair_cycles=1)
    with pytest.raises(CompanyWorkflowBlocked, match="after repair limit"):
        await engine.run("Build a small feature", "owner/repository")


@pytest.mark.asyncio
async def test_customer_gate_failure_reports_decision_and_counts():
    """A blocked customer gate should expose safe decision metadata for diagnosis."""
    class BlockedCustomerRunner(FakeAgentRunner):
        async def run(self, role_key, user_request, evidence):
            output = await super().run(role_key, user_request, evidence)
            if role_key == "customer_advocate":
                output["status"] = "NEEDS_WORK"
                output["deliverables"]["customer_review"] = "NEEDS_WORK"
                output["blockers"] = ["first issue", "second issue"]
                output["findings"] = ["finding"]
                output["evidence_needed"] = ["evidence"]
            return output

    engine = CompanyWorkflowEngine(BlockedCustomerRunner(), FakeTools())
    with pytest.raises(
        CompanyWorkflowBlocked,
        match=r"Customer review did not pass .*decision='NEEDS_WORK'.*findings=1, blockers=2, evidence_needed=1",
    ):
        await engine.run("Create a documentation-only report", "owner/repository")
