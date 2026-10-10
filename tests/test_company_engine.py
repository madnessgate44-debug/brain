"""Tests for the company workflow orchestration and real-evidence gates."""

import pytest

from brain.company.engine import (
    CompanyWorkflowBlocked,
    CompanyWorkflowEngine,
    _compact_repository_snapshot,
    validate_change_set,
)


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


def test_validate_change_set_rejects_unsafe_and_duplicate_paths():
    errors = validate_change_set({
        "files": [
            {"path": "../outside.py", "content": "pass"},
            {"path": "brain/safe.py", "content": "pass"},
            {"path": "brain/safe.py", "content": "again"},
            {"path": "brain\\unsafe.py", "content": "pass"},
            {"path": ".git/config", "content": "pass"},
            {"path": ".GIT/config", "content": "pass"},
            {"path": "src/.git/config", "content": "pass"},
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
async def test_engine_bounds_repository_source_context_before_model_calls():
    class CapturingRunner(FakeAgentRunner):
        def __init__(self):
            super().__init__()
            self.first_evidence = None

        async def run(self, role_key, user_request, evidence):
            if self.first_evidence is None:
                self.first_evidence = evidence
            return await super().run(role_key, user_request, evidence)

    class LargeRepositoryTools(FakeTools):
        async def inspect_repository(self, repository):
            return {
                "repository": repository,
                "default_branch": "main",
                "base_commit": "abc123",
                "files": [{"path": f"src/module_{i}.py", "size": 9000} for i in range(80)],
                "source_contents": {
                    **{"README.md": "readme evidence " * 1000},
                    **{f"src/module_{i}.py": f"source evidence {i} " * 1000 for i in range(80)},
                    "docs/BRAIN_RUNTIME_VERIFICATION.md": "target file context",
                },
                "source_manifest": {
                    "candidate_count": 81,
                    "read_count": 81,
                    "coverage_complete": True,
                    "failed_paths": {},
                    "omitted_by_aggregate_budget": [],
                    "aggregate_bytes_read": 900000,
                },
            }

    runner = CapturingRunner()
    engine = CompanyWorkflowEngine(runner, LargeRepositoryTools())
    await engine.run(
        "Create docs/BRAIN_RUNTIME_VERIFICATION.md with verified runtime evidence",
        "owner/repository",
    )
    snapshot = runner.first_evidence["repository_snapshot"]
    assert len(snapshot["source_contents"]) <= 20
    assert sum(map(len, snapshot["source_contents"].values())) <= 41_000
    assert "docs/BRAIN_RUNTIME_VERIFICATION.md" in snapshot["source_contents"]
    assert len(snapshot["files"]) <= 300
    assert snapshot["source_manifest"]["model_context_char_limit"] == 40_000
    assert len(snapshot["source_manifest"]["model_context_omitted_or_truncated_paths"]) > 0



@pytest.mark.asyncio
async def test_engine_checkpoints_prior_agent_outputs_before_later_stage_failure():
    checkpoints = []
    engine = CompanyWorkflowEngine(
        FakeAgentRunner(),
        FakeTools(test_status="FAIL"),
        checkpoint_callback=checkpoints.append,
    )

    with pytest.raises(CompanyWorkflowBlocked, match="checks failed"):
        await engine.run("Build a small feature", "owner/repository")

    assert checkpoints
    checkpoint = checkpoints[-1]
    assert checkpoint["stage"] == "test_execution_completed"
    assert checkpoint["test_evidence"]["status"] == "FAIL"
    assert {"product_owner", "ux_designer", "architect", "developer", "code_reviewer"} <= set(
        checkpoint["role_outputs"]
    )


@pytest.mark.asyncio
async def test_engine_final_checkpoint_records_all_roles_and_human_approval_gate():
    checkpoints = []
    engine = CompanyWorkflowEngine(
        FakeAgentRunner(),
        FakeTools(),
        checkpoint_callback=checkpoints.append,
    )

    result = await engine.run("Build a small feature", "owner/repository")

    assert result["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert checkpoints[-1]["stage"] == "human_review_handoff_created"
    assert checkpoints[-1]["status"] == "READY_FOR_HUMAN_APPROVAL"
    assert len(checkpoints[-1]["completed_roles"]) == 9



def test_repository_compactor_never_passes_truncated_files_as_complete_source():
    large_path = "brain/large_module.py"
    complete_large_source = "line of source\n" * 500
    small_path = "README.md"
    small_source = "# Brain\n"

    snapshot = {
        "repository": "owner/repository",
        "default_branch": "main",
        "base_commit": "abc123",
        "files": [
            {"path": large_path, "size": len(complete_large_source)},
            {"path": small_path, "size": len(small_source)},
        ],
        "source_contents": {
            large_path: complete_large_source,
            small_path: small_source,
        },
        "source_manifest": {
            "candidate_count": 2,
            "read_count": 2,
            "coverage_complete": True,
            "failed_paths": {},
        },
    }

    compacted = _compact_repository_snapshot(
        snapshot,
        f"Update {large_path}",
        max_chars=1000,
        max_files=10,
    )

    assert compacted["source_contents"] == {small_path: small_source}
    assert large_path in compacted["source_manifest"]["model_context_omitted_paths"]
    assert "model_context_omitted_or_truncated_paths" not in compacted["source_manifest"]
