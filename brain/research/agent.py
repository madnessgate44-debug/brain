"""R&D agent: rank technology discoveries and produce evidence-linked reports."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol

from brain.research.discovery import GitHubRepositoryDiscovery, heuristic_score
from brain.research.evidence import ResearchEvidenceCollector


class TextProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


_MISSION_GROUPS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("browser", 30, ("browser", "browsers", "web", "playwright", "chromium", "puppeteer", "selenium")),
    ("automation", 15, ("automation", "automate", "automated", "agent", "agents", "computer", "rpa")),
    ("extensions", 15, ("extension", "extensions", "chrome", "firefox", "addon", "addons")),
    ("security", 10, ("security", "sandbox", "ssrf", "permission", "permissions", "isolation")),
    ("hosting", 10, ("hosting", "host", "deployment", "serverless", "actions", "runner", "cloud")),
    ("persistence", 10, ("persistence", "persistent", "database", "sqlite", "state", "recovery", "artifact")),
    ("research", 10, ("research", "search", "scrape", "crawling", "retrieval", "crawl", "fetch")),
)


def mission_relevance(candidate: dict[str, Any], mission: str) -> tuple[int, list[str]]:
    """Estimate mission fit from public metadata; this is not a code-quality verdict."""
    mission_tokens = set(re.findall(r"[a-z0-9]+", mission.casefold()))
    candidate_text = " ".join([
        str(candidate.get("full_name", "")),
        str(candidate.get("description", "")),
        " ".join(str(topic) for topic in candidate.get("topics", []) if isinstance(topic, str)),
    ]).casefold()
    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate_text))
    active_groups = [
        (name, weight, terms)
        for name, weight, terms in _MISSION_GROUPS
        if any(term in mission_tokens for term in terms)
    ]
    matches: list[str] = []
    score = 0
    for name, weight, terms in active_groups:
        if any(term in candidate_tokens for term in terms):
            matches.append(name)
            score += weight
    return min(100, score), matches


class ResearchAndDevelopmentAgent:
    """Research public and authorized private repository metadata."""

    def __init__(
        self,
        discovery: GitHubRepositoryDiscovery | None = None,
        provider: TextProvider | None = None,
        now: datetime | None = None,
        evidence_collector: ResearchEvidenceCollector | None = None,
    ) -> None:
        self.discovery = discovery or GitHubRepositoryDiscovery()
        self.provider = provider
        self.now = now or datetime.now(timezone.utc)
        self.evidence_collector = evidence_collector

    async def run(self, max_candidates: int = 30, mission: str = "Find tools that improve Brain research, coding, browser automation, testing, and free execution.") -> dict[str, Any]:
        """Discover candidates, rank them, and return a machine-readable evidence report."""
        mission = mission.strip()[:4000]
        self._active_mission = mission
        candidates = await self.discovery.search(max_candidates=max_candidates)
        ranked: list[dict[str, Any]] = []
        for candidate in candidates:
            score = heuristic_score(candidate, self.now)
            relevance_score, relevance_matches = mission_relevance(candidate, mission)
            license_id = str(candidate.get("license") or "NOASSERTION").upper()
            license_status = (
                "review_required"
                if license_id in {"NOASSERTION", "NONE", "OTHER", "UNKNOWN"}
                else "identified_not_legal_advice"
            )
            recommendation = (
                "low_mission_fit"
                if relevance_score < 25
                else "investigate"
                if score >= 65 and license_status != "review_required"
                else "review_before_import"
            )
            ranked.append({
                **candidate,
                "heuristic_score": score,
                "mission_relevance_score": relevance_score,
                "mission_relevance_matches": relevance_matches,
                "license_status": license_status,
                "recommendation": recommendation,
                "evaluation_basis": "public repository metadata and mission-term overlap only",
                "model_assessment": None,
            })

        public_candidates = [item for item in ranked if not item.get("private", False)]
        model_status = "not_configured"
        if self.provider is not None and public_candidates:
            try:
                assessments = await self._assess_with_model(public_candidates[:12])
                by_name = {item["full_name"]: item for item in assessments}
                for item in public_candidates:
                    if item["full_name"] in by_name:
                        item["model_assessment"] = by_name[item["full_name"]]
                model_status = "passed" if assessments else "invalid_output"
            except (ValueError, TypeError, json.JSONDecodeError):
                model_status = "invalid_output"
            except Exception:
                model_status = "unavailable"
        elif self.provider is not None and ranked:
            model_status = "skipped_private_metadata"

        ranked.sort(
            key=lambda item: (
                item["mission_relevance_score"],
                item["model_assessment"]["relevance"]
                if item.get("model_assessment") else 0,
                item["heuristic_score"],
                item["stars"],
            ),
            reverse=True,
        )
        private_count = sum(1 for item in ranked if item.get("private", False))
        evidence = (
            await self.evidence_collector.collect(ranked, mission)
            if self.evidence_collector is not None
            else {
                "repository_documentation": [],
                "repository_documentation_count": 0,
                "repository_documentation_errors": 0,
                "job_market": {
                    "status": "not_configured",
                    "source_url": "https://remotive.com/api/remote-jobs",
                    "sample_count": 0,
                    "jobs": [],
                    "limitation": "No evidence collector configured; no job-market conclusions should be drawn.",
                },
                "limitation": "No public source evidence collected in this run.",
            }
        )
        return {
            "schema_version": "1.1",
            "mission": mission,
            "research_scope": {
                "repository_metadata": "searched and scored",
                "source_code": "not audited; no third-party code executed",
                "repository_documentation": "public README excerpts collected when available",
                "general_web_browsing": evidence.get("web_research", {}).get("status", "unknown"),
                "job_descriptions_and_live_skill_requirements": evidence.get("job_market", {}).get("status", "unknown"),
                "hosting_prices_and_free_tier_terms": "searched where public pages are returned; not independently verified",
                "limitations": [
                    "GitHub repository metadata is a discovery signal, not source-level evidence.",
                    "This report does not establish job-market requirements or verify hosting terms.",
                ],
            },
            "agent": "research_and_development",
            "generated_at": self.now.isoformat(),
            "status": "completed",
            "discovery_source": (
                "GitHub public search and authorized account metadata"
                if getattr(self.discovery, "token", "")
                else "GitHub public repository search API"
            ),
            "model_assessment_status": model_status,
            "candidate_count": len(ranked),
            "private_candidate_count": private_count,
            "policy": {
                "free_tier_first": True,
                "no_paid_upgrade_or_purchase": True,
                "no_third_party_code_executed": True,
                "no_repository_imported_automatically": True,
                "unlicensed_repositories_require_manual_license_review": True,
                "private_metadata_sent_to_external_model": False,
                "credentials_exposed_to_candidates": False,
            },
            "candidates": ranked,
            "recommendation_summary": (
                "Prioritize candidates with the strongest mission-term overlap, then inspect their source code, dependency chain, security controls, and license before adoption. Metadata and README evidence are not proof of correctness or safety."
                if ranked else
                "No repository candidates were found; refine the mission-specific searches before making adoption decisions."
            ),
            "roadmap": [
                "Shortlist the highest mission-fit repositories and inspect their source, dependencies, maintenance activity, and license.",
                "Compare browser control, extension permissions, navigation/network isolation, and failure recovery against Brain's acceptance criteria.",
                "Prototype one isolated capability at a time; do not execute third-party code in the research runner.",
                "Run end-to-end tests on public test pages and record screenshots, action results, and failure cases.",
                "Measure GitHub Actions execution limits and artifact retention; treat runner state as ephemeral and preserve important reports explicitly.",
            ] if any(term in mission.casefold() for term in ("browser", "playwright", "chromium", "extension", "automation")) else [
                "Review the highest mission-fit candidates and source evidence.",
                "Inspect source, dependencies, maintenance, security controls, and license before adoption.",
                "Validate promising options with a small isolated test and record evidence before changing Brain.",
            ],
            "evidence": evidence,
        }

    async def _assess_with_model(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assert self.provider is not None
        allowed = {item["full_name"] for item in candidates}
        compact = [
            {
                "full_name": item["full_name"],
                "description": item["description"],
                "stars": item["stars"],
                "language": item["language"],
                "license": item["license"],
                "pushed_at": item["pushed_at"],
                "url": item["url"],
            }
            for item in candidates
        ]
        system = (
            "You are Brain's Research and Development analyst. Assess public repository metadata "
            "only. Do not claim to have inspected source code, run tests, verified security, or "
            "confirmed a free hosted tier. Never recommend bypassing access controls or licenses. "
            "Return JSON only: {\"assessments\":[{\"full_name\":string,\"relevance\":integer "
            "1-5,\"capability\":string,\"risks\":[string]}]}. Only use supplied full_name values."
        )
        raw = await self.provider.complete(
            system,
            json.dumps({
                "goal": "Assess public repository metadata for the user's specific research mission. Do not infer source-code, job-market, security, or pricing facts not present in supplied metadata.",
                "mission": self._active_mission,
                "candidates": compact,
            }),
        )
        parsed = json.loads(raw)
        assessments = parsed.get("assessments") if isinstance(parsed, dict) else None
        if not isinstance(assessments, list):
            raise ValueError("Model assessment must contain an assessments array.")
        validated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in assessments:
            if not isinstance(item, dict):
                continue
            name = item.get("full_name")
            relevance = item.get("relevance")
            capability = item.get("capability")
            risks = item.get("risks")
            if (
                name not in allowed
                or name in seen
                or isinstance(relevance, bool)
                or not isinstance(relevance, int)
                or not 1 <= relevance <= 5
                or not isinstance(capability, str)
                or not isinstance(risks, list)
                or any(not isinstance(risk, str) for risk in risks)
            ):
                continue
            seen.add(name)
            validated.append({
                "full_name": name,
                "relevance": relevance,
                "capability": capability[:500],
                "risks": [risk[:300] for risk in risks[:10]],
                "basis": "model assessment of public metadata; not a code audit",
            })
        return validated


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact report without treating repository metadata as trusted instructions."""
    lines = [
        "# Brain R&D discovery report",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Mission: {report.get('mission', 'not supplied')}",
        f"- Candidates: {report.get('candidate_count', 0)}",
        f"- Private candidates: {report.get('private_candidate_count', 0)}",
        f"- Model assessment: {report.get('model_assessment_status', 'unknown')}",
        f"- Source: {report.get('discovery_source', 'unknown')}",
        "",
        "## Research scope and limitations",
        "",
        "- Repository discovery and ranking use metadata only in this version.",
        "- Public README excerpts and a bounded job-board sample may be collected; neither is a source-code audit or comprehensive labor-market survey.",
        "- Do not treat this report as a completed technical or job-market research report.",
        "",
        "## Source evidence",
        "",
        f"- Public README excerpts collected: {report.get('evidence', {}).get('repository_documentation_count', 0)}",
        f"- Job-market sample status: {report.get('evidence', {}).get('job_market', {}).get('status', 'not collected')}",
        "",
        f"- General web research status: {report.get('evidence', {}).get('web_research', {}).get('status', 'not collected')}",
        f"- Public pages fetched: {report.get('evidence', {}).get('web_research', {}).get('pages_fetched', 0)}",
        "",
        "### General web research",
        "",
        "### Public repository documentation",
        "",
    ]
    evidence = report.get("evidence", {})
    for item in evidence.get("repository_documentation", [])[:8]:
        if not isinstance(item, dict):
            continue
        repo_name = str(item.get("repository", "unknown")).replace("[", "\\[").replace("]", "\\]")
        source_url = str(item.get("source_url", ""))
        excerpt = str(item.get("excerpt", "")).replace("\\n", " ")[:700]
        for char in ("\\", "`", "*", "_", "[", "]"):
            excerpt = excerpt.replace(char, "\\" + char)
        lines.extend([
            f"- [{repo_name}]({source_url}) — {item.get('source_type', 'public documentation')}",
            f"  - Excerpt: {excerpt}",
            f"  - Boundary: {item.get('evidence_boundary', 'documentation only; not a code audit')}",
        ])
    web_research = evidence.get("web_research", {})
    for source in web_research.get("sources", [])[:8] if isinstance(web_research, dict) else []:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "Web source")).replace("[", "\\[").replace("]", "\\]")
        url = str(source.get("url", ""))
        excerpt = str(source.get("excerpt", ""))[:700]
        for char in ("\\\\", "`", "*", "_", "[", "]"):
            excerpt = excerpt.replace(char, "\\" + char)
        lines.extend([
            f"- [{title}]({url}) — {source.get('status', 'unknown')}",
            f"  - Search query: {source.get('query', 'not recorded')}",
            f"  - Excerpt: {excerpt or 'No readable excerpt retrieved.'}",
        ])
    for limitation in web_research.get("limitations", []) if isinstance(web_research, dict) else []:
        lines.append(f"- Limitation: {limitation}")
    lines.extend(["", "### Job-market sample", ""])
    job_market = evidence.get("job_market", {})
    for job in job_market.get("jobs", [])[:10] if isinstance(job_market, dict) else []:
        if not isinstance(job, dict):
            continue
        title = str(job.get("title", "Job listing")).replace("[", "\\[").replace("]", "\\]")
        url = str(job.get("url", ""))
        tags = ", ".join(str(tag)[:80] for tag in job.get("tags", [])[:12])
        excerpt = str(job.get("description_excerpt", "")).replace("\\n", " ")[:500]
        for char in ("\\", "`", "*", "_", "[", "]"):
            excerpt = excerpt.replace(char, "\\" + char)
        lines.extend([
            f"- [{title}]({url}) — {job.get('company', 'Company not listed')}",
            f"  - Tags: {tags or 'not provided'}",
            f"  - Description excerpt: {excerpt}",
        ])
    if isinstance(job_market, dict) and job_market.get("limitation"):
        lines.append(f"- Job sample limitation: {job_market['limitation']}")
    lines.append("")
    lines.extend([
        "",
        "## Recommendation and roadmap",
        "",
        str(report.get("recommendation_summary", "No mission-specific recommendation was generated.")),
        "",
        "### Next steps",
        "",
    ])
    roadmap = report.get("roadmap", [])
    if roadmap:
        lines.extend(f"{index}. {step}" for index, step in enumerate(roadmap, start=1))
    else:
        lines.append("No roadmap steps were generated.")
    lines.extend(["", "## Candidate shortlist", ""])
    candidates = report.get("candidates", [])
    if not candidates:
        lines.append("No qualifying candidates were found in this run.")
    for item in candidates[:20]:
        name = str(item.get("full_name", "unknown")).replace("[", "\\[").replace("]", "\\]")
        url = str(item.get("url", ""))
        visibility = "private" if item.get("private", False) else "public"
        lines.extend([
            f"### [{name}]({url})",
            f"- Visibility: {visibility}",
            f"- Mission fit: {item.get('mission_relevance_score', 0)}/100 "
            f"(matched: {', '.join(item.get('mission_relevance_matches', [])) or 'no mission terms'})",
            f"- Metadata quality score: {item.get('heuristic_score', 0)}/100",
            f"- Stars: {item.get('stars', 0)}; language: {item.get('language') or 'unknown'}",
            f"- License identifier: {item.get('license', 'NOASSERTION')} "
            f"({item.get('license_status', 'review_required')})",
            f"- Last pushed: {item.get('pushed_at', 'unknown')}",
            f"- Description: {(item.get('description') or 'No description supplied').replace(chr(10), ' ')}",
            f"- Recommendation: {item.get('recommendation', 'review_before_import')}",
        ])
        assessment = item.get("model_assessment")
        if isinstance(assessment, dict):
            lines.append(
                f"- Model relevance: {assessment.get('relevance')}/5 — "
                f"{assessment.get('capability', '')}"
            )
            if assessment.get("risks"):
                lines.append("- Model-noted risks: " + "; ".join(assessment["risks"]))
        lines.append("")
    lines.extend([
        "## Safety boundary",
        "",
        "This is discovery and triage, not an approval to import or execute code. "
        "Private repository metadata is not sent to the external model. Inspect source, "
        "license terms, dependencies, security, free-tier terms, and isolation requirements "
        "before integration. No candidate code was executed.",
        "",
    ])
    return "\n".join(lines)
