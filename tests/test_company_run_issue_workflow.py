"""Tests for capability-aware target repository credential resolution."""

import pytest

import brain.company.run_issue_workflow as workflow
from brain.company.github_gateway import GitHubGatewayError
from brain.company.mission_capabilities import plan_capabilities


class FakeGateway:
    def __init__(self, token, allowed_owner):
        self.token = token
        self.allowed_owner = allowed_owner

    async def verify_write_access(self, repository):
        if self.token == "no-write":
            raise GitHubGatewayError("write access denied")
        return {"repository": repository, "write_access": True}

    async def inspect_repository(self, repository, max_files=80):
        if self.token == "no-read":
            raise GitHubGatewayError("read access denied")
        return {"repository": repository, "default_branch": "main"}


@pytest.mark.asyncio
async def test_write_gateway_uses_primary_token_when_it_has_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("fix defects"),
    )

    assert gateway.token == "primary-write"


@pytest.mark.asyncio
async def test_write_gateway_falls_back_to_actions_token_when_primary_lacks_permission(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="no-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("fix defects"),
    )

    assert gateway.token == "actions-write"


@pytest.mark.asyncio
async def test_gateway_reports_detailed_failures_when_no_token_has_required_capability(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured credential satisfied") as error:
        await workflow.build_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="no-write",
            actions_token="no-write",
            capability_plan=plan_capabilities("fix defects"),
        )

    assert "BRAIN_GITHUB_TOKEN" in str(error.value)
    assert "write access denied" in str(error.value)


@pytest.mark.asyncio
async def test_gateway_reports_when_no_credentials_are_configured(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    with pytest.raises(RuntimeError, match="No configured credential satisfied") as error:
        await workflow.build_gateway(
            repository="owner/project",
            owner="owner",
            primary_token="",
            actions_token="",
            capability_plan=plan_capabilities("fix defects"),
        )

    assert "No GitHub credential is configured" in str(error.value)


@pytest.mark.asyncio
async def test_read_only_mission_uses_read_access_without_write_preflight(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/project",
        owner="owner",
        primary_token="read-only-token",
        actions_token="",
        capability_plan=plan_capabilities("Audit and report findings"),
    )

    assert gateway.token == "read-only-token"



@pytest.mark.asyncio
async def test_control_repository_write_prefers_scoped_actions_token(monkeypatch):
    """Use the workflow token for contents writes on its own repository."""
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/brain",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "actions-write"


@pytest.mark.asyncio
async def test_external_repository_write_keeps_primary_token_first(monkeypatch):
    """Do not try the control-repository GITHUB_TOKEN first for another repository."""
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)

    gateway = await workflow.build_gateway(
        repository="owner/other-project",
        owner="owner",
        primary_token="primary-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "primary-write"


@pytest.mark.asyncio
async def test_control_repository_actions_token_uses_read_preflight_then_actual_write(monkeypatch):
    """Do not reject GITHUB_TOKEN solely because repo metadata reports push=false."""
    class ActionsTokenMetadataGateway(FakeGateway):
        async def verify_write_access(self, repository):
            raise GitHubGatewayError("metadata reports push=false")

    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", ActionsTokenMetadataGateway)

    gateway = await workflow.build_gateway(
        repository="owner/brain",
        owner="owner",
        primary_token="no-write",
        actions_token="actions-write",
        capability_plan=plan_capabilities("create file docs/guide.md"),
        control_repository="owner/brain",
    )

    assert gateway.token == "actions-write"



@pytest.mark.parametrize(
    ("repository", "control_repository", "primary_token", "actions_token", "expected_token"),
    [
        ("owner/brain", "owner/brain", "primary-pat", "actions-token", "primary-pat"),
        ("owner/amina", "owner/brain", "primary-pat", "actions-token", "primary-pat"),
        ("owner/brain", "owner/brain", "primary-pat", "", "primary-pat"),
    ],
)
def test_pull_request_gateway_uses_credential_scoped_to_target_repository(
    monkeypatch, repository, control_repository, primary_token, actions_token, expected_token
):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)
    fallback = FakeGateway("fallback", "owner")

    gateway = workflow.build_pull_request_gateway(
        repository=repository,
        owner="owner",
        primary_token=primary_token,
        actions_token=actions_token,
        control_repository=control_repository,
        fallback_gateway=fallback,
    )

    assert gateway.token == expected_token


def test_web_research_is_requested_for_external_research_missions():
    assert workflow.should_collect_public_web_research("Research the latest Playwright browser documentation.")
    assert workflow.should_collect_public_web_research("Compare current hosting prices and persistence limits.")
    assert not workflow.should_collect_public_web_research("Fix the typo in README and run the existing tests.")


@pytest.mark.asyncio
async def test_shared_public_web_evidence_is_bounded_and_logged(monkeypatch):
    class FakeCollector:
        def __init__(self, max_web_pages=8):
            assert max_web_pages == 6

        async def collect_web_research(self, mission):
            return {
                "status": "completed",
                "search_provider": "fake",
                "queries": ["browser docs"],
                "sources": [
                    {
                        "title": "Official docs",
                        "url": "https://docs.example.com/",
                        "query": "browser docs",
                        "status": "fetched",
                        "excerpt": "Evidence " * 300,
                    }
                ],
                "limitations": ["sample only"],
            }

    monkeypatch.setattr(workflow, "ResearchEvidenceCollector", FakeCollector)
    events = []
    result = await workflow.collect_shared_public_web_evidence(
        "Research the latest Playwright browser documentation.", events
    )
    assert result["status"] == "completed"
    assert result["pages_fetched"] == 1
    assert len(result["sources"][0]["excerpt"]) == 1400
    assert events[-1]["stage"] == "public_web_research"
    assert events[-1]["status"] == "PASS"


@pytest.mark.asyncio
async def test_shared_public_web_evidence_is_not_requested_for_ordinary_code_tasks():
    events = []
    result = await workflow.collect_shared_public_web_evidence(
        "Fix the typo in README and run the existing tests.", events
    )
    assert result["status"] == "not_requested"
    assert events == []


def test_pull_request_gateway_uses_fallback_when_no_primary_pat_exists(monkeypatch):
    monkeypatch.setattr(workflow, "GitHubRepositoryGateway", FakeGateway)
    fallback = FakeGateway("fallback-actions", "owner")

    gateway = workflow.build_pull_request_gateway(
        repository="owner/amina",
        owner="owner",
        primary_token="",
        actions_token="actions-token",
        control_repository="owner/brain",
        fallback_gateway=fallback,
    )

    assert gateway is fallback



def test_build_audit_source_chunks_compactly_preserves_paths_and_line_numbers():
    chunks = workflow.build_audit_source_chunks({
        "src/a.ts": "const a = 1;\nconst b = 2;\n",
        "src/b.ts": "export const c = 3;\n",
    }, max_chars=80)

    rendered = "\n".join(chunk["text"] for chunk in chunks)
    assert "FILE: src/a.ts" in rendered
    assert "FILE: src/b.ts" in rendered
    assert "L1: const a = 1;" in rendered
    assert "L2: const b = 2;" in rendered
    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 80 for chunk in chunks)


def test_build_audit_source_chunks_marks_truncated_long_lines():
    chunks = workflow.build_audit_source_chunks(
        {"src/large.ts": "x" * 100},
        max_chars=200,
        max_line_chars=20,
    )

    assert "[LINE TRUNCATED FOR PROMPT SIZE]" in chunks[0]["text"]
