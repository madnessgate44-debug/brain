"""Real Chromium smoke test for a compatible Linux browser host.

This test launches Playwright Chromium, navigates to a public test site, and inspects
the resulting page. It does not test authenticated sessions or the ChatGPT mobile bridge.
"""

import pytest

from brain.runtime.workers.browser_worker import BrowserWorker


@pytest.mark.asyncio
async def test_live_chromium_navigates_and_inspects_public_page(tmp_path, monkeypatch):
    pytest.importorskip("playwright.async_api")
    monkeypatch.setenv("BRAIN_BROWSER_ALLOWED_DOMAINS", "example.com")
    worker = BrowserWorker(
        allowed_domains=["example.com"],
        profile_dir=str(tmp_path / "browser-profile"),
        headless=True,
    )

    result = await worker.execute([
        {"op": "navigate", "url": "https://example.com/"},
        {"op": "inspect", "max_chars": 1000},
    ])

    assert result["status"] == "succeeded", result
    assert result["completed_actions"] == 2
    navigation = result["results"][0]["result"]
    assert navigation["url"].startswith("https://example.com/")
    assert navigation["http_status"] == 200
    inspection = result["results"][1]["result"]
    assert inspection["title"] == "Example Domain"
    assert "documentation examples" in inspection["text"].casefold()
