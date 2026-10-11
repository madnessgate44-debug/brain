"""Safety tests for the GitHub repository gateway."""

import json

import httpx
import pytest

from brain.company.github_gateway import GitHubGatewayError, GitHubRepositoryGateway


def test_gateway_requires_configured_owner_allowlist():
    gateway = GitHubRepositoryGateway(
        token="test-token",
        allowed_owner="example-owner",
        api_base_url="https://example.test",
    )
    with pytest.raises(GitHubGatewayError, match="owner is not"):
        gateway._validate_repository("someone-else/project")


@pytest.mark.parametrize("path", ["", "/etc/passwd", "../secret", "src/../secret", ".git/config", r"src\file.py"])
def test_gateway_rejects_unsafe_repository_paths(path):
    with pytest.raises(GitHubGatewayError, match="Unsafe repository path"):
        GitHubRepositoryGateway._validate_path(path)


def test_gateway_rejects_missing_token():
    gateway = GitHubRepositoryGateway(token="", allowed_owner="example-owner")
    with pytest.raises(GitHubGatewayError, match="BRAIN_GITHUB_TOKEN"):
        gateway._validate_repository("example-owner/project")


@pytest.mark.asyncio
async def test_gateway_rejects_unbounded_change_set_before_network_call():
    gateway = GitHubRepositoryGateway(
        token="test-token",
        allowed_owner="example-owner",
        api_base_url="https://example.test",
    )
    with pytest.raises(GitHubGatewayError, match="1 to 30 files"):
        await gateway.apply_change_set(
            repository="example-owner/project",
            change_set={"files": []},
            branch_name="brain/test-change",
            commit_message="test",
        )



@pytest.mark.asyncio
async def test_gateway_write_preflight_rejects_token_without_contents_write():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/repos/example-owner/project"
        return httpx.Response(403, json={"message": "repository access denied"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = GitHubRepositoryGateway(
            token="test-token",
            allowed_owner="example-owner",
            api_base_url="https://example.test",
            client=client,
        )
        with pytest.raises(GitHubGatewayError, match="returned 403"):
            await gateway.verify_write_access("example-owner/project")


@pytest.mark.asyncio
async def test_gateway_write_preflight_reads_advertised_push_permission_without_mutation():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/repos/example-owner/project"
        return httpx.Response(
            200,
            json={"permissions": {"push": True}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = GitHubRepositoryGateway(
            token="test-token",
            allowed_owner="example-owner",
            api_base_url="https://example.test",
            client=client,
        )
        result = await gateway.verify_write_access("example-owner/project")

    assert result == {
        "repository": "example-owner/project",
        "write_access": True,
        "permission_evidence": "confirmed_push",
    }

@pytest.mark.asyncio
async def test_gateway_actual_diff_uses_real_newlines_for_multiple_files(monkeypatch):
    gateway = GitHubRepositoryGateway(
        token="test-token",
        allowed_owner="example-owner",
        api_base_url="https://example.test",
    )

    async def fake_request(method, path, **kwargs):
        if method == "GET" and path == "/repos/example-owner/project":
            return {"default_branch": "main"}
        if path == "/repos/example-owner/project/git/ref/heads/main":
            return {"object": {"sha": "base-sha"}}
        if path == "/repos/example-owner/project/git/commits/base-sha":
            return {"tree": {"sha": "base-tree"}}
        if path == "/repos/example-owner/project/git/ref/heads/brain%2Ftest-change":
            raise GitHubGatewayError("GitHub API GET returned 404: branch missing")
        if path.endswith("/git/blobs"):
            return {"sha": "blob-sha"}
        if path.endswith("/git/trees"):
            return {"sha": "tree-sha"}
        if path.endswith("/git/commits"):
            return {"sha": "commit-sha"}
        if path.endswith("/git/refs"):
            return {}
        if "/compare/" in path:
            return {"files": [
                {"filename": "a.py", "patch": "@@ -1 +1 @@\n-old\n+new"},
                {"filename": "b.py", "patch": "@@ -1 +1 @@\n-before\n+after"},
            ]}
        raise AssertionError(f"Unexpected GitHub request: {method} {path}")

    monkeypatch.setattr(gateway, "_request", fake_request)
    result = await gateway.apply_change_set(
        repository="example-owner/project",
        change_set={"files": [
            {"path": "a.py", "content": "new\n"},
            {"path": "b.py", "content": "after\n"},
        ]},
        branch_name="brain/test-change",
        commit_message="test diff formatting",
    )

    actual_diff = result["diff"]
    assert "FILE: a.py\n" in actual_diff
    assert "\nFILE: b.py\n" in actual_diff
    assert actual_diff.count("\n") >= 5
    assert "\\n" not in actual_diff

@pytest.mark.asyncio
async def test_gateway_creates_company_pull_request_as_draft():
    captured = []

    def handler(request):
        if request.method == "GET" and request.url.path == "/repos/example-owner/project":
            return httpx.Response(200, json={"default_branch": "main"}, request=request)
        if request.method == "POST" and request.url.path == "/repos/example-owner/project/pulls":
            payload = json.loads(request.content)
            captured.append(payload)
            return httpx.Response(
                201,
                json={"number": 42, "html_url": "https://github.com/example-owner/project/pull/42",
                      "state": "open", "merged": False},
                request=request,
            )
        raise AssertionError(f"Unexpected GitHub request: {request.method} {request.url.path}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = GitHubRepositoryGateway(
            token="test-token",
            allowed_owner="example-owner",
            api_base_url="https://example.test",
            client=client,
        )
        result = await gateway.create_pull_request(
            "example-owner/project", "brain/test", "Brain: proposed fix", "Review required"
        )

    assert result["url"].endswith("/pull/42")
    assert captured[0]["draft"] is True
