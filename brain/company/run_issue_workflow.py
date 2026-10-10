"""Run Brain's specialist workflow for a trusted owner-created GitHub issue."""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.company.diagnostics import write_failure_artifacts
from brain.company.mission_capabilities import plan_capabilities

from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.engine import CompanyWorkflowEngine
from brain.company.github_gateway import GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.tools import GitHubCompanyTools
from brain.research.evidence import ResearchEvidenceCollector


def should_collect_public_web_research(objective: str) -> bool:
    """Enable shared public-web evidence for research, current-information, and browser tasks."""
    text = (objective or "").casefold()
    triggers = (
        r"\bsearch (?:the )?web\b",
        r"\bbrowse (?:the )?web\b",
        r"\bweb research\b",
        r"\bonline research\b",
        r"\bexternal sources\b",
        r"\blatest\b",
        r"\bcurrent (?:docs|documentation|pricing|hosting|market|requirements|options)\b",
        r"\bup[- ]to[- ]date\b",
        r"\bmarket research\b",
        r"\bjob[- ]market\b",
        r"\bplaywright\b",
        r"\bchromium\b",
        r"\bbrowser automation\b",
        r"\bbrowser extension\b",
    )
    return any(re.search(pattern, text) for pattern in triggers)


async def collect_shared_public_web_evidence(
    objective: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fetch a small, safe evidence bundle once so every specialist can use the same sources."""
    if not should_collect_public_web_research(objective):
        return {"status": "not_requested", "queries": [], "sources": [], "pages_fetched": 0}
    try:
        result = await ResearchEvidenceCollector(max_web_pages=6).collect_web_research(objective)
        sources = [
            {
                "title": str(item.get("title", "Web source"))[:180],
                "url": str(item.get("url", ""))[:2048],
                "query": str(item.get("query", ""))[:240],
                "status": str(item.get("status", "unknown")),
                "excerpt": str(item.get("excerpt", ""))[:1400],
            }
            for item in result.get("sources", [])[:6]
            if isinstance(item, dict)
        ]
        bounded = {
            "status": result.get("status", "unknown"),
            "search_provider": result.get("search_provider", "unknown"),
            "queries": result.get("queries", [])[:4],
            "pages_fetched": len(sources),
            "sources": sources,
            "limitations": result.get("limitations", [])[:6],
        }
        events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "public_web_research",
            "status": "PASS" if bounded["status"] == "completed" else "WARN",
            "detail": f"Collected {len(sources)} bounded public source excerpts; sources are untrusted context, not proof of repository behavior.",
        })
        return bounded
    except Exception as exc:
        events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "public_web_research",
            "status": "WARN",
            "detail": f"Public web research unavailable ({type(exc).__name__}); no browsing success is claimed.",
        })
        return {
            "status": "unavailable",
            "queries": [],
            "sources": [],
            "pages_fetched": 0,
            "limitations": ["Public web evidence could not be collected in this run."],
        }


def build_audit_source_chunks(
    source_contents: dict[str, str],
    max_chars: int = 130000,
    max_line_chars: int = 3500,
) -> list[dict[str, str]]:
    """Encode numbered source compactly so audit context does not repeat paths per line."""
    chunks: list[dict[str, str]] = []
    current_lines: list[str] = []
    current_chars = 0

    for path in sorted(source_contents.keys()):
        content = source_contents[path]
        try:
            lines = content.splitlines()
        except Exception:
            lines = [content]

        for idx, line in enumerate(lines, 1):
            safe_line = line[:max_line_chars]
            entry = f"{path}:{idx}:{safe_line}"
            entry_len = len(entry) + 1  # +1 for actual newline
            if current_chars + entry_len > max_chars and current_lines:
                chunks.append({"source_context": "\n".join(current_lines)})
                current_lines = [
                    f"[Continuation from previous chunk]"
                ]
                current_chars = len(current_lines[0]) + 1
            current_lines.append(entry)
            current_chars += entry_len

    if current_lines:
        chunks.append({"source_context": "\n".join(current_lines)})

    if not chunks:
        chunks.append({"source_context": "(No source files provided)"})

    return chunks
