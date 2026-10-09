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
    ):
        self.gateway = gateway or GitHubRepositoryGateway()
        self.control_repository = (
            control_repository or get_setting("BRAIN_CONTROL_REPOSITORY")
        )
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._active_branches: dict[str, str] = {}

    async def inspect_repository(self, repository: str) -> dict[str, Any]:
        """Collect a bounded source snapshot so design and engineering use real files."""
        snapshot = await self.gateway.inspect_repository(repository, max_files=100)
        candidates = [
            item["path"] for item in snapshot["files"]
            if item["path"] in {
                "README.md", "package.json", "pyproject.toml", "index.html",
                "vite.config.ts", "tsconfig.json", "src/App.tsx", "src/App.jsx",
                "src/main.tsx", "src/main.jsx", "brain/api/app.py",
            }
            or (
                item["path"].startswith(("src/", "brain/"))
                and item["path"].endswith((".tsx", ".ts", ".jsx", ".js", ".py", ".css"))
                and not any(part in item["path"].lower() for part in ("test", "lock", "generated"))
            )
        ]
        contents = {}
        total_bytes = 0
        for path in candidates[:30]:
            try:
                text = await self.gateway.read_file(repository, path, max_bytes=30_000)
            except GitHubGatewayError:
                continue
            size = len(text.encode("utf-8"))
            if total_bytes + size > 220_000:
                break
            contents[path] = text
            total_bytes += size
        snapshot["source_contents"] = contents
        snapshot["source_files_read"] = len(contents)
        return snapshot

    async def apply_change_set(
        self, change_set: dict[str, Any], repository: str
    ) -> dict[str, Any]:
        """Create one feature branch, then extend it for any bounded repair cycles."""
        summary = change_set.get("summary", "Implement approved software requirements")
        if not isinstance(summary, str):
            summary = "Implement approved software requirements"
        branch = self._active_branches.get(repository)
        update_branch = branch is not None
        if branch is None:
            branch = f"brain/mission-{uuid.uuid4().hex[:12]}"
        result = await self.gateway.apply_change_set(
            repository=repository,
            change_set=change_set,
            branch_name=branch,
            commit_message=f"Brain: {summary[:140]}",
            update_branch=update_branch,
        )
        self._active_branches[repository] = branch
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
        issue = await self.gateway._request(
            "POST",
            f"/repos/{owner}/{name}/issues",
            json={
                "title": f"Brain verification {uuid.uuid4().hex[:8]}",
                "body": (
                    "/brain test\n\n"
                    f"repository: {repository}\n"
                    f"branch: {branch}\n\n"
                    "Automated company-workflow verification. Do not run arbitrary commands."
                ),
            },
        )
        issue_number = issue["number"]
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            comments = await self.gateway._request(
                "GET",
                f"/repos/{owner}/{name}/issues/{issue_number}/comments",
                params={"per_page": 100},
            )
            for comment in comments:
                body = comment.get("body", "")
                if "## Brain remote test run" not in body:
                    continue
                result_match = re.search(
                    r"\*\*Result:\*\*\s*(PASS|FAIL|EXECUTION_ERROR)", body
                )
                run_match = re.search(r"https://github\.com/[^\s]+/actions/runs/\d+", body)
                if not result_match:
                    continue
                result = result_match.group(1)
                return {
                    "executed": result in {"PASS", "FAIL"},
                    "status": "FAIL" if result == "EXECUTION_ERROR" else result,
                    "execution_error": result == "EXECUTION_ERROR",
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
        return await self.gateway.create_pull_request(
            repository=repository,
            branch=branch,
            title=f"Brain: {workflow_result.get('summary', 'Reviewed implementation')}"[:240],
            body=body,
        )
