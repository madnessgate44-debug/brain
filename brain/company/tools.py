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
            ".py", ".pyi", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
            ".vue", ".svelte", ".html", ".css", ".scss", ".sass", ".less",
            ".json", ".jsonc", ".md", ".mdx", ".yml", ".yaml", ".toml",
            ".sh", ".bash", ".zsh", ".ps1", ".sql", ".xml", ".ini", ".cfg",
            ".go", ".rs", ".java", ".kt", ".kts", ".swift", ".rb", ".php",
            ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".dart", ".ex", ".exs",
            ".erl", ".hs", ".pl", ".r", ".scala", ".gradle",
        )
        root_files = {
            "README.md", "package.json", "pyproject.toml", "index.html",
            "vite.config.ts", "vite.config.js", "tsconfig.json", "server.ts",
            "server.js", "next.config.js", "next.config.ts", "pytest.ini",
            "vitest.config.ts", "jest.config.js", "playwright.config.ts",
            ".env.example", "alembic.ini", "Dockerfile", "render.yaml",
            "Procfile", "requirements.txt", "runtime.txt", "Makefile",
        }
        excluded_parts = {
            "node_modules", "dist", "build", "coverage", ".git", "generated",
            "vendor", ".next", ".turbo",
        }
        candidates = []
        for item in snapshot["files"]:
            path = item["path"]
            parts = {part.casefold() for part in path.split("/")}
            in_scope_tree = path.startswith((
                "src/", "brain/", "tests/", "test/", "scripts/",
                ".github/workflows/", "alembic/", "docs/",
            ))
            test_tree = any(part in {"tests", "test", "__tests__"} for part in parts)
            is_source = path.endswith(source_suffixes) and (
                in_scope_tree or "/" not in path
            )
            is_root_config = (
                path in root_files
                or path.startswith(".github/workflows/")
                or path.startswith(".github/dependabot.")
            )
            if parts.intersection(excluded_parts):
                continue
            if is_source or is_root_config or test_tree:
                candidates.append(path)

        candidates = list(dict.fromkeys(candidates))
        contents: dict[str, str] = {}
        errors: dict[str, str] = {}
        total_bytes = 0
        aggregate_limit = 2_200_000
        omitted_by_budget: list[str] = []
        read_concurrency = 8

        async def read_candidate(path: str, remaining_bytes: int) -> tuple[str, str | None, str | None]:
            try:
                value = await self.gateway.read_file(
                    repository, path, max_bytes=min(200_000, remaining_bytes)
                )
                return path, value, None
            except GitHubGatewayError as exc:
                return path, None, str(exc)

        stop_reading = False
        for batch_start in range(0, len(candidates), read_concurrency):
            if total_bytes >= aggregate_limit:
                omitted_by_budget.extend(candidates[batch_start:])
                break
            batch = candidates[batch_start:batch_start + read_concurrency]
            remaining_bytes = aggregate_limit - total_bytes
            results = await asyncio.gather(
                *(read_candidate(path, remaining_bytes) for path in batch)
            )
            for offset, (path, text, error) in enumerate(results):
                if total_bytes >= aggregate_limit:
                    omitted_by_budget.extend(candidates[batch_start + offset:])
                    stop_reading = True
                    break
                if error is not None:
                    errors[path] = error
                    continue
                if text is None:
                    errors[path] = "GitHub returned no text content."
                    continue
                size = len(text.encode("utf-8"))
                if total_bytes + size > aggregate_limit:
                    omitted_by_budget.extend(candidates[batch_start + offset:])
                    stop_reading = True
                    break
                contents[path] = text
                total_bytes += size
            if stop_reading:
                break

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
        self,
        change_set: dict[str, Any],
        repository: str,
        expected_base_sha: str | None = None,
    ) -> dict[str, Any]:
        """Create a branch only if the inspected base commit is still current."""
        summary = change_set.get("summary", "Implement approved software requirements")
        if not isinstance(summary, str):
            summary = "Implement approved software requirements"
        branch = f"brain/mission-{uuid.uuid4().hex[:12]}"
        result = await self.gateway.apply_change_set(
            repository=repository,
            change_set=change_set,
            branch_name=branch,
            commit_message=f"Brain: {summary[:140]}",
            expected_base_sha=expected_base_sha,
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
                # Issues are public in many deployments: never accept a result that
                # an arbitrary commenter can forge before the Actions report arrives.
                if (comment.get("user") or {}).get("login") != "github-actions[bot]":
                    continue
                if "## Brain remote test run" not in body:
                    continue

                def report_field(label: str) -> str | None:
                    prefix = f"**{label}:**"
                    for line in body.splitlines():
                        if line.startswith(prefix):
                            return line[len(prefix):].strip()
                    return None

                if report_field("Target repository") != repository:
                    continue
                if report_field("Target branch") != branch:
                    continue
                reported_result = report_field("Result")
                if reported_result not in {"PASS", "FAIL", "EXECUTION_ERROR"}:
                    continue
                run_prefix = f"https://github.com/{owner}/{name}/actions/runs/"
                run_url = next(
                    (
                        part for part in body.split()
                        if part.startswith(run_prefix)
                        and part[len(run_prefix):].isdigit()
                    ),
                    None,
                )
                if not run_url:
                    continue
                if reported_result == "PASS" and (
                    report_field("Exit code") != "0"
                    or report_field("Workflow job") != "success"
                ):
                    continue
                return {
                    "executed": True,
                    "status": "PASS" if reported_result == "PASS" else "FAIL",
                    "reported_result": reported_result,
                    "run_url": run_url,
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
