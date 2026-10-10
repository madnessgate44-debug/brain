"""R&D agent: rank public technology discoveries and produce evidence-linked reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol

from brain.research.discovery import GitHubRepositoryDiscovery, heuristic_score


class TextProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class ResearchAndDevelopmentAgent:
    """Research public GitHub metadata and optionally use Brain's configured model."""

    def __init__(
        self,
        discovery: GitHubRepositoryDiscovery | None = None,
        provider: TextProvider | None = None,
        now: datetime | None = None,
    ) -> None:
        self.discovery = discovery or GitHubRepositoryDiscovery()
        self.provider = provider
        self.now = now or datetime.now(timezone.utc)

    async def run(self, max_candidates: int = 30) -> dict[str, Any]:
        """Discover candidates, rank them, and return a machine-readable evidence report."""
        candidates = await self.discovery.search(max_candidates=max_candidates)
        ranked: list[dict[str, Any]] = []
        for candidate in candidates:
            score = heuristic_score(candidate, self.now)
            license_id = str(candidate.get("license") or "NOASSERTION").upper()
            license_status = (
                "review_required"
                if license_id in {"NOASSERTION", "NONE", "OTHER", "UNKNOWN"}
                else "identified_not_legal_advice"
            )
            ranked.append({
                **candidate,
                "heuristic_score": score,
                "license_status": license_status,
                "recommendation": (
                    "investigate"
                    if score >= 65 and license_status != "review_required"
                    else "review_before_import"
                ),
                "evaluation_basis": "public GitHub metadata only",
                "model_assessment": None,
            })

        model_status = "not_configured"
        if self.provider is not None and ranked:
            model_status = "failed"
            try:
                assessments = await self._assess_with_model(ranked[:12])
                by_name = {item["full_name"]: item for item in assessments}
                for item in ranked:
                    if item["full_name"] in by_name:
                        item["model_assessment"] = by_name[item["full_name"]]
                model_status = "passed"
            except (ValueError, TypeError, json.JSONDecodeError):
                model_status = "invalid_output"
            except Exception:
                model_status = "unavailable"

        ranked.sort(
            key=lambda item: (
                item["model_assessment"]["relevance"]
                if item.get("model_assessment") else 0,
                item["heuristic_score"],
                item["stars"],
            ),
            reverse=True,
        )
        return {
            "schema_version": "1.0",
            "agent": "research_and_development",
            "generated_at": self.now.isoformat(),
            "status": "completed",
            "discovery_source": "GitHub public repository search API",
            "model_assessment_status": model_status,
            "candidate_count": len(ranked),
            "policy": {
                "free_tier_first": True,
                "no_paid_upgrade_or_purchase": True,
                "no_third_party_code_executed": True,
                "no_repository_imported_automatically": True,
                "unlicensed_repositories_require_manual_license_review": True,
                "credentials_exposed_to_candidates": False,
            },
            "candidates": ranked,
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
                "goal": "Find tools that could improve Brain's coding, research, browser, testing, "
                        "or free cloud execution capabilities.",
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
                "basis": "model assessment of supplied public metadata; not a code audit",
            })
        return validated


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact report without treating repository metadata as trusted instructions."""
    lines = [
        "# Brain R&D discovery report",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Candidates: {report.get('candidate_count', 0)}",
        f"- Model assessment: {report.get('model_assessment_status', 'unknown')}",
        "- Source: public GitHub repository search metadata",
        "",
        "## Candidate shortlist",
        "",
    ]
    candidates = report.get("candidates", [])
    if not candidates:
        lines.append("No qualifying candidates were found in this run.")
    for item in candidates[:20]:
        name = str(item.get("full_name", "unknown")).replace("[", "\\[").replace("]", "\\]")
        url = str(item.get("url", ""))
        lines.extend([
            f"### [{name}]({url})",
            f"- Heuristic score: {item.get('heuristic_score', 0)}/100",
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
        "Inspect repository source, license terms, dependencies, security, free-tier terms, "
        "and isolation requirements before integration. No candidate code was executed.",
        "",
    ])
    return "\n".join(lines)
