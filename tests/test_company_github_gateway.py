"""Safety tests for the GitHub repository gateway."""

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
async def test_gateway_repair_extends_existing_branch_and_returns_full_diff():
    import json

    import httpx

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(), request.content))
        path = request.url.raw_path.decode()
        if request.method == "GET" and path.endswith("/repos/example-owner/project"):
            return httpx.Response(200, json={"default_branch": "main"})
        if request.method == "GET" and path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "default-sha"}})
        if request.method == "GET" and "git/ref/heads/brain%2Frepair" in path:
            return httpx.Response(200, json={"object": {"sha": "existing-branch-sha"}})
        if request.method == "GET" and path.endswith("/git/commits/existing-branch-sha"):
            return httpx.Response(200, json={"tree": {"sha": "existing-tree-sha"}})
        if request.method == "POST" and path.endswith("/git/blobs"):
            return httpx.Response(201, json={"sha": "new-blob-sha"})
        if request.method == "POST" and path.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "new-tree-sha"})
        if request.method == "POST" and path.endswith("/git/commits"):
            payload = json.loads(request.content)
            assert payload["parents"] == ["existing-branch-sha"]
            return httpx.Response(201, json={"sha": "new-commit-sha"})
        if request.method == "PATCH" and "git/refs/heads/brain%2Frepair" in path:
            return httpx.Response(200, json={"ref": "refs/heads/brain/repair"})
        if request.method == "GET" and "/compare/default-sha...brain/repair" in path:
            return httpx.Response(200, json={"files": [
                {"filename": "src/first.py", "patch": "@@ -1 +1 @@"},
                {"filename": "src/second.py", "patch": "@@ -2 +2 @@"},
            ]})
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = GitHubRepositoryGateway(
        token="test-token",
        allowed_owner="example-owner",
        api_base_url="https://example.test",
        client=client,
    )
    try:
        result = await gateway.apply_change_set(
            repository="example-owner/project",
            change_set={"files": [{"path": "src/second.py", "content": "updated"}]},
            branch_name="brain/repair",
            commit_message="repair implementation",
            update_branch=True,
        )
    finally:
        await client.aclose()

    assert result["commit_sha"] == "new-commit-sha"
    assert result["changed_files"] == ["src/first.py", "src/second.py"]
    assert result["diff"].count("FILE: ") == 2
    assert any(method == "PATCH" and "git/refs/heads/brain%2Frepair" in path
               for method, path, _ in requests)
