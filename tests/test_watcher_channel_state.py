"""Contract guard for the issue #240 channel state record (2026-11-01).

The recorded channel verdict on issue #240 claimed "nothing is enabled", but a live
probe found two issue-#240 automations still present. Both were deleted. These
assertions protect the corrected record from drifting back into a claim that no
automation was ever left running, or into anything that looks enabled.
"""

import json
from pathlib import Path

import pytest

STATE = Path(__file__).resolve().parents[1] / "watcher" / "channel" / "state-2026-11-01.json"


@pytest.fixture(scope="module")
def state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def test_state_file_exists():
    assert STATE.is_file(), f"missing channel state record: {STATE}"


def test_no_issue_240_automation_left_enabled(state):
    assert state["automations_left_enabled"] == []
    for automation in state["issue_240_automations"]:
        assert automation["disposition"].startswith("DELETED") or automation[
            "disposition"
        ].startswith("ALREADY DELETED")
        assert automation["post_delete_get_http"] == 404


def test_record_acknowledges_two_automations_survived_the_earlier_verdict(state):
    ids = {automation["id"] for automation in state["issue_240_automations"]}
    assert "017c4b55-8904-47b0-863e-a36ca4df406a" in ids
    assert "c2521706-7a97-4d64-b191-0b29ddc10682" in ids
    heartbeat = next(
        a for a in state["issue_240_automations"] if a["id"] == "c2521706-7a97-4d64-b191-0b29ddc10682"
    )
    assert heartbeat["state_before"] == "ACTIVE"
    assert heartbeat["enabled_before"] is True
    assert heartbeat["trigger_type"] == "cron"
    assert any(run["trigger_source"] == "cron" for run in heartbeat["observed_runs"])


def test_account_is_personal_workspace_without_git_claims(state):
    assert state["account"]["kind"] == "personal-workspace"
    assert state["account"]["git_claims"] == []
    assert state["account"]["budgets_http"] == 400


def test_only_preexisting_automations_remain(state):
    remaining = {automation["id"] for automation in state["pre_existing_automations"]}
    assert remaining == {
        "aa4ae120-c4bd-4cf5-9762-ddf5638109c5",
        "216fd7ae-94a1-4779-a3cd-e95b6053166b",
    }


def test_recreate_is_gated_on_owner_spend_decision(state):
    assert state["verdict"] == "REJECTED for activation"
    assert "owner spend decision" in state["recreate_condition"]
    assert "team org" in state["recreate_condition"]
