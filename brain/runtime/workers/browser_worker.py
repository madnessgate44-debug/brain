"""Bounded browser execution for Brain missions.

The browser is an internal worker. It never accepts credentials or cookies in a task.
Mutating actions require an explicit owner-approved flag supplied only through the
authenticated browser-task API; runtime dispatch is separately HMAC-bound to a mission.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from urllib.parse import urlsplit


class BrowserPolicyError(ValueError):
    """Raised when a browser task violates the execution policy."""


MUTATING_ACTIONS = frozenset({"click", "type", "press"})
SUPPORTED_ACTIONS = frozenset(
    {"navigate", "inspect", "click", "type", "press", "wait_for", "screenshot"}
)
MAX_ACTIONS = 25
MAX_TEXT_CHARS = 12_000

# Consumer AI chat interfaces are not generic automation APIs. Their current
# terms restrict automated extraction of service output. Brain may open these
# sites for a human, but must not script interaction or read chat output there.
RESTRICTED_CONSUMER_AI_HOSTS = frozenset({
    "chatgpt.com",
    "chat.openai.com",
    "gemini.google.com",
    "bard.google.com",
})


def is_restricted_consumer_ai_url(raw_url: str) -> bool:
    """Return whether a URL is a consumer ChatGPT/Gemini chat interface."""
    try:
        hostname = (urlsplit(raw_url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(
        hostname == host or hostname.endswith("." + host)
        for host in RESTRICTED_CONSUMER_AI_HOSTS
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def browser_dispatch_payload(
    mission_id: str,
    title: str,
    objective: str,
    actions: list[dict[str, Any]],
    owner_approved: bool,
) -> dict[str, Any]:
    """Return the exact payload covered by the dispatch signature."""
    return {
        "mission_id": mission_id,
        "title": title,
        "objective": objective,
        "actions": actions,
        "owner_approved": owner_approved,
        "version": 1,
    }


def sign_browser_dispatch(secret: str, payload: dict[str, Any]) -> str:
    """Sign a browser dispatch so unsigned mission metadata cannot trigger execution."""
    if len(secret) < 24:
        raise BrowserPolicyError("BRAIN_CONTROL_API_KEY must be configured with at least 24 characters.")
    return hmac.new(secret.encode(), _canonical_json(payload).encode(), hashlib.sha256).hexdigest()


def verify_browser_dispatch(
    secret: str,
    payload: dict[str, Any],
    signature: str,
) -> bool:
    """Verify a dispatch signature without leaking timing information."""
    if not secret or not signature:
        return False
    expected = sign_browser_dispatch(secret, payload)
    return hmac.compare_digest(expected, signature)


def domain_matches(hostname: str, rule: str) -> bool:
    host = hostname.lower().rstrip(".")
    allowed = rule.strip().lower().rstrip(".")
    if not host or not allowed:
        return False
    if allowed == "*":
        return True
    if allowed.startswith("*."):
        suffix = allowed[1:]
        return host.endswith(suffix) and host != allowed[2:]
    return host == allowed


def _host_resolves_publicly(hostname: str) -> bool:
    try:
        literal = ipaddress.ip_address(hostname)
        return literal.is_global
    except ValueError:
        pass

    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror):
        return False
    addresses: set[str] = set()
    for record in records:
        try:
            addresses.add(str(ipaddress.ip_address(record[4][0])))
        except ValueError:
            return False
    return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)


def is_allowed_url(raw_url: str, allowed_domains: list[str]) -> bool:
    """Allow only HTTP(S) URLs on configured public hosts; fail closed on DNS errors."""
    try:
        parsed = urlsplit(raw_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        return False
    if port is not None and not (1 <= port <= 65535):
        return False
    host = hostname.lower().rstrip(".")
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
        or host == "metadata.google.internal"
    ):
        return False
    if not any(domain_matches(host, rule) for rule in allowed_domains):
        return False
    return _host_resolves_publicly(host)


def validate_browser_actions(actions: Any) -> list[dict[str, Any]]:
    """Validate a bounded, explicit browser action sequence."""
    if not isinstance(actions, list) or not actions or len(actions) > MAX_ACTIONS:
        raise BrowserPolicyError(f"actions must be a list containing 1 to {MAX_ACTIONS} items")
    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(actions):
        if not isinstance(raw, dict):
            raise BrowserPolicyError(f"action {index} must be an object")
        op = raw.get("op")
        if op not in SUPPORTED_ACTIONS:
            raise BrowserPolicyError(f"action {index} has unsupported op")
        action = dict(raw)
        if op == "navigate":
            if not isinstance(action.get("url"), str) or len(action["url"]) > 2048:
                raise BrowserPolicyError(f"action {index} requires a valid url string")
        elif op in {"click", "type", "press", "wait_for"}:
            if not isinstance(action.get("selector"), str) or not action["selector"].strip():
                raise BrowserPolicyError(f"action {index} requires a selector")
            if len(action["selector"]) > 1000:
                raise BrowserPolicyError(f"action {index} selector is too long")
        if op == "type":
            if not isinstance(action.get("text"), str) or len(action["text"]) > 20_000:
                raise BrowserPolicyError(f"action {index} requires text no longer than 20000 characters")
        if op == "press" and (
            not isinstance(action.get("key"), str) or len(action["key"]) > 40
        ):
            raise BrowserPolicyError(f"action {index} requires a key string")
        if op == "wait_for" and action.get("state", "visible") not in {
            "attached", "detached", "visible", "hidden"
        }:
            raise BrowserPolicyError(f"action {index} has invalid wait state")
        if op == "inspect":
            max_chars = action.get("max_chars", 5000)
            if not isinstance(max_chars, int) or not 1 <= max_chars <= MAX_TEXT_CHARS:
                raise BrowserPolicyError(f"action {index} max_chars must be between 1 and {MAX_TEXT_CHARS}")
        validated.append(action)
    return validated


class BrowserWorker:
    """Execute explicit browser actions in a persistent public-web profile."""

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        profile_dir: str | None = None,
        headless: bool | None = None,
        executable_path: str | None = None,
        page_session_factory: Callable[[], Any] | None = None,
    ) -> None:
        raw_domains = os.getenv("BRAIN_BROWSER_ALLOWED_DOMAINS", "") if allowed_domains is None else ",".join(allowed_domains)
        self.allowed_domains = [item.strip() for item in raw_domains.split(",") if item.strip()]
        # General public-web browsing is the default. Explicit domain rules remain
        # available for deployments that intentionally want a narrower scope.
        if not self.allowed_domains:
            self.allowed_domains = ["*"]
        self.profile_dir = Path(profile_dir or os.getenv("BRAIN_BROWSER_PROFILE_DIR", "./workspace/browser-profile"))
        raw_headless = os.getenv("BRAIN_BROWSER_HEADLESS", "true").lower()
        self.headless = (raw_headless not in {"0", "false", "no"}) if headless is None else headless
        self.executable_path = executable_path or os.getenv("BRAIN_BROWSER_EXECUTABLE_PATH") or None
        self.page_session_factory = page_session_factory

    async def execute(self, actions: Any, owner_approved: bool = False) -> dict[str, Any]:
        validated = validate_browser_actions(actions)
        if any(action["op"] in MUTATING_ACTIONS for action in validated) and not owner_approved:
            raise BrowserPolicyError("mutating browser actions require explicit owner approval")
        results: list[dict[str, Any]] = []
        async with self._page_session() as page:
            for index, action in enumerate(validated):
                try:
                    result = await self._run_action(page, action)
                    results.append({"index": index, "op": action["op"], "ok": True, "result": result})
                except Exception as exc:
                    results.append({
                        "index": index,
                        "op": action["op"],
                        "ok": False,
                        "error": type(exc).__name__,
                        "message": str(exc)[:500],
                    })
                    break
        return {
            "worker": "browser_worker",
            "status": "succeeded" if len(results) == len(validated) and all(item["ok"] for item in results) else "failed",
            "completed_actions": sum(1 for item in results if item["ok"]),
            "requested_actions": len(validated),
            "results": results,
        }

    @asynccontextmanager
    async def _page_session(self) -> AsyncIterator[Any]:
        if self.page_session_factory is not None:
            async with self.page_session_factory() as page:
                yield page
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Browser runtime is not installed. Install Brain's optional browser dependencies."
            ) from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            launch_options: dict[str, Any] = {
                "headless": self.headless,
                "accept_downloads": False,
                "args": ["--disable-dev-shm-usage", "--no-first-run"],
            }
            if self.executable_path:
                launch_options["executable_path"] = self.executable_path
            context = await playwright.chromium.launch_persistent_context(
                str(self.profile_dir), **launch_options
            )

            async def route_request(route: Any) -> None:
                url = route.request.url
                if url.startswith(("data:", "blob:", "about:")):
                    await route.continue_()
                elif is_allowed_url(url, self.allowed_domains):
                    await route.continue_()
                else:
                    await route.abort("blockedbyclient")

            await context.route("**/*", route_request)
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                page.set_default_timeout(8000)
                yield page
            finally:
                await context.close()

    def _assert_current_page_allowed(self, page: Any) -> None:
        current_url = page.url
        if current_url == "about:blank":
            return
        if not is_allowed_url(current_url, self.allowed_domains):
            raise BrowserPolicyError("current page is outside the configured public-domain allowlist")

    async def _run_action(self, page: Any, action: dict[str, Any]) -> dict[str, Any]:
        op = action["op"]
        if op != "navigate" and is_restricted_consumer_ai_url(page.url):
            raise BrowserPolicyError(
                "Automated interaction with consumer ChatGPT/Gemini chat pages is disabled. "
                "Use a provider-supported integration; Brain will not script chat submission "
                "or extract consumer-site output."
            )
        if op == "navigate":
            if not is_allowed_url(action["url"], self.allowed_domains):
                raise BrowserPolicyError("navigation URL is outside the configured public-domain allowlist")
            response = await page.goto(action["url"], wait_until="domcontentloaded", timeout=20_000)
            self._assert_current_page_allowed(page)
            return {
                "url": page.url,
                "title": await page.title(),
                "http_status": getattr(response, "status", None),
            }
        if op == "inspect":
            self._assert_current_page_allowed(page)
            return {
                "url": page.url,
                "title": await page.title(),
                "text": (await page.locator("body").inner_text())[: action.get("max_chars", 5000)],
            }
        if op in MUTATING_ACTIONS or op in {"wait_for", "screenshot"}:
            self._assert_current_page_allowed(page)
        if op == "click":
            await page.locator(action["selector"]).click(timeout=action.get("timeout_ms", 5000))
            return {"clicked": True}
        if op == "type":
            locator = page.locator(action["selector"])
            if action.get("clear", True):
                await locator.fill(action["text"], timeout=action.get("timeout_ms", 5000))
            else:
                await locator.press_sequentially(action["text"], timeout=action.get("timeout_ms", 5000))
            return {"typed": True, "characters": len(action["text"])}
        if op == "press":
            await page.locator(action["selector"]).press(action["key"], timeout=action.get("timeout_ms", 5000))
            return {"pressed": action["key"]}
        if op == "wait_for":
            await page.locator(action["selector"]).wait_for(
                state=action.get("state", "visible"),
                timeout=action.get("timeout_ms", 5000),
            )
            return {"found": True, "state": action.get("state", "visible")}
        if op == "screenshot":
            image = await page.screenshot(full_page=False, animations="disabled")
            return {"mime_type": "image/png", "base64": base64.b64encode(image).decode("ascii")}
        raise BrowserPolicyError(f"unsupported browser action: {op}")
