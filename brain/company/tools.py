"""Concrete company workflow tools backed by GitHub and GitHub Actions."""

import asyncio
import os
import re
import uuid
from typing import Any

from brain.company.github_gateway import GitHubGatewayError, GitHubRepositoryGateway
from brain.company.settings import get_setting


class GitHubCompanyTools:
    """Implement branch changes, remote checks, and human-review PR creation."""

    def __init__(
        self,
        gateway: GitHubRepositoryGateway | None = None,
        control_repository: str | None = None,
        poll_seconds: float = 5.0,
        timeout_seconds: float = 900.0,
        verification_gateway: GitHubRepositoryGateway | None = None,
        pull_request_gateway: GitHubRepositoryGateway | None = None,
    ):
        self.gateway = gateway or GitHubRepositoryGateway()
        self.verification_gateway = verification_gateway or self.gateway
        self.pull_request_gateway = pull_request_gateway or self.gateway
        self.control_repository = (
            control_repository or get_setting("BRAIN_CONTROL_REPOSITORY")
        )
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds

    async def inspect_repository(self, repository: str) -> dict[str, Any]:
        """Build a multi-pass source inventory; disclose every candidate not read."""
        snapshot = await self.gateway.inspect_repository(repository, max_files=1000)
        source_suffixes = (
            ".tsx", ".ts", ".jsx", ".js", ".py", ".css", ".html", ".json",
            ".md", ".yml", ".yaml", ".toml",
        )
        root_files = {
            "README.md", "package.json", "pyproject.toml", "index.html",
            "vite.config.ts", "vite.config.js", "tsconfig.json", "server.ts",
            "server.js", "next.config.js", "next.config.ts", "pytest.ini",
            "vitest.config.ts", "jest.config.js", "playwright.config.ts",
        }
        excluded_parts = {
            "node_modules", "dist", "build", "coverage", ".git", "generated",
            "vendor", ".next", ".turbo",
        }
        candidates = []
        for item in snapshot["files"]:
            path = item["path"]
            parts = {part.casefold() for part in path.split("/")}
            in_scope_tree = path.startswith(("src/", "brain/", "tests/", "test/", "scripts/", ".github/workflows/"))
            test_tree = any(part in {"tests", "test", "__tests__"} for part in parts)
            is_source = path.endswith(source_suffixes) and in_scope_tree
            is_root_config = path in root_files or path.startswith(".github/workflows/")
            if parts.intersection(excluded_parts):
                continue
            if is_source or is_root_config or test_tree:
                candidates.append(path)

        candidates = list(dict.fromkeys(candidates))
        contents: dict[str, str] = {}
        errors: dict[str, str] = {}
        total_bytes = 0
        aggregate_limit = 1_500_000
        omitted_by_budget: list[str] = []
        for index, path in enumerate(candidates):
            if total_bytes >= aggregate_limit:
                omitted_by_budget.extend(candidates[index:])
                break
            try:
                text = await self.gateway.read_file(
                    repository, path, max_bytes=min(30_000, aggregate_limit - total_bytes)
                )
            except GitHubGatewayError as exc:
                errors[path] = str(exc)
                continue
            size = len(text.encode("utf-8"))
            if total_bytes + size > aggregate_limit:
                omitted_by_budget.append(path)
                omitted_by_budget.extend(candidates[index + 1:])
                break
            contents[path] = text
            total_bytes += size

        snapshot["source_contents"] = contents
        snapshot["source_files_read"] = len(contents)
        snapshot["source_manifest"] = {
            "candidate_count": len(candidates),
            "read_count": len(contents),
            "failed_paths": errors,
            "omitted_by_aggregate_budget": omitted_by_budget,
            "candidate_paths": candidates,
            "read_paths": list(contents),
            "tree_file_count_returned": len(snapshot.get("files", [])),
            "tree_truncated": bool(snapshot.get("truncated")),
            "aggregate_bytes_read": total_bytes,
            "aggregate_byte_limit": aggregate_limit,
            "coverage_complete": (
                not errors and not omitted_by_budget and not snapshot.get("truncated")
            ),
        }
        return snapshot

    async def apply_change_set(
        self, change_set: dict[str, Any], repository: str
    ) -> dict[str, Any]:
        """Create a unique branch and commit the model-proposed file changes."""
        summary = change_set.get("summary", "Implement approved software requirements")
        if not isinstance(summary, str):
            summary = "Implement approved software requirements"
        branch = f"brain/mission-{uuid.uuid4().hex[:12]}"
        result = await self.gateway.apply_change_set(
            repository=repository,
            change_set=change_set,
            branch_name=branch,
            commit_message=f"Brain: {summary[:140]}",
        )
        return result

    async def run_checks(self, repository: str, branch: str) -> dict[str, Any]:
        """Trigger the fixed Brain Actions runner and wait for its recorded result."""
        if not self.control_repository or "/" not in self.control_repository:
            raise GitHubGatewayError(
                "BRAIN_CONTROL_REPOSITORY must identify the repository hosting Brain's task runner."
            )
        if not branch.startswith("brain/"):
            raise GitHubGatewayError("Checks are allowed only for Brain-created branches.")

        owner, name = self.control_repository.split("/", 1)
        # The verification issue must be created with a PAT, not GITHUB_TOKEN:
        # GitHub suppresses follow-on workflow runs for events caused by GITHUB_TOKEN.
        trigger_gateway = self.verification_gateway
        issue = await trigger_gateway._request(
            "POST",
            f"/repos/{owner}/{name}/issues",
            json={
                "title": f"Brain verification {uuid.uuid4().hex[:8]}",
                "body": (
                    "/brain test\n\n"
                    f"repository: {repository}\n"
                    f"branch: {branch}\n\n"
                    "brain-internal-verification: true\n"
                    "Automated company-workflow verification. Do not run arbitrary commands."
                ),
            },
        )
        issue_number = issue["number"]
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            comments = await trigger_gateway._request(
                "GET",
                f"/repos/{owner}/{name}/issues/{issue_number}/comments",
                params={"per_page": 100},
            )
            for comment in comments:
                body = comment.get("body", "")
                if "## Brain remote test run" not in body:
                    continue
                result_match = re.search(r"\*\*Result:\*\*\s*(PASS|FAIL)", body)
                run_match = re.search(r"https://github\.com/[^\s]+/actions/runs/\d+", body)
                if not result_match:
                    continue
                result = result_match.group(1)
                return {
                    "executed": True,
                    "status": result,
                    "run_url": run_match.group(0) if run_match else None,
                    "issue_url": issue.get("html_url"),
                    "report": body,
                    "branch": branch,
                    "repository": repository,
                }
            await asyncio.sleep(self.poll_seconds)
        raise TimeoutError(
            f"Timed out waiting for GitHub Actions verification for issue #{issue_number}."
        )

    async def open_pull_request(
        self, repository: str, branch: str, workflow_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a PR for human review after every workflow gate has passed."""
        changed_files = workflow_result.get("changed_files", [])
        test_url = workflow_result.get("test_evidence", {}).get("run_url")
        body = "\n".join([
            "## Brain software-company workflow",
            "",
            "This pull request was prepared by Brain's gated specialist workflow.",
            "",
            "### Verification",
            f"- Repository checks: {test_url or 'Result recorded; URL unavailable'}",
            f"- Changed files: {', '.join(changed_files) or 'See diff'}",
            "- Product/UX, architecture, independent review, QA, security, and customer gates passed.",
            "- Human review is required. Brain has not merged or deployed this change.",
        ])
        return await self.pull_request_gateway.create_pull_request(
            repository=repository,
            branch=branch,
            title=f"Brain: {workflow_result.get('summary', 'Reviewed implementation')}"[:240],
            body=body,
        )
