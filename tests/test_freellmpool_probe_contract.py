from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_freellmpool_probe_workflow_is_secret_free_and_restricted():
    workflow = (ROOT / ".github/workflows/freellm-probe.yml").read_text(encoding="utf-8")
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "ghcr.io/0xzr/freellmpool:0.13.0" in workflow
    assert "--tmpfs /home/freellmpool/.config/freellmpool" in workflow
    assert "secrets." not in workflow.lower()
    assert "--env" not in workflow
    assert "github.actor == 'madnessgate44-debug'" in workflow
    assert "pull_request.head.repo.full_name == github.repository" in workflow
    assert "/readyz" in (ROOT / "scripts/freellm_probe.py").read_text(encoding="utf-8")
