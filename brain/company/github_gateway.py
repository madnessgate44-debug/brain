"""GitHub repository operations for the company workflow.

All mutations happen on a dedicated branch. No method writes to the default branch,
merges a pull request, deploys, or executes arbitrary issue-supplied commands.
"""

import base64
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from brain.company.settings import get_setting


class GitHubGatewayError(RuntimeError):
    """Raised when a repository operation fails or violates safety policy."""


class GitHubRepositoryGateway:
    """Least-surprise GitHub REST client for bounded repository changes."""

    def __init__(
        self,
        token: str | None = None,
        allowed_owner: str | None = None,
        api_base_url: str = "https://api.github.com",
        client: httpx.AsyncClient | None = None,
    ):
        self.token = token or get_setting("BRAIN_GITHUB_TOKEN")
        self.allowed_owner = (allowed_owner or get_setting("BRAIN_GITHUB_OWNER")).casefold()
        self.api_base_url = api_base_url.rstrip("/")
        self._client = client

    def _validate_repository(self, repository: str) -> tuple[str, str]:
        if not self.token:
            raise GitHubGatewayError("BRAIN_GITHUB_TOKEN is not configured.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
            raise GitHubGatewayError("Repository must use owner/repository format.")
        if not self.allowed_owner:
            raise GitHubGatewayError(
                "BRAIN_GITHUB_OWNER is not configured; repository writes are disabled."
            )
        owner, name = repository.split("/", 1)
        if owner.casefold() != self.allowed_owner:
            raise GitHubGatewayError("Repository owner is not in the configured allowlist.")
        return owner, name

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.request(
                method,
                f"{self.api_base_url}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                **kwargs,
            )
            if response.status_code >= 400:
                detail = response.text[:1200]
                raise GitHubGatewayError(
                    f"GitHub API {method} {path} returned {response.status_code}: {detail}"
                )
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()
        finally:
            if own_client:
                await client.aclose()

    async def inspect_repository(self, repository: str, max_files: int = 80) -> dict[str, Any]:
        """Return a bounded repository snapshot for planning and review."""
        owner, name = self._validate_repository(repository)
        base = f"/repos/{quote(owner)}/{quote(name)}"
        metadata = await self._request("GET", base)
        branch = metadata.get("default_branch")
        if not branch:
            raise GitHubGatewayError("Repository has no default branch.")
        ref = await self._request("GET", f"{base}/git/ref/heads/{quote(branch, safe='')}")
        commit_sha = ref["object"]["sha"]
        commit = await self._request("GET", f"{base}/git/commits/{commit_sha}")
        tree_sha = commit["tree"]["sha"]
        tree = await self._request("GET", f"{base}/git/trees/{tree_sha}", params={"recursive": "1"})
        files = [
            {"path": item["path"], "sha": item.get("sha"), "size": item.get("size", 0)}
            for item in tree.get("tree", [])
            if item.get("type") == "blob"
        ][:max_files]
        return {
            "repository": repository,
            "default_branch": branch,
            "base_commit": commit_sha,
            "files": files,
            "truncated": bool(tree.get("truncated")) or len(files) >= max_files,
        }

    async def read_file(self, repository: str, path: str, max_bytes: int = 200_000) -> str:
        """Read one text file while enforcing path and size limits."""
        owner, name = self._validate_repository(repository)
        self._validate_path(path)
        encoded_path = quote(path, safe="/")
        data = await self._request(
            "GET", f"/repos/{quote(owner)}/{quote(name)}/contents/{encoded_path}"
        )
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise GitHubGatewayError(f"{path} is not a supported text file.")
        raw = base64.b64decode(data["content"])
        if len(raw) > max_bytes:
            raise GitHubGatewayError(f"{path} exceeds the {max_bytes}-byte read limit.")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitHubGatewayError(f"{path} is not UTF-8 text.") from exc

    @staticmethod
    def _validate_path(path: str) -> None:
        if (
            not path
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or path.startswith(".git/")
        ):
            raise GitHubGatewayError(f"Unsafe repository path: {path!r}")

    async def apply_change_set(
        self,
        repository: str,
        change_set: dict[str, Any],
        branch_name: str,
        commit_message: str,
    ) -> dict[str, Any]:
        """Commit a bounded file change set on a new branch; never update default branch."""
        owner, name = self._validate_repository(repository)
        files = change_set.get("files")
        if not isinstance(files, list) or not files or len(files) > 30:
            raise GitHubGatewayError("Change set must contain 1 to 30 files.")
        if not re.fullmatch(r"brain/[a-zA-Z0-9._/-]{1,90}", branch_name):
            raise GitHubGatewayError("Branch name must use the brain/ prefix and safe characters.")
        if not commit_message.strip() or len(commit_message) > 180:
            raise GitHubGatewayError("Commit message must be 1–180 characters.")

        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise GitHubGatewayError("Each change must contain a path and text content.")
            self._validate_path(item["path"])
            if not isinstance(item.get("content"), str):
                raise GitHubGatewayError("Binary or missing file content is not supported.")
            if len(item["content"].encode("utf-8")) > 200_000:
                raise GitHubGatewayError(f"{item['path']} exceeds the 200 KB per-file limit.")

        base = f"/repos/{quote(owner)}/{quote(name)}"
        repo = await self._request("GET", base)
        default_branch = repo.get("default_branch")
        if not default_branch:
            raise GitHubGatewayError("Repository has no default branch.")
        base_ref = await self._request(
            "GET", f"{base}/git/ref/heads/{quote(default_branch, safe='')}"
        )
        base_sha = base_ref["object"]["sha"]
        base_commit = await self._request("GET", f"{base}/git/commits/{base_sha}")
        base_tree_sha = base_commit["tree"]["sha"]

        try:
            await self._request(
                "GET", f"{base}/git/ref/heads/{quote(branch_name, safe='')}"
            )
        except GitHubGatewayError as exc:
            if "returned 404" not in str(exc):
                raise
        else:
            raise GitHubGatewayError(f"Branch {branch_name} already exists.")

        tree_entries = []
        for item in files:
            blob = await self._request(
                "POST",
                f"{base}/git/blobs",
                json={
                    "content": base64.b64encode(item["content"].encode("utf-8")).decode("ascii"),
                    "encoding": "base64",
                },
            )
            tree_entries.append({
                "path": item["path"],
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            })
        tree = await self._request(
            "POST", f"{base}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_entries},
        )
        commit = await self._request(
            "POST", f"{base}/git/commits",
            json={
                "message": commit_message,
                "tree": tree["sha"],
                "parents": [base_sha],
            },
        )
        await self._request(
            "POST", f"{base}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": commit["sha"]},
        )
        comparison = await self._request(
            "GET",
            f"{base}/compare/{quote(base_sha, safe='')}...{quote(branch_name, safe='/')}",
        )
        diff_parts = []
        for changed in comparison.get("files", []):
            diff_parts.append(f"FILE: {changed.get('filename', 'unknown')}")
            diff_parts.append(changed.get("patch") or "[Patch omitted by GitHub; inspect file content.]")
        actual_diff = "\n".join(diff_parts)
        return {
            "repository": repository,
            "branch": branch_name,
            "base_branch": default_branch,
            "base_sha": base_sha,
            "commit_sha": commit["sha"],
            "changed_files": [item["path"] for item in files],
            "diff": actual_diff,
        }

    async def create_pull_request(
        self,
        repository: str,
        branch: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """Open a pull request for human review; never merge it."""
        owner, name = self._validate_repository(repository)
        if not branch.startswith("brain/"):
            raise GitHubGatewayError("Only Brain-created branches can be proposed.")
        base = f"/repos/{quote(owner)}/{quote(name)}"
        repo = await self._request("GET", base)
        result = await self._request(
            "POST",
            f"{base}/pulls",
            json={
                "title": title[:240],
                "body": body,
                "head": branch,
                "base": repo["default_branch"],
                "draft": False,
            },
        )
        return {
            "number": result["number"],
            "url": result["html_url"],
            "state": result["state"],
            "merged": result.get("merged", False),
        }
