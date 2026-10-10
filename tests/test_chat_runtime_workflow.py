from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_chat_runtime_check_authenticates_mission_baseline_requests():
    workflow = (ROOT / ".github/workflows/brain-chat-runtime-check.yml").read_text(
        encoding="utf-8"
    )

    assert 'auth_headers = {"X-Brain-API-Key": os.environ["BRAIN_CONTROL_API_KEY"]}' in workflow
    assert 'before = client.get("/missions", headers=auth_headers)' in workflow
    assert 'after = client.get("/missions", headers=auth_headers)' in workflow
    assert 'headers=auth_headers,' in workflow
    assert 'before = client.get("/missions")' not in workflow
    assert 'after = client.get("/missions")' not in workflow
