"""Tests for the company workflow orchestration and real-evidence gates."""

import pytest

from brain.company.agent_runner import _prepare_prompt_evidence
from brain.company.engine import CompanyWorkflowBlocked, CompanyWorkflowEngine, validate_change_set


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
            "base_commit": "abc123",
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


def test_validate_change_set_rejects_unsafe_and_duplicate_paths():
    errors = validate_change_set({
        "files": [
            {"path": "../outside.py", "content": "pass"},
            {"path": "brain/safe.py", "content": "pass"},
            {"path": "brain/safe.py", "content": "again"},
            {"path": "brain\\unsafe.py", "content": "pass"},
        ]
    })
    assert any("unsafe" in error for error in errors)
    assert any("duplicate file path" in error for error in errors)


def test_validate_change_set_enforces_file_count_and_size_limits():
    too_many = {"files": [{"path": f"src/file_{i}.py", "content": "x"} for i in range(31)]}
    oversized = {"files": [{"path": "src/large.py", "content": "x" * 200_001}]}
    assert any("between 1 and 30 files" in error for error in validate_change_set(too_many))
    assert any("200,000-byte" in error for error in validate_change_set(oversized))


def test_validate_change_set_rejects_non_text_content_and_empty_patch():
    assert validate_change_set({"files": []})
    assert any(
        "must be text" in error
        for error in validate_change_set({"files": [{"path": "src/file.py", "content": None}]})
    )


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
    assert result["base_commit"] == "abc123"
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


@pytest.mark.asyncio
async def test_engine_preserves_planned_source_files_for_role_specific_prompt_selection():
    planned_path = "tests/test_company_run_issue_workflow.py"
    target_path = "docs/BRAIN_RUNTIME_VERIFICATION.md"

    class CapturingRunner(FakeAgentRunner):
        def __init__(self):
            super().__init__()
            self.developer_evidence = None

        async def run(self, role_key, user_request, evidence):
            output = await super().run(role_key, user_request, evidence)
            if role_key == "architect":
                output["deliverables"]["file_plan"] = [planned_path]
            if role_key == "developer":
                self.developer_evidence = evidence
            return output

    class LargeRepositoryTools(FakeTools):
        async def inspect_repository(self, repository):
            module_paths = [f"src/module_{i}.py" for i in range(80)]
            paths = ["README.md", target_path, planned_path, *module_paths]
            source_contents = {
                "README.md": "readme evidence " * 1000,
                target_path: "target file context",
                planned_path: "def test_source_file_is_available():\\n    assert True\\n",
                **{f"src/module_{i}.py": f"source evidence {i} " * 1000 for i in range(80)},
            }
            return {
                "repository": repository,
                "default_branch": "main",
                "base_commit": "abc123",
                "files": [{"path": path, "size": len(source_contents[path])} for path in paths],
                "source_contents": source_contents,
                "source_manifest": {
                    "candidate_count": len(paths),
                    "read_count": len(paths),
                    "coverage_complete": True,
                    "failed_paths": {},
                    "omitted_by_aggregate_budget": [],
                    "candidate_paths": paths,
                    "read_paths": paths,
                    "aggregate_bytes_read": sum(len(text) for text in source_contents.values()),
                },
            }

    runner = CapturingRunner()
    engine = CompanyWorkflowEngine(runner, LargeRepositoryTools())
    objective = f"Create {target_path} with verified runtime evidence"
    await engine.run(objective, "owner/repository")

    snapshot = runner.developer_evidence["repository_snapshot"]
    assert len(snapshot["source_contents"]) == 83
    assert sum(map(len, snapshot["source_contents"].values())) > 41_000
    assert planned_path in snapshot["source_contents"]
    assert snapshot["source_manifest"]["source_contents_retained_count"] == 83
    assert snapshot["source_manifest"]["source_selection_deferred_to_role_runner"] is True
    assert len(snapshot["files"]) <= 300

    # The actual role prompt still stays within its own budget and includes the
    # architect-planned file, even though the user did not name that path.
    prompt_evidence = _prepare_prompt_evidence("developer", objective, runner.developer_evidence)
    prompt_snapshot = prompt_evidence["repository_snapshot"]
    assert planned_path in prompt_snapshot["source_contents"]
    assert prompt_snapshot["source_selection"]["omitted_explicit_paths"] == []
    assert prompt_snapshot["source_selection"]["selected_chars"] <= 90_000
