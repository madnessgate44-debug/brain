"""Tests for safe credential separation in company workflow tools."""

import asyncio

import pytest

from brain.company.tools import GitHubCompanyTools


class FakeGateway:
    def __init__(
        self,
        name,
        run_data=None,
        author_login="github-actions[bot]",
        target_repository="owner/brain",
        target_branch="brain/test-branch",
        reported_result="PASS",
        run_url="https://github.com/owner/brain/actions/runs/123",
    ):
        self.name = name
        self.calls = []
        self.run_data = run_data or {
            "status": "completed",
            "event": "issues",
            "path": ".github/workflows/brain-task-runner.yml",
            "head_repository": {"full_name": "owner/brain"},
            # The run is triggered by an issue in the control repo; this is not
            # the target branch being tested.
            "head_branch": "main",
            "conclusion": "success" if reported_result == "PASS" else "failure",
        }
        self.author_login = author_login
        self.comment_body = (
            "## Brain remote test run\\n\\n"
            f"**Target repository:** {target_repository}\\n"
            f"**Target branch:** {target_branch}\\n"
            f"**Result:** {reported_result}\\n"
            f"Workflow run: {run_url}"
        )

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path.endswith("/issues"):
            return {"number": 42, "html_url": "https://github.com/owner/brain/issues/42"}
        if method == "GET" and path.endswith("/issues/42/comments"):
            return [{
                "user": {"login": self.author_login},
                "body": self.comment_body,
            }]
        if method == "GET" and "/actions/runs/123" in path:
            return self.run_data
        raise AssertionError(f"Unexpected request: {method} {path}")


@pytest.mark.asyncio
async def test_verification_issue_uses_separate_pat_gateway():
    """PAT-created issue events can trigger the test workflow; GITHUB_TOKEN events cannot."""
    write_gateway = FakeGateway("actions-token")
    trigger_gateway = FakeGateway("pat")
    tools = GitHubCompanyTools(
        gateway=write_gateway,
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/brain", "brain/test-branch")

    assert result["executed"] is True
    assert result["status"] == "PASS"
    assert result["run_url"] == "https://github.com/owner/brain/actions/runs/123"
    assert len(write_gateway.calls) == 0
    assert [call[0] for call in trigger_gateway.calls] == ["POST", "GET", "GET"]


@pytest.mark.asyncio
async def test_run_checks_rejects_non_bot_comment():
    trigger_gateway = FakeGateway("pat", author_login="malicious-user")
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_rejects_wrong_target_repository():
    run_data = {
        "status": "completed",
        "event": "issues",
        "path": ".github/workflows/brain-task-runner.yml",
        "head_repository": {"full_name": "owner/other-repo"},
        "head_branch": "brain/test-branch",
        "conclusion": "success",
    }
    trigger_gateway = FakeGateway("pat", run_data=run_data, target_repository="owner/other-repo")
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_rejects_wrong_target_branch():
    run_data = {
        "status": "completed",
        "event": "issues",
        "path": ".github/workflows/brain-task-runner.yml",
        "head_repository": {"full_name": "owner/brain"},
        "head_branch": "brain/wrong-branch",
        "conclusion": "success",
    }
    trigger_gateway = FakeGateway("pat", run_data=run_data, target_branch="brain/wrong-branch")
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_rejects_wrong_workflow():
    run_data = {
        "status": "completed",
        "event": "issues",
        "path": ".github/workflows/wrong-workflow.yml",
        "head_repository": {"full_name": "owner/brain"},
        "head_branch": "brain/test-branch",
        "conclusion": "success",
    }
    trigger_gateway = FakeGateway("pat", run_data=run_data)
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_rejects_inprogress_run():
    run_data = {
        "status": "in_progress",
        "event": "issues",
        "path": ".github/workflows/brain-task-runner.yml",
        "head_repository": {"full_name": "owner/brain"},
        "head_branch": "brain/test-branch",
        "conclusion": None,
    }
    trigger_gateway = FakeGateway("pat", run_data=run_data)
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_rejects_mismatched_conclusion():
    run_data = {
        "status": "completed",
        "event": "issues",
        "path": ".github/workflows/brain-task-runner.yml",
        "head_repository": {"full_name": "owner/brain"},
        "head_branch": "brain/test-branch",
        "conclusion": "failure",
    }
    trigger_gateway = FakeGateway("pat", run_data=run_data)
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=0.1,
    )

    with pytest.raises(TimeoutError):
        await tools.run_checks("owner/brain", "brain/test-branch")


