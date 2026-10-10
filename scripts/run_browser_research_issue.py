"""Owner-triggered, free-first public-web research using Brain's planner and Playwright.

Input issue format: /brain browse plus one fenced JSON object with title, objective,
start_url, and optional allowed_domains. Only read-only plans execute automatically.
Plans containing mutating actions are returned for review and are not executed.
Never use this workflow for private/logged-in pages, credentials, CAPTCHA bypass,
purchases, or account changes.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from brain.company.llm_provider import ModelProviderError, ProviderConfigurationError
from brain.runtime.workers.browser_planner import BrowserPlanner, BrowserPlanningError
from brain.runtime.workers.browser_worker import (
    BrowserPolicyError,
    BrowserWorker,
    MUTATING_ACTIONS,
    is_allowed_url,
)


def parse_research_payload(event: dict[str, Any], repository_owner: str) -> dict[str, Any]:
    """Validate an owner-authored public research request."""
    issue = event.get("issue") or {}
    user = issue.get("user") or {}
    if user.get("login", "").casefold() != repository_owner.casefold():
        raise ValueError("Only an issue authored by the repository owner may start research.")

    body = issue.get("body") or ""
    if "/brain browse" not in body:
        raise ValueError("Issue body must include /brain browse.")
    fence = chr(96) * 3
    blocks = re.findall(re.escape(fence) + r"json\s*(.*?)\s*" + re.escape(fence), body, flags=re.DOTALL | re.IGNORECASE)
    if len(blocks) != 1:
        raise ValueError("Include exactly one fenced JSON object after /brain browse.")
    try:
        payload = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValueError("The research request JSON is invalid.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The research request must be a JSON object.")

    allowed_keys = {"title", "objective", "start_url", "allowed_domains"}
    if set(payload) - allowed_keys:
        raise ValueError("Unsupported research fields were supplied.")
    title = payload.get("title")
    objective = payload.get("objective")
    start_url = payload.get("start_url")
    if not isinstance(title, str) or not title.strip() or len(title) > 255:
        raise ValueError("title is required and must be 255 characters or fewer.")
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 10_000:
        raise ValueError("objective is required and must be 10000 characters or fewer.")
    if not isinstance(start_url, str) or not 1 <= len(start_url) <= 2048:
        raise ValueError("start_url is required and must be 2048 characters or fewer.")
    try:
        parsed = urlsplit(start_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("start_url is not a valid public URL.") from exc
    if parsed.scheme not in {"https", "http"} or not hostname or parsed.username or parsed.password:
        raise ValueError("start_url must be an HTTP(S) URL without embedded credentials.")

    domains = payload.get("allowed_domains", [hostname])
    if not isinstance(domains, list) or not domains or len(domains) > 30:
        raise ValueError("allowed_domains must contain 1 to 30 domain rules.")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 255 for item in domains):
        raise ValueError("Every allowed_domains entry must be a non-empty domain rule.")
    domains = [item.strip().lower().rstrip(".") for item in domains]
    from brain.runtime.workers.browser_worker import domain_matches
    if not any(domain_matches(hostname, rule) for rule in domains):
        raise ValueError("start_url host must match one of allowed_domains.")

    return {
        "title": title.strip(),
        "objective": objective.strip(),
        "start_url": start_url,
        "allowed_domains": domains,
    }


def actions_require_approval(actions: list[dict[str, Any]]) -> bool:
    """Use the browser worker's authoritative mutation set."""
    return any(action.get("op") in MUTATING_ACTIONS for action in actions)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


