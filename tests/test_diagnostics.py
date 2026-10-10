import json

from brain.company.diagnostics import failure_report, write_failure_artifacts


def test_failure_report_includes_traceback_timeline_and_runtime(monkeypatch):
    secret = "never-print-this-token"
    monkeypatch.setenv("BRAIN_GITHUB_TOKEN", secret)
    try:
        raise RuntimeError(f"GitHub request failed with Authorization: Bearer {secret}")
    except RuntimeError as exc:
        report = failure_report(
            exc,
            mission={"repository": "owner/repo", "objective": f"audit using {secret}"},
            events=[{"stage": "repository_read", "status": "FAIL", "detail": "HTTP 403"}],
            started_at="2026-10-10T00:00:00+00:00",
        )
    rendered = json.dumps(report)
    assert report["status"] == "FAILED"
    assert report["failure"]["type"] == "RuntimeError"
    assert "traceback" in report["failure"]
    assert report["timeline"][0]["stage"] == "repository_read"
    assert secret not in rendered
    assert report["credential_diagnostics"]["BRAIN_GITHUB_TOKEN_configured"] is True


def test_failure_artifacts_write_markdown_and_json(tmp_path):
    try:
        raise ValueError("bad state")
    except ValueError as exc:
        md = tmp_path / "failure.md"
        js = tmp_path / "failure.json"
        write_failure_artifacts(exc, report_path=md, json_path=js, events=[])
    assert "Full traceback" in md.read_text()
    assert json.loads(js.read_text())["failure"]["type"] == "ValueError"



def test_checkpoint_sanitizer_redacts_secrets_recursively(monkeypatch):
    from brain.company.diagnostics import sanitize_diagnostic_value

    secret = "checkpoint-secret-value"
    monkeypatch.setenv("BRAIN_GITHUB_TOKEN", secret)
    value = sanitize_diagnostic_value({
        "role_outputs": [{"text": f"authorization bearer {secret}"}],
        "metadata": {"api_key": secret},
    })
    rendered = json.dumps(value)
    assert secret not in rendered
    assert "[REDACTED]" in rendered
