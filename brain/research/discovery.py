"""Bounded public GitHub discovery for Brain's R&D agent.

Discovery is read-only. Candidate repositories are metadata-scanned only; this module
never clones, installs, or executes third-party code.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


class DiscoveryError(RuntimeError):
    """Raised when repository discovery cannot produce trustworthy results."""


DEFAULT_QUERIES = (
    "topic:ai-agent stars:>50",
    "topic:llm stars:>100",
    "topic:developer-tools stars:>100",
    "AI coding agent in:name,description stars:>100",
)


class GitHubRepositoryDiscovery:
    """Search public GitHub repository metadata with bounded request volume."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        queries: tuple[str, ...] = DEFAULT_QUERIES,
        per_query: int = 15,
        timeout_seconds: float = 15.0,
        now: datetime | None = None,
    ) -> None:
        self._client = client
        self.queries = queries
        self.per_query = min(30, max(1, per_query))
        self.timeout_seconds = timeout_seconds
        self.now = now or datetime.now(timezone.utc)

    async def search(self, max_candidates: int = 30) -> list[dict[str, Any]]:
        """Return deduplicated, recently active public repository candidates."""
        limit = min(100, max(1, max_candidates))
        cutoff = (self.now - timedelta(days=180)).date().isoformat()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Brain-RD-Agent",
            },
        )
        found: dict[str, dict[str, Any]] = {}
        try:
            for query in self.queries:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"{query} pushed:>={cutoff} archived:false",
                        "sort": "updated",
                        "order": "desc",
                        "per_page": self.per_query,
                    },
                )
                if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                    raise DiscoveryError("GitHub search API rate limit reached; retry in a later run.")
                response.raise_for_status()
                payload = response.json()
                items = payload.get("items")
                if not isinstance(items, list):
                    raise DiscoveryError("GitHub search returned an unexpected response shape.")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    full_name = item.get("full_name")
                    if not isinstance(full_name, str) or "/" not in full_name:
                        continue
                    if item.get("fork") is True or item.get("archived") is True:
                        continue
                    pushed_at = item.get("pushed_at")
                    if not isinstance(pushed_at, str) or pushed_at[:10] < cutoff:
                        continue
                    license_data = item.get("license")
                    license_id = (
                        license_data.get("spdx_id", "NOASSERTION")
                        if isinstance(license_data, dict)
                        else "NOASSERTION"
                    )
                    candidate = {
                        "full_name": full_name,
                        "url": item.get("html_url", ""),
                        "description": (item.get("description") or "")[:500],
                        "stars": int(item.get("stargazers_count") or 0),
                        "forks": int(item.get("forks_count") or 0),
                        "language": item.get("language"),
                        "license": license_id or "NOASSERTION",
                        "pushed_at": pushed_at,
                        "created_at": item.get("created_at"),
                        "topics": item.get("topics", []) if isinstance(item.get("topics"), list) else [],
                    }
                    previous = found.get(full_name)
                    if previous is None or candidate["stars"] > previous["stars"]:
                        found[full_name] = candidate
        except DiscoveryError:
            raise
        except httpx.HTTPError as exc:
            raise DiscoveryError(f"GitHub repository discovery failed: {type(exc).__name__}.") from exc
        finally:
            if owns_client:
                await client.aclose()

        candidates = sorted(
            found.values(),
            key=lambda item: (item["pushed_at"], item["stars"]),
            reverse=True,
        )
        return candidates[:limit]


def heuristic_score(candidate: dict[str, Any], now: datetime | None = None) -> int:
    """Score public metadata only; this is a triage signal, not a security verdict."""
    now = now or datetime.now(timezone.utc)
    score = 0
    stars = int(candidate.get("stars") or 0)
    score += 30 if stars >= 5000 else 24 if stars >= 1000 else 16 if stars >= 250 else 8
    pushed_at = str(candidate.get("pushed_at") or "")
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        age_days = max(0, (now - pushed).days)
        score += 30 if age_days <= 7 else 24 if age_days <= 30 else 12 if age_days <= 90 else 4
    except (ValueError, TypeError):
        score += 0
    license_id = str(candidate.get("license") or "NOASSERTION").upper()
    if license_id not in {"NOASSERTION", "NONE", "OTHER", "UNKNOWN"}:
        score += 20
    if str(candidate.get("description") or "").strip():
        score += 10
    if candidate.get("language"):
        score += 5
    if candidate.get("archived") is True or candidate.get("fork") is True:
        score -= 100
    return min(100, max(0, score))
