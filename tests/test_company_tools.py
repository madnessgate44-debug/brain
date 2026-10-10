"""Tests for safe credential separation in company workflow tools."""

import asyncio

import pytest

from brain.company.tools import GitHubCompanyTools


class FakeGateway:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def _validate_repository(self, repository):
        if repository != "owner/brain":
            raise RuntimeError("repository owner is not allowed")
        return ("owner", "brain")

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path.endswith("/issues"):
            return {"number": 42, "html_url": "https://github.com/owner/brain/issues/42"}
        if method == "GET" and path.endswith("/issues/42/comments"):
            return [{
                "user": {"login": "github-actions[bot]"},
                "body": (
                    "## Brain remote test run\n\n"
                    "**Target repository:** owner/brain\n"
                    "**Target branch:** brain/test-branch\n"
                    "**Result:** PASS\n"
                    "**Exit code:** 0\n"
                    "**Workflow job:** success\n"
                    "Workflow run: https://github.com/owner/brain/actions/runs/123"
                )
            }]
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
    assert [call[0] for call in trigger_gateway.calls] == ["POST", "GET"]


@pytest.mark.asyncio
async def test_verification_ignores_forged_or_mismatched_result_comments():
    class ForgedThenTrustedGateway(FakeGateway):
        async def _request(self, method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            if method == "POST" and path.endswith("/issues"):
                return {"number": 42, "html_url": "https://github.com/owner/brain/issues/42"}
            if method == "GET" and path.endswith("/issues/42/comments"):
                def report(user, target):
                    return {
                        "user": {"login": user},
                        "body": "\n".join([
                            "## Brain remote test run",
                            f"**Target repository:** {target}",
                            "**Target branch:** brain/test-branch",
                            "**Result:** PASS",
                            "**Exit code:** 0",
                            "**Workflow job:** success",
                            "Workflow run: https://github.com/owner/brain/actions/runs/123",
                        ]),
                    }
                return [
                    report("untrusted-user", "owner/brain"),
                    report("github-actions[bot]", "owner/other-repo"),
                    report("github-actions[bot]", "owner/brain"),
                ]
            raise AssertionError(f"Unexpected request: {method} {path}")

    gateway = ForgedThenTrustedGateway("pat")
    tools = GitHubCompanyTools(
        gateway=gateway,
        verification_gateway=gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/brain", "brain/test-branch")

    assert result["status"] == "PASS"
    assert result["run_url"] == "https://github.com/owner/brain/actions/runs/123"


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
        + [
            "package.json", "README.md", "brain-app.html", "brain-ui-mobile.html",
            "alembic/versions/001_initial_schema.py", "docs/operations.md",
            "scripts/deploy.sh", "src/db/schema.sql", "src/UPPER.PY",
            ".gitignore", "Dockerfile.prod", "uv.lock",
            ".github/workflows/ci.yml", "render.yaml",
            "dist/bundle.js", "node_modules/pkg/index.js",
        ]
    )
    gateway = FakeInspectionGateway(paths)
    tools = GitHubCompanyTools(gateway=gateway)

    snapshot = await tools.inspect_repository("owner/amina")

    expected = [
        path for path in paths
        if path.startswith(("src/", "alembic/", "docs/", "scripts/", ".github/workflows/"))
        or path in {
            "package.json", "README.md", "brain-app.html",
            "brain-ui-mobile.html", "render.yaml", ".gitignore",
            "Dockerfile.prod", "uv.lock",
        }
    ]
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

@pytest.mark.asyncio
async def test_verification_runner_bootstrap_error_is_reported_as_terminal_failure():
    class ExecutionErrorGateway(FakeGateway):
        async def _request(self, method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            if method == "POST" and path.endswith("/issues"):
                return {"number": 43, "html_url": "https://github.com/owner/brain/issues/43"}
            if method == "GET" and path.endswith("/issues/43/comments"):
                return [{
                    "user": {"login": "github-actions[bot]"},
                    "body": (
                        "## Brain remote test run\n\n"
                        "**Target repository:** owner/brain\n"
                        "**Target branch:** brain/test-branch\n"
                        "**Result:** EXECUTION_ERROR\n"
                        "Workflow run: https://github.com/owner/brain/actions/runs/124"
                    )
                }]
            raise AssertionError(f"Unexpected request: {method} {path}")

    trigger_gateway = ExecutionErrorGateway("pat")
    tools = GitHubCompanyTools(
        gateway=FakeGateway("actions-token"),
        verification_gateway=trigger_gateway,
        control_repository="owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    result = await tools.run_checks("owner/brain", "brain/test-branch")

    assert result["executed"] is True
    assert result["status"] == "FAIL"
    assert result["reported_result"] == "EXECUTION_ERROR"
    assert result["run_url"] == "https://github.com/owner/brain/actions/runs/124"



def test_company_tools_defaults_control_repository_from_owner(monkeypatch):
    monkeypatch.setenv("BRAIN_CONTROL_REPOSITORY", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    monkeypatch.setenv("BRAIN_GITHUB_OWNER", "example-owner")

    tools = GitHubCompanyTools(gateway=object())

    assert tools.control_repository == "example-owner/brain"



@pytest.mark.asyncio
async def test_verification_issue_respects_control_repository_owner_allowlist():
    trigger_gateway = FakeGateway("pat")
    tools = GitHubCompanyTools(
        gateway=FakeGateway("write"),
        verification_gateway=trigger_gateway,
        control_repository="other-owner/brain",
        poll_seconds=0,
        timeout_seconds=1,
    )

    with pytest.raises(RuntimeError, match="repository owner is not allowed"):
        await tools.run_checks("owner/brain", "brain/test-branch")

    assert trigger_gateway.calls == []
