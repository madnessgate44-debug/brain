"""Bounded public evidence collection for Brain R&D missions.

Reads public repository README files and a public job-board API. It never clones,
installs, or executes third-party code. Remote text is treated as untrusted evidence.
"""
from __future__ import annotations

import asyncio
import base64
import html
import re

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse
import ipaddress
import socket


SEARCH_URL = "https://html.duckduckgo.com/html/"


class _SearchResultParser(HTMLParser):
    """Extract only links marked as DuckDuckGo result links."""
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = (attrs_map.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._active = {"href": attrs_map.get("href") or ""}
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active is not None:
            self._active["title"] = _plain_text(" ".join(self._text), 240)
            if self._active["href"] and self._active["title"]:
                self.links.append(self._active)
            self._active = None
            self._text = []


class _PageTextParser(HTMLParser):
    """Extract readable text while ignoring scripts, styles, and navigation boilerplate."""
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "nav", "footer"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "nav", "footer"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            clean = _plain_text(data, 3000)
            if clean:
                self.parts.append(clean)


def _public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in {None, 80, 443}:
            return False
        try:
            address = ipaddress.ip_address(host)
            return address.is_global
        except ValueError:
            if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
                return False
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = {ipaddress.ip_address(item[4][0]) for item in records}
            return bool(addresses) and all(address.is_global for address in addresses)
    except (ValueError, OSError, socket.gaierror):
        return False


def _result_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target
    return raw


def _mission_queries(mission: str) -> list[str]:
    """Create topic-focused web searches; ignore narrative boilerplate and project names."""
    normalized = mission.casefold()
    if any(term in normalized for term in ("browser", "playwright", "chromium", "puppeteer", "extension")):
        return [
            "open source browser automation Playwright Chromium agent",
            "browser extension automation agent Chrome Firefox permissions",
            "GitHub Actions free hosting persistent browser automation limits",
            "browser automation engineer Playwright Python job skills",
        ]
    words = re.findall(r"[A-Za-z0-9+#.]{3,}", mission)
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "brain", "tomatom",
        "into", "free", "design", "first", "platform", "investigate", "relevant",
        "open", "source", "repositories", "repository", "support", "control", "return",
        "evidence", "linked", "recommendation", "roadmap", "build", "operate", "needed",
        "requirements", "mission", "research", "browser", "automation",
    }
    unique: list[str] = []
    for word in words:
        if word.casefold() not in stop and word.casefold() not in {x.casefold() for x in unique}:
            unique.append(word)
        if len(unique) >= 4:
            break
    queries = [" ".join(unique)] if unique else []
    queries.extend([
        "open source AI agent web research evidence",
        "GitHub Actions free hosting persistence limits",
        "AI agent automation engineer job skills",
    ])
    return queries[:4]

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

    def __init__(self, timeout_seconds: float = 12.0, max_readmes: int = 8, max_jobs: int = 10, max_web_pages: int = 8):
        self.timeout_seconds = timeout_seconds
        self.max_readmes = min(8, max(1, max_readmes))
        self.max_jobs = min(10, max(1, max_jobs))
        self.max_web_pages = min(8, max(1, max_web_pages))

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

            web_result = await self._web_research(client, mission)
            job_result = await self._jobs(client)
        return {
            "repository_documentation": readmes,
            "repository_documentation_count": len(readmes),
            "repository_documentation_errors": readme_errors,
            "job_market": job_result,
            "web_research": web_result,
            "policy": {
                "public_sources_only": True,
                "third_party_code_executed": False,
                "private_repository_metadata_sent": False,
                "external_model_received_job_descriptions": False,
            },
            "mission": mission[:4000],
        }


    async def _web_research(self, client: httpx.AsyncClient, mission: str) -> dict[str, Any]:
        """Search public web pages and retrieve bounded text excerpts; never execute page scripts."""
        searches: list[dict[str, str]] = []
        errors: list[str] = []
        seen: set[str] = set()
        for query in _mission_queries(mission):
            try:
                response = await client.get(SEARCH_URL, params={"q": query}, headers={"User-Agent": "Mozilla/5.0 Brain-RD/1.0", "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8"})
                response.raise_for_status()
                parser = _SearchResultParser()
                parser.feed(response.text[:1_000_000])
                for link in parser.links:
                    url = _result_url(link["href"])
                    if not _public_http_url(url) or url in seen:
                        continue
                    seen.add(url)
                    searches.append({"title": link["title"], "url": url, "query": query})
                    if len(searches) >= self.max_web_pages:
                        break
            except (httpx.HTTPError, ValueError):
                errors.append("Search request failed for one query.")
            if len(searches) >= self.max_web_pages:
                break

        pages = await asyncio.gather(
            *(self._fetch_public_page(client, item) for item in searches),
            return_exceptions=True,
        )
        evidence = []
        fetch_errors = 0
        for result in pages:
            if isinstance(result, Exception):
                fetch_errors += 1
            elif result:
                evidence.append(result)
        return {
            "status": "completed" if evidence else "unavailable",
            "search_provider": "DuckDuckGo HTML search",
            "queries": _mission_queries(mission),
            "result_count": len(searches),
            "pages_fetched": len(evidence),
            "fetch_errors": fetch_errors,
            "search_errors": errors,
            "sources": evidence,
            "limitations": [
                "Search results are a bounded sample, not exhaustive coverage.",
                "Page scripts are not executed and forms are not submitted.",
                "Only bounded text excerpts are retained; source claims require independent verification.",
                "Some sites block automated retrieval or return incomplete content.",
            ],
        }

    async def _fetch_public_page(self, client: httpx.AsyncClient, item: dict[str, str]) -> dict[str, Any] | None:
        url = item["url"]
        if not _public_http_url(url):
            return None
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 Brain-RD/1.0", "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8"}, follow_redirects=False)
        if response.is_redirect:
            return {
                "title": item["title"], "url": url, "query": item["query"],
                "status": "redirect_not_followed", "excerpt": "",
            }
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None
        parser = _PageTextParser()
        parser.feed(response.text[:1_000_000])
        excerpt = _plain_text(" ".join(parser.parts), 3500)
        if not excerpt:
            return None
        return {
            "title": item["title"], "url": url, "query": item["query"],
            "status": "fetched", "excerpt": excerpt,
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
