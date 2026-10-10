"""Bounded public evidence collection for Brain R&D missions.

Reads public repository README files and a public job-board API. It never clones,
installs, or executes third-party code. Remote text is treated as untrusted evidence.
"""
from __future__ import annotations

import asyncio
import base64
import html
import re
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"


def _safe_repo_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value))


def _plain_text(value: Any, limit: int = 1200) -> str:
    if not isinstance(value, str):
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


class ResearchEvidenceCollector:
    """Collect bounded, public, link-backed evidence for candidate repositories and job skills."""

    def __init__(self, timeout_seconds: float = 12.0, max_readmes: int = 8, max_jobs: int = 10):
        self.timeout_seconds = timeout_seconds
        self.max_readmes = min(8, max(1, max_readmes))
        self.max_jobs = min(10, max(1, max_jobs))

    async def collect(self, candidates: list[dict[str, Any]], mission: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Brain-RD-Evidence-Collector",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers, follow_redirects=False) as client:
            public = [c for c in candidates if not c.get("private") and _safe_repo_name(str(c.get("full_name", "")))]
            readme_results = await asyncio.gather(
                *(self._readme(client, c) for c in public[: self.max_readmes]),
                return_exceptions=True,
            )
            readmes = []
            readme_errors = 0
            for result in readme_results:
                if isinstance(result, Exception):
                    readme_errors += 1
                elif result:
                    readmes.append(result)

            job_result = await self._jobs(client)
        return {
            "repository_documentation": readmes,
            "repository_documentation_count": len(readmes),
            "repository_documentation_errors": readme_errors,
            "job_market": job_result,
            "policy": {
                "public_sources_only": True,
                "third_party_code_executed": False,
                "private_repository_metadata_sent": False,
                "external_model_received_job_descriptions": False,
            },
            "mission": mission[:4000],
        }

    async def _readme(self, client: httpx.AsyncClient, candidate: dict[str, Any]) -> dict[str, Any] | None:
        name = str(candidate.get("full_name", ""))
        response = await client.get(f"{GITHUB_API}/repos/{name}/readme")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        encoded = payload.get("content")
        if not isinstance(encoded, str):
            return None
        try:
            raw = base64.b64decode(encoded)
            text = raw.decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return None
        # Retain a bounded excerpt only; do not interpret repository text as instructions.
        excerpt = _plain_text(text, 5000)
        if not excerpt:
            return None
        url = payload.get("html_url") or f"https://github.com/{name}"
        if not isinstance(url, str) or not url.startswith("https://github.com/"):
            url = f"https://github.com/{name}"
        return {
            "repository": name,
            "source_url": url,
            "source_type": "public README",
            "excerpt": excerpt,
            "evidence_boundary": "README text only; source implementation and security not audited",
        }

    async def _jobs(self, client: httpx.AsyncClient) -> dict[str, Any]:
        # A public job-board endpoint, no API key. Results are evidence samples, not a labor-market census.
        try:
            response = await client.get(REMOTIVE_API, params={"search": "browser automation playwright"})
            response.raise_for_status()
            payload = response.json()
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            items = []
            if isinstance(jobs, list):
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    url = job.get("url")
                    title = job.get("title")
                    company = job.get("company_name")
                    if not isinstance(url, str) or not url.startswith("https://"):
                        continue
                    if not isinstance(title, str) or not isinstance(company, str):
                        continue
                    tags = job.get("tags", [])
                    items.append({
                        "title": _plain_text(title, 180),
                        "company": _plain_text(company, 120),
                        "url": url,
                        "published_at": job.get("publication_date") if isinstance(job.get("publication_date"), str) else None,
                        "tags": [_plain_text(tag, 80) for tag in tags[:20] if isinstance(tag, str)] if isinstance(tags, list) else [],
                        "description_excerpt": _plain_text(job.get("description"), 1400),
                        "source": "Remotive public job-board API",
                    })
                    if len(items) >= self.max_jobs:
                        break
            return {
                "status": "completed",
                "source_url": REMOTIVE_API,
                "query": "browser automation playwright",
                "sample_count": len(items),
                "jobs": items,
                "limitation": "Search sample only; not a comprehensive job-market survey. Listings may expire.",
            }
        except (httpx.HTTPError, ValueError, TypeError):
            return {
                "status": "unavailable",
                "source_url": REMOTIVE_API,
                "query": "browser automation playwright",
                "sample_count": 0,
                "jobs": [],
                "limitation": "Public job-board request failed; no job-market conclusions should be drawn.",
            }
