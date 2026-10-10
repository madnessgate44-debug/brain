"""Command-line entry point for scheduled Brain R&D discovery."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.settings import get_setting
from brain.research.agent import ResearchAndDevelopmentAgent, render_markdown
from brain.research.discovery import GitHubRepositoryDiscovery


async def _run(max_candidates: int) -> dict:
    provider = OpenAICompatibleProvider() if get_setting("BRAIN_AI_API_KEY") else None
    agent = ResearchAndDevelopmentAgent(
        discovery=GitHubRepositoryDiscovery(per_query=15),
        provider=provider,
    )
    return await agent.run(max_candidates=max_candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and evaluate technology repositories.")
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    if not 1 <= args.max_candidates <= 100:
        parser.error("--max-candidates must be between 1 and 100.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(_run(args.max_candidates))
    (output_dir / "brain-rd-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "brain-rd-report.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(render_markdown(report))


if __name__ == "__main__":
    main()
