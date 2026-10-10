"""Regression checks for the mission-free chat runtime workflow configuration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_runtime_check_uses_configured_gemini_provider_not_deepseek():
    workflow = (
        ROOT / ".github" / "workflows" / "brain-chat-runtime-check.yml"
    ).read_text(encoding="utf-8")

    assert "secrets.BRAIN_AI_API_KEY" in workflow
    assert "generativelanguage.googleapis.com/v1beta/openai" in workflow
    assert "gemini-3.5-flash-lite" in workflow
    assert "DEEPSEEK_API_KEY" not in workflow
    assert "api.deepseek.com" not in workflow
    assert "deepseek-chat" not in workflow


def test_chat_runtime_check_authenticates_baseline_and_followup_mission_reads():
    workflow = (
        ROOT / ".github" / "workflows" / "brain-chat-runtime-check.yml"
    ).read_text(encoding="utf-8")

    assert 'auth_headers = {"X-Brain-API-Key": os.environ["BRAIN_CONTROL_API_KEY"]}' in workflow
    assert 'client.get("/missions", headers=auth_headers)' in workflow
