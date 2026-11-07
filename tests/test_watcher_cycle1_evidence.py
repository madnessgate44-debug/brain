"""Contract tests for the issue #240 cycle-1 evidence artifacts.

These guard the recorded facts, not a live service. They fail if an artifact
loses the identifiers a reviewer needs to re-check the claim, or if a secret
value ever appears in one.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIVE_STATE = ROOT / "watcher" / "channel" / "live-state-2026-11-01.md"
SCORECARD = ROOT / "watcher" / "scorecard" / "forge-vs-claude-code-cycle-1.md"
QUEUE = ROOT / "watcher" / "hub" / "work-queue-2026-11-01.md"
SHADOW_AUDIT = ROOT / "shadow" / "audit-240-cycle1-2026-11-01.md"

SECRET_PATTERN = re.compile(
    r"(gAAAAA|sk-[A-Za-z0-9]|ghp_|gho_|ghu_|github_pat_|AIza|AQ\.[A-Za-z0-9_-]{40,}|BEGIN [A-Z ]*PRIVATE KEY)"
)


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_live_state_names_the_active_receiver_and_its_run():
    text = _read(LIVE_STATE)
    # The live automation and the event run it produced.
    assert "017c4b55-8904-47b0-863e-a36ca4df406a" in text
    assert "f30b6fcb-e3f6-45f3-a730-28bf2ab6071e" in text
    # The receipt was autonomous, not human-opened.
    assert "trigger_source" in text and "event" in text
    # The deleted draft is named so the correction is auditable.
    assert "7aea2400-61ef-42dd-8b6f-c4de5266bf9f" in text


def test_live_state_records_nonzero_cost_as_an_owner_decision():
    text = _read(LIVE_STATE)
    assert "0.0012309304" in text
    assert "owner" in text.lower() and "spend" in text.lower()


def test_scorecard_pins_the_inspected_firstborn_commit_and_all_rows():
    text = _read(SCORECARD)
    assert "36a9916e900f9019ef1c46d95d08985c38fbac9d" in text
    # Every cycle-0 row is re-checked and every row carries a file:line citation.
    assert text.count("**CONFIRMED") >= 20
    assert re.search(r"src/[\w./-]+\.ts:\d+", text), "no path:line citation found"


def test_scorecard_does_not_promote_runtime_rows_without_a_run():
    text = _read(SCORECARD)
    assert "E2E UNVERIFIED" in text
    assert "No Forge capability is promoted to E2E VERIFIED" in text


def test_work_queue_uses_the_agreed_status_vocabulary():
    text = _read(QUEUE)
    for status in ("VERIFIED", "QUEUED", "BLOCKED", "PARTIAL"):
        assert status in text, f"queue is missing status {status}"
    # A resume point and exactly one owner question are required by the addendum.
    assert "Resume point" in text
    assert text.lower().count("owner question") == 1


def test_shadow_audit_is_recorded():
    text = _read(SHADOW_AUDIT)
    assert "VERIFIED" in text
    assert "Secret sweep" in text


def test_no_secret_value_appears_in_any_cycle1_artifact():
    for path in (LIVE_STATE, SCORECARD, QUEUE, SHADOW_AUDIT):
        text = _read(path)
        match = SECRET_PATTERN.search(text)
        assert match is None, f"possible secret in {path.relative_to(ROOT)}: {match.group(0)!r}"
