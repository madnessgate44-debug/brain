"""Real Chromium smoke test for a compatible Linux browser host.

The normal unit suite does not require the optional Playwright dependency. The manual
browser-runtime-smoke workflow installs Chromium and executes this test for real.
"""

import pytest

from brain.runtime.workers.browser_worker import BrowserWorker


@pytest.mark.asyncio
async def test_live_chromium_launches_and_inspects_blank_page(tmp_path, monkeypatch):
    pytest.importorskip("playwright.async_api")
    monkeypatch.setenv("BRAIN_BROWSER_ALLOWED_DOMAINS", "example.com")
    worker = BrowserWorker(
        allowed_domains=["example.com"],
        profile_dir=str(tmp_path / "browser-profile"),
        headless=True,
    )

    result = await worker.execute([{"op": "inspect", "max_chars": 100}])

    assert result["status"] == "succeeded", result
    assert result["completed_actions"] == 1
    assert result["results"][0]["result"]["url"] == "about:blank"