@pytest.mark.asyncio
async def test_run_checks_accepts_verified_failure_as_failure():
    trigger_gateway = FakeGateway("pat", reported_result="FAIL")
    tools = GitHubCompanyTools(
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/brain", "brain/test-branch")

    assert result["executed"] is True
    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_pull_request_uses_separate_pat_gateway():
    """Keep content writes on GITHUB_TOKEN while PR creation uses the configured PAT."""
    write_gateway = FakeGateway("actions-token")

    class FakePullRequestGateway:
        def __init__(self):
            self.calls = []

        async def create_pull_request(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "url": "https://github.com/owner/brain/pull/999",
                "merged": False,
            }

    pull_request_gateway = FakePullRequestGateway()
    tools = GitHubCompanyTools(
        gateway=write_gateway,
        pull_request_gateway=pull_request_gateway,
        control_repository="owner/brain",
    )

    result = await tools.open_pull_request(
        "owner/brain",
        "brain/test-branch",
        {
            "summary": "Document runtime verification",
            "changed_files": ["docs/BRAIN_RUNTIME_VERIFICATION.md"],
            "test_evidence": {"run_url": "https://github.com/owner/brain/actions/runs/123"},
        },
    )

    assert result["url"] == "https://github.com/owner/brain/pull/999"
    assert len(pull_request_gateway.calls) == 1
    assert len(write_gateway.calls) == 0


@pytest.mark.asyncio
async def test_pull_request_title_does_not_stringify_structured_summary():
    write_gateway = FakeGateway("actions-token")

    class FakePullRequestGateway:
        def __init__(self):
            self.calls = []

        async def create_pull_request(self, **kwargs):
            self.calls.append(kwargs)
            return {"url": "https://github.com/owner/brain/pull/1000", "merged": False}

    pull_request_gateway = FakePullRequestGateway()
    tools = GitHubCompanyTools(
        gateway=write_gateway,
        pull_request_gateway=pull_request_gateway,
        control_repository="owner/brain",
    )

    await tools.open_pull_request(
        "owner/brain",
        "brain/test-branch",
        {
            "summary": {"objective": "Repeat the full end-to-end acceptance mission through every specialist."},
            "changed_files": ["docs/BRAIN_RUNTIME_VERIFICATION.md"],
            "test_evidence": {"run_url": "https://github.com/owner/brain/actions/runs/123"},
        },
    )

    title = pull_request_gateway.calls[0]["title"]
    assert title == "Brain: update BRAIN RUNTIME VERIFICATION"
    assert "{'" not in title


class FakeInspectionGateway:
    def __init__(self, paths):
        self.paths = paths
        self.read_paths = []

    async def inspect_repository(self, repository, max_files=80):
        return {
            "repository": repository,
            "default_branch": "main",
            "base_commit": "abc123",
            "files": [{"path": path, "size": 100} for path in self.paths],
            "truncated": False,
        }

    async def read_file(self, repository, path, max_bytes=200_000):
        self.read_paths.append(path)
        return f"// source for {path}\n"


@pytest.mark.asyncio
async def test_inspection_reads_all_in_scope_source_and_test_files_and_reports_coverage():
    paths = (
        [f"src/components/Component{i}.tsx" for i in range(45)]
        + [f"src/services/__tests__/service{i}.test.ts" for i in range(8)]
        + ["package.json", "README.md", "dist/bundle.js", "node_modules/pkg/index.js"]
    )
    gateway = FakeInspectionGateway(paths)
    tools = GitHubCompanyTools(gateway=gateway)

    snapshot = await tools.inspect_repository("owner/amina")

    expected = [path for path in paths if path.startswith("src/") or path in {"package.json", "README.md"}]
    assert set(gateway.read_paths) == set(expected)
    assert snapshot["source_files_read"] == len(expected)
    assert snapshot["source_manifest"]["candidate_count"] == len(expected)
    assert snapshot["source_manifest"]["read_count"] == len(expected)
    assert snapshot["source_manifest"]["coverage_complete"] is True
    assert snapshot["source_manifest"]["omitted_by_aggregate_budget"] == []
    assert snapshot["source_manifest"]["tree_truncated"] is False


@pytest.mark.asyncio
async def test_inspection_marks_aggregate_budget_omissions_instead_of_claiming_complete():
    class LargeInspectionGateway(FakeInspectionGateway):
        async def read_file(self, repository, path, max_bytes=200_000):
            self.read_paths.append(path)
            return "x" * min(max_bytes, 60_000)

    paths = [f"src/file{i}.ts" for i in range(60)]
    gateway = LargeInspectionGateway(paths)
    tools = GitHubCompanyTools(gateway=gateway)

    snapshot = await tools.inspect_repository("owner/amina")

    manifest = snapshot["source_manifest"]
    assert manifest["read_count"] < manifest["candidate_count"]
    assert manifest["omitted_by_aggregate_budget"]
    assert manifest["coverage_complete"] is False



@pytest.mark.asyncio
async def test_inspection_reads_a_single_source_file_larger_than_thirty_kilobytes():
    class LargeFileGateway(FakeInspectionGateway):
        async def read_file(self, repository, path, max_bytes=200_000):
            self.read_paths.append(path)
            return "x" * 50_000

    gateway = LargeFileGateway(["src/services/largeService.ts"])
    tools = GitHubCompanyTools(gateway=gateway)

    snapshot = await tools.inspect_repository("owner/amina")

    assert snapshot["source_files_read"] == 1
    assert len(snapshot["source_contents"]["src/services/largeService.ts"]) == 50_000
    assert snapshot["source_manifest"]["coverage_complete"] is True


@pytest.mark.asyncio
async def test_inspection_reads_source_files_with_bounded_concurrency():
    class ConcurrentInspectionGateway(FakeInspectionGateway):
        def __init__(self, paths):
            super().__init__(paths)
            self.active_reads = 0
            self.max_active_reads = 0

        async def read_file(self, repository, path, max_bytes=200_000):
            self.read_paths.append(path)
            self.active_reads += 1
            self.max_active_reads = max(self.max_active_reads, self.active_reads)
            await asyncio.sleep(0.01)
            self.active_reads -= 1
            return f"// source for {path}\\n"

    paths = [f"brain/module_{index}.py" for index in range(24)]
    gateway = ConcurrentInspectionGateway(paths)
    tools = GitHubCompanyTools(gateway=gateway)

    snapshot = await tools.inspect_repository("owner/brain")

    assert snapshot["source_files_read"] == len(paths)
    assert set(gateway.read_paths) == set(paths)
    assert 1 < gateway.max_active_reads <= 8