async def execute_research(payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Plan a task, stop for approval if it mutates state, otherwise browse."""
    output_dir.mkdir(parents=True, exist_ok=True)
    planning_objective = (
        payload["objective"]
        + "\n\nStart URL explicitly supplied by the owner: "
        + payload["start_url"]
        + "\nAllowed public domains: "
        + ", ".join(payload["allowed_domains"])
    )
    plan = await BrowserPlanner().plan(planning_objective)
    actions = [dict(action) for action in plan["actions"]]

    # Pin the first navigation to the owner's URL. If the model omitted it, insert it.
    start_host = (urlsplit(payload["start_url"]).hostname or "").lower().rstrip(".")
    if actions and actions[0].get("op") == "navigate":
        planned_host = (urlsplit(actions[0].get("url", "")).hostname or "").lower().rstrip(".")
        if planned_host == start_host:
            actions[0]["url"] = payload["start_url"]
        else:
            actions.insert(0, {"op": "navigate", "url": payload["start_url"]})
    else:
        actions.insert(0, {"op": "navigate", "url": payload["start_url"]})
    if len(actions) > 25:
        raise BrowserPlanningError("The plan exceeds the 25-action safety limit after pinning the start URL.")

    plan_record = {
        "title": payload["title"],
        "objective": payload["objective"],
        "start_url": payload["start_url"],
        "allowed_domains": payload["allowed_domains"],
        "actions": actions,
        "execution_started": False,
    }
    _write_json(output_dir / "browser-plan.json", plan_record)

    if actions_require_approval(actions):
        result = {
            "status": "requires_owner_approval",
            "reason": "The proposed plan includes an action that may change website state.",
            "requested_actions": len(actions),
            "completed_actions": 0,
            "results": [],
        }
        _write_json(output_dir / "browser-execution-report.json", result)
        copy_payload = {
            "title": payload["title"],
            "objective": payload["objective"],
            "allowed_domains": payload["allowed_domains"],
            "actions": actions,
            "owner_approved": True,
        }
        _write_markdown(
            output_dir / "browser-result.md",
            [
                "## Brain public-web research: APPROVAL REQUIRED",
                "",
                f"- **Task:** {payload['title']}",
                f"- **Start URL:** {payload['start_url']}",
                "- **Execution:** Not started. No website changes were made.",
                "",
                "Review the exact proposed actions below. To execute a mutating task, create a separate issue with /brain browser and this JSON only after explicitly approving every action.",
                "",
                json.dumps(copy_payload, ensure_ascii=False, indent=2),
                "",
                "This workflow is limited to public, non-sensitive pages. Do not use it for logged-in accounts, private data, credentials, purchases, or CAPTCHA/access-control bypass.",
            ],
        )
        return result

    # Preflight every navigation before starting Chromium. The worker repeats these checks.
    for action in actions:
        if action.get("op") == "navigate" and not is_allowed_url(
            action.get("url", ""), payload["allowed_domains"]
        ):
            raise BrowserPolicyError("A planned navigation is outside the allowed public domains.")

    profile_root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "brain-public-research-profile"
    worker = BrowserWorker(
        allowed_domains=payload["allowed_domains"],
        profile_dir=str(profile_root),
        headless=True,
    )
    result = await worker.execute(actions, owner_approved=False)
    for item in result.get("results", []):
        value = item.get("result")
        if item.get("op") == "screenshot" and isinstance(value, dict) and value.get("base64"):
            image_bytes = base64.b64decode(value.pop("base64"))
            filename = f"screenshot-action-{item['index'] + 1:02d}.png"
            (output_dir / filename).write_bytes(image_bytes)
            value["artifact"] = filename
    result["title"] = payload["title"]
    result["objective"] = payload["objective"]
    result["allowed_domains"] = payload["allowed_domains"]
    _write_json(output_dir / "browser-execution-report.json", result)

    lines = [
        f"## Brain public-web research: {result.get('status', 'unknown').upper()}",
        "",
        f"- **Task:** {payload['title']}",
        f"- **Start URL:** {payload['start_url']}",
        f"- **Actions completed:** {result.get('completed_actions', 0)}/{result.get('requested_actions', 0)}",
        "- **Scope:** Public, non-sensitive websites only.",
        "",
        "### Evidence log",
    ]
    for item in result.get("results", []):
        if item.get("ok"):
            safe = dict(item.get("result", {}))
            if "text" in safe:
                safe["text"] = "[page text omitted from public issue comment; inspect the workflow artifact]"
            safe.pop("base64", None)
            lines.append(f"- Action {item.get('index', 0) + 1} ({item.get('op')}): PASS — {json.dumps(safe, ensure_ascii=False)[:500]}")
        else:
            lines.append(f"- Action {item.get('index', 0) + 1} ({item.get('op')}): FAIL — {item.get('error')}: {item.get('message')}")
    lines.extend([
        "",
        "The full plan, JSON evidence report, page text, and screenshots (if any) are attached to the workflow run. Artifacts are not permanent storage.",
    ])
    _write_markdown(output_dir / "browser-result.md", lines)
    return result


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    output_dir = Path("browser-output")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not event_path or not owner:
            raise ValueError("Missing GitHub issue event context.")
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        payload = parse_research_payload(event, owner)
        result = asyncio.run(execute_research(payload, output_dir))
        return 0 if result.get("status") in {"succeeded", "requires_owner_approval"} else 1
    except (ValueError, BrowserPolicyError, BrowserPlanningError, ProviderConfigurationError, ModelProviderError) as exc:
        message = f"## Brain public-web research: BLOCKED\n\n{str(exc)[:1000]}\n\nNo browser actions were executed unless the report explicitly says otherwise."
        _write_markdown(output_dir / "browser-result.md", [message])
        _write_json(output_dir / "browser-execution-report.json", {"status": "blocked", "reason": str(exc)[:1000]})
        return 1
    except Exception as exc:  # noqa: BLE001 - report safe failure details to the owner
        message = f"## Brain public-web research: FAILED\n\nWorker error: {type(exc).__name__}. Inspect workflow logs for details."
        _write_markdown(output_dir / "browser-result.md", [message])
        _write_json(output_dir / "browser-execution-report.json", {"status": "failed", "error_type": type(exc).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
