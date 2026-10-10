"""Tests for R&D discovery, metadata scoring, and model-output boundaries."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from brain.research.agent import ResearchAndDevelopmentAgent, render_markdown
from brain.research.discovery import DiscoveryError, GitHubRepositoryDiscovery, heuristic_score


def repo(name, **overrides):
    value = {
        "full_name": name,
        "html_url": f"https://github.com/{name}",
        "description": "AI coding agent for repository tasks",
        "stargazers_count": 1500,
        "forks_count": 100,
        "language": "Python",
        "license": {"spdx_id": "MIT"},
        "pushed_at": "2026-10-09T12:00:00Z",
        "created_at": "2025-01-01T00:00:00Z",
        "topics": ["ai-agent"],
        "fork": False,
        "archived": False,
        "private": False,
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_discovery_deduplicates_filters_old_forks_and_limits_results():
    def handler(request):
        items = [
            repo("acme/agent"),
            repo("acme/agent", stargazers_count=1700),
            repo("acme/old", pushed_at="2025-01-01T00:00:00Z"),
            repo("acme/fork", fork=True),
        ]
        return httpx.Response(200, json={"total_count": len(items), "items": items})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    discovery = GitHubRepositoryDiscovery(
        client=client,
        queries=("topic:ai-agent", "topic:llm"),
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    try:
        result = await discovery.search(max_candidates=5)
    finally:
        await client.aclose()

    assert [item["full_name"] for item in result] == ["acme/agent"]
    assert result[0]["stars"] == 1700
    assert result[0]["license"] == "MIT"


@pytest.mark.asyncio
async def test_discovery_can_include_authorized_private_repositories():
    seen_headers = []
    def handler(request):
        seen_headers.append(request.headers.get("Authorization"))
        if "is:private" in request.url.params["q"]:
            return httpx.Response(200, json={"items": [repo("owner/internal-tool", private=True)]})
        return httpx.Response(200, json={"items": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    discovery = GitHubRepositoryDiscovery(
        client=client,
        queries=("topic:ai-agent",),
        token="read-only-test-token",
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    try:
        result = await discovery.search()
    finally:
        await client.aclose()

    assert len(result) == 1
    assert result[0]["private"] is True
    assert seen_headers == ["Bearer read-only-test-token", "Bearer read-only-test-token"]


@pytest.mark.asyncio
async def test_discovery_fails_explicitly_on_api_error():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    )
    discovery = GitHubRepositoryDiscovery(client=client, queries=("topic:ai-agent",))
    try:
        with pytest.raises(DiscoveryError, match="discovery failed"):
            await discovery.search()
    finally:
        await client.aclose()


def test_heuristic_score_rewards_recent_activity_and_identified_license():
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    recent = {
        "stars": 1500,
        "pushed_at": "2026-10-09T12:00:00Z",
        "license": "MIT",
        "description": "A useful developer tool",
        "language": "Python",
    }
    old_unlicensed = {
        **recent,
        "pushed_at": "2025-01-01T00:00:00Z",
        "license": "NOASSERTION",
    }
    assert heuristic_score(recent, now) > heuristic_score(old_unlicensed, now)


@pytest.mark.asyncio
async def test_agent_uses_only_model_assessments_for_discovered_public_repositories():
    class FakeDiscovery:
        token = ""

        async def search(self, max_candidates=30):
            return [{
                "full_name": "acme/real",
                "url": "https://github.com/acme/real",
                "description": "real project",
                "stars": 1000,
                "forks": 10,
                "language": "Python",
                "license": "MIT",
                "pushed_at": "2026-10-09T12:00:00Z",
                "created_at": "2025-01-01T00:00:00Z",
                "topics": [],
                "private": False,
            }]

    class FakeProvider:
        async def complete(self, system_prompt, user_prompt):
            return json.dumps({"assessments": [
                {"full_name": "attacker/fabricated", "relevance": 5,
                 "capability": "invented", "risks": []},
                {"full_name": "acme/real", "relevance": 4,
                 "capability": "coding automation", "risks": ["needs isolation"]},
            ]})

    agent = ResearchAndDevelopmentAgent(
        discovery=FakeDiscovery(),
        provider=FakeProvider(),
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    report = await agent.run()
    candidate = report["candidates"][0]

    assert report["model_assessment_status"] == "passed"
    assert candidate["full_name"] == "acme/real"
    assert candidate["model_assessment"]["relevance"] == 4
    assert report["policy"]["no_third_party_code_executed"] is True
    assert report["policy"]["no_repository_imported_automatically"] is True


@pytest.mark.asyncio
async def test_private_repository_metadata_is_not_sent_to_external_model():
    class FakeDiscovery:
        token = "configured"

        async def search(self, max_candidates=30):
            return [{
                "full_name": "owner/internal-tool",
                "url": "https://github.com/owner/internal-tool",
                "description": "private project metadata",
                "stars": 5,
                "forks": 0,
                "language": "Python",
                "license": "NOASSERTION",
                "pushed_at": "2026-10-09T12:00:00Z",
                "created_at": "2026-10-01T00:00:00Z",
                "topics": [],
                "private": True,
            }]

    class NeverCalledProvider:
        async def complete(self, system_prompt, user_prompt):
            raise AssertionError("private metadata must not be sent to the external provider")

    report = await ResearchAndDevelopmentAgent(
        discovery=FakeDiscovery(), provider=NeverCalledProvider()
    ).run()

    assert report["model_assessment_status"] == "skipped_private_metadata"
    assert report["private_candidate_count"] == 1
    assert report["policy"]["private_metadata_sent_to_external_model"] is False


@pytest.mark.asyncio
async def test_agent_keeps_metadata_results_if_model_returns_invalid_json():
    class FakeDiscovery:
        token = ""

        async def search(self, max_candidates=30):
            return [{
                "full_name": "acme/real",
                "url": "https://github.com/acme/real",
                "description": "real project",
                "stars": 10,
                "forks": 0,
                "language": "Python",
                "license": "NOASSERTION",
                "pushed_at": "2026-10-09T12:00:00Z",
                "created_at": "2026-10-01T00:00:00Z",
                "topics": [],
                "private": False,
            }]

    class FakeProvider:
        async def complete(self, system_prompt, user_prompt):
            return "not json"

    report = await ResearchAndDevelopmentAgent(
        discovery=FakeDiscovery(), provider=FakeProvider()
    ).run()

    assert report["model_assessment_status"] == "invalid_output"
    assert report["candidate_count"] == 1
    assert report["candidates"][0]["license_status"] == "review_required"


def test_markdown_report_warns_that_discovery_is_not_a_security_audit():
    report = {
        "generated_at": "2026-10-10T00:00:00+00:00",
        "candidate_count": 0,
        "private_candidate_count": 0,
        "model_assessment_status": "not_configured",
        "candidates": [],
    }
    markdown = render_markdown(report)
    assert "No candidate code was executed" in markdown
    assert "not an approval to import or execute code" in markdown


@pytest.mark.asyncio
async def test_mission_is_preserved_in_report_and_markdown():
    class FakeDiscovery:
        token = ""

        async def search(self, max_candidates=30):
            return []

    mission = "Research Tomatom browser extensions and free hosting limits."
    report = await ResearchAndDevelopmentAgent(discovery=FakeDiscovery()).run(mission=mission)
    markdown = render_markdown(report)

    assert report["mission"] == mission
    assert report["research_scope"]["source_code_and_documentation"] == "not inspected by this version"
    assert "job descriptions" in markdown
    assert "not independently investigated" in markdown


def test_mission_discovery_adds_bounded_targeted_query():
    discovery = GitHubRepositoryDiscovery(mission="Tomatom browser extensions free hosting limits")
    words = []
    stop_words = {"about", "after", "also", "and", "are", "build", "built", "can", "could", "design", "find", "from", "free", "give", "into", "mission", "need", "our", "that", "the", "their", "them", "then", "this", "through", "tools", "with", "would", "your", "brain", "tomatom", "research", "investigate", "return"}
    for raw_word in discovery.mission.lower().replace("/", " ").replace("-", " ").split():
        word = "".join(ch for ch in raw_word if ch.isalnum())
        if len(word) >= 4 and word not in stop_words and word not in words:
            words.append(word)
        if len(words) >= 5:
            break
    assert words == ["browser", "extensions", "hosting", "limits"]


@pytest.mark.asyncio
async def test_agent_includes_public_source_evidence_without_claiming_code_audit():
    class FakeDiscovery:
        token = ""
        async def search(self, max_candidates=30):
            return []

    class FakeEvidenceCollector:
        async def collect(self, candidates, mission):
            return {
                "repository_documentation": [{"repository": "acme/browser", "source_url": "https://github.com/acme/browser", "source_type": "public README", "excerpt": "Uses Playwright", "evidence_boundary": "README only"}],
                "repository_documentation_count": 1,
                "repository_documentation_errors": 0,
                "job_market": {"status": "completed", "source_url": "https://remotive.com/api/remote-jobs", "sample_count": 1, "jobs": [{"title": "Browser Automation Engineer", "company": "Example", "url": "https://example.com/job", "tags": ["Playwright", "Python"], "description_excerpt": "Build browser automation"}], "limitation": "sample only"},
            }

    report = await ResearchAndDevelopmentAgent(discovery=FakeDiscovery(), evidence_collector=FakeEvidenceCollector()).run(mission="Build Tomatom")
    assert report["evidence"]["repository_documentation_count"] == 1
    assert report["evidence"]["job_market"]["jobs"][0]["tags"] == ["Playwright", "Python"]
    assert report["research_scope"]["source_code"] == "not audited; no third-party code executed"
