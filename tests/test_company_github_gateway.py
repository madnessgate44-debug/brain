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
