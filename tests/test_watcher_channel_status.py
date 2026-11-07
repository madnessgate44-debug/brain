"""Contract tests for the recorded Watcher channel state (issue #240).

These guard the *recorded* facts, not the live runtime: a future edit must not silently
flip the channel back to "enabled", drop the loop guard, or lose the rollback path.
Live state is re-read from the automation API by the session that makes a claim; this
test only proves the repository does not contradict itself.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "watcher" / "channel" / "status-2026-11-01.md"
AUDIT = ROOT / "shadow" / "audit-2026-11-01-channel-remediation.md"
REINSPECTION = ROOT / "watcher" / "reports" / "forge-parity-reinspection-2026-11-01.md"
PLAN = ROOT / "watcher" / "plans" / "first-plan-2026-11-01.md"

DISABLED_IDS = (
    "017c4b55-8904-47b0-863e-a36ca4df406a",
    "c2521706-7a97-4d64-b191-0b29ddc10682",
)


def test_channel_status_note_exists_and_records_both_automations_disabled():
    text = STATUS.read_text(encoding="utf-8")
    for automation_id in DISABLED_IDS:
        assert automation_id in text, f"missing automation id {automation_id}"
    assert "INACTIVE" in text
    assert "disabled_reason=manual" in text
    # The before/after must be labelled: the ACTIVE table is the pre-remediation state.
    assert "state at 06:17Z" in text
    assert "both INACTIVE" in text


def test_channel_status_note_keeps_the_loop_guard_and_rollback():
    text = STATUS.read_text(encoding="utf-8")
    assert "[TO-CHATGPT]" in text
    assert "!icontains(comment.body,'[TO-CHATGPT]')" in text
    assert "PATCH" in text and '"enabled": true' in text
    assert "DELETE /api/automation/v1/{id}" in text


def test_channel_status_note_names_the_untouched_standing_loop():
    text = STATUS.read_text(encoding="utf-8")
    assert "aa4ae120-c4bd-4cf5-9762-ddf5638109c5" in text
    assert "left ACTIVE" in text


def test_shadow_audit_rejects_activation_and_approves_remediation():
    text = AUDIT.read_text(encoding="utf-8")
    assert "REJECTED for activation" in text
    assert "approve" in text.lower()
    assert "disabled_reason=manual" in text
    # The live multi-session collision must stay recorded.
    assert "fbf81402" in text
    assert "re-enabled" in text


def test_reinspection_pins_the_forge_head_and_does_not_promote_to_e2e():
    text = REINSPECTION.read_text(encoding="utf-8")
    assert "36a9916e900f9019ef1c46d95d08985c38fbac9d" in text
    assert "madnessgate44-debug/Firstborn" in text
    assert "No E2E run was performed" in text
    # The one narrowed row must cite the fixed command registry.
    assert "AUTHORIZED_COMMANDS" in text


def test_plan_keeps_channel_first_and_marks_completed_rows():
    text = PLAN.read_text(encoding="utf-8")
    assert "Ahmed" in text
    assert "DONE" in text
    assert "ppt" in text


def test_no_secret_shaped_value_is_recorded_in_the_new_docs():
    import re

    pattern = re.compile(
        r"(gAAAAA|sk-[A-Za-z0-9]{10,}|ghp_|gho_|ghu_|github_pat_|AIza[0-9A-Za-z_-]{20,}|"
        r"AQ\.[A-Za-z0-9_-]{40,}|BEGIN [A-Z ]*PRIVATE KEY)"
    )
    for path in (STATUS, AUDIT, REINSPECTION, PLAN):
        assert not pattern.search(path.read_text(encoding="utf-8")), f"secret-shaped value in {path}"
