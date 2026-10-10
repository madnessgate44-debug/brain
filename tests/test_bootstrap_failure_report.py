import json

from scripts.write_bootstrap_failure_report import (
    build_bootstrap_failure_report,
    ensure_failure_reports,
    is_structurally_valid_report,
    render_failure_markdown,
)


BASE_ENV = {
    "GITHUB_REPOSITORY": "madnessgate44-debug/brain",
    "GITHUB_SHA": "abc123",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REF_NAME": "main",
    "GITHUB_RUN_ID": "12345",
    "GITHUB_RUN_ATTEMPT": "2",
    "GITHUB_WORKFLOW": "Brain Chat Company Workflow",
    "GITHUB_EVENT_NAME": "issues",
    "GITHUB_SERVER_URL": "https://github.com",
    "RUNNER_OS": "Linux",
    "CHECKOUT_OUTCOME": "success",
    "SETUP_PYTHON_OUTCOME": "success",
    "INSTALL_OUTCOME": "success",
    "LOCK_OUTCOME": "success",
    "RUN_OUTCOME": "success",
}


def test_checkout_failure_includes_exact_revision_and_failed_step():
    env = {**BASE_ENV, "CHECKOUT_OUTCOME": "failure"}
    report = build_bootstrap_failure_report(
        env,
        {"action": "opened", "issue": {"number": 154}},
    )

    assert report["runtime"]["commit_sha"] == "abc123"
    assert report["runtime"]["ref"] == "refs/heads/main"
    assert report["runtime"]["ref_name"] == "main"
    assert report["runtime"]["run_id"] == "12345"
    assert report["runtime"]["run_attempt"] == "2"
    assert report["runtime"]["issue_number"] == 154
    assert report["runtime"]["event_action"] == "opened"
    assert report["failed_steps"] == [{"step": "checkout", "outcome": "failure"}]
    assert report["impact"]["repository_mutation_status"].startswith("UNKNOWN")
    assert report["impact"]["tests_status"].startswith("UNKNOWN")


def test_mission_runner_failure_is_named_explicitly():
    report = build_bootstrap_failure_report(
        {**BASE_ENV, "RUN_OUTCOME": "failure"},
        {"action": "edited", "issue": {"number": 154}},
    )

    assert report["failed_steps"] == [{"step": "mission_runner", "outcome": "failure"}]
    assert report["status"] == "FAILED"
    assert report["impact"]["success_claimed"] is False


def test_missing_issue_payload_fields_do_not_break_report_generation():
    report = build_bootstrap_failure_report(BASE_ENV, {})

    assert report["runtime"]["issue_number"] is None
    assert report["runtime"]["event_action"] is None
    assert report["runtime"]["commit_sha"] == "abc123"
    assert report["failed_steps"] == []


def test_successful_bootstrap_has_no_failed_steps():
    report = build_bootstrap_failure_report(BASE_ENV, {"action": "opened"})

    assert report["failed_steps"] == []
    assert all(value == "success" for value in report["step_outcomes"].values())


def test_report_never_copies_secret_values():
    secret = "do-not-leak-this-token"
    env = {**BASE_ENV, "BRAIN_GITHUB_TOKEN": secret, "BRAIN_GITHUB_ACTIONS_TOKEN": secret}
    report = build_bootstrap_failure_report(env, {"issue": {"number": 154}})
    serialized = json.dumps(report) + render_failure_markdown(report)

    assert secret not in serialized
    assert "BRAIN_GITHUB_TOKEN" not in serialized
    assert "BRAIN_GITHUB_ACTIONS_TOKEN" not in serialized


def test_ensure_failure_reports_writes_json_and_markdown(tmp_path):
    env = {**BASE_ENV, "CHECKOUT_OUTCOME": "failure"}
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"

    created = ensure_failure_reports(
        env,
        {"action": "opened", "issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    report = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert report["runtime"]["issue_number"] == 154
    assert "Commit SHA: abc123" in markdown
    assert "checkout: failure" in markdown
    assert "Mutation status: UNKNOWN" in markdown
    assert "Tests status: UNKNOWN" in markdown


def test_existing_mission_reports_are_never_overwritten(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    markdown_path.write_text("existing mission report", encoding="utf-8")
    json_path.write_text('{"status": "PASS", "report": "mission evidence"}', encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is False
    assert markdown_path.read_text(encoding="utf-8") == "existing mission report"
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "PASS"


def test_ensure_failure_reports_repairs_malformed_json_and_preserves_markdown(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    markdown_path.write_text("pre-existing markdown report", encoding="utf-8")
    json_path.write_text("{not-valid-json", encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert markdown_path.read_text(encoding="utf-8") == "pre-existing markdown report"
    repaired = json.loads(json_path.read_text(encoding="utf-8"))
    assert repaired["status"] == "FAILED"
    assert repaired["failure"]["type"] == "WorkflowBootstrapFailure"


def test_ensure_failure_reports_repairs_empty_json_and_preserves_markdown(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    markdown_path.write_text("pre-existing markdown report", encoding="utf-8")
    json_path.write_text("   \n ", encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert markdown_path.read_text(encoding="utf-8") == "pre-existing markdown report"
    repaired = json.loads(json_path.read_text(encoding="utf-8"))
    assert repaired["status"] == "FAILED"


def test_ensure_failure_reports_renders_missing_markdown_from_valid_json(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    valid_report = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(valid_report)
    json_path.write_text(original_json, encoding="utf-8")
    assert not markdown_path.exists()

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert json_path.read_text(encoding="utf-8") == original_json
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Brain execution failure report" in markdown
    assert "Commit SHA: abc123" in markdown


def test_ensure_failure_reports_repairs_empty_markdown_preserves_valid_json(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    valid_report = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(valid_report)
    json_path.write_text(original_json, encoding="utf-8")
    markdown_path.write_text("   \n ", encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert json_path.read_text(encoding="utf-8") == original_json
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Brain execution failure report" in markdown
    assert "Commit SHA: abc123" in markdown


def test_ensure_failure_reports_repairs_invalid_utf8_markdown_preserves_valid_json(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    valid_report = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(valid_report)
    json_path.write_text(original_json, encoding="utf-8")
    markdown_path.write_bytes(b"\xff\xfe\x00\x01")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert json_path.read_text(encoding="utf-8") == original_json
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Brain execution failure report" in markdown
    assert "Commit SHA: abc123" in markdown


def test_ensure_failure_reports_preserves_valid_json_and_markdown(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    valid_report = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(valid_report)
    json_path.write_text(original_json, encoding="utf-8")
    valid_markdown = render_failure_markdown(valid_report)
    markdown_path.write_text(valid_markdown, encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is False
    assert json_path.read_text(encoding="utf-8") == original_json
    assert markdown_path.read_text(encoding="utf-8") == valid_markdown


def test_workflow_wires_helper_and_retains_checkout_safe_fallback():
    from pathlib import Path

    workflow = Path(".github/workflows/brain-chat-company-workflow.yml").read_text(encoding="utf-8")

    assert "python3 scripts/write_bootstrap_failure_report.py" in workflow
    assert "Checkout itself can fail" in workflow
    assert "python3 - <<" in workflow
    assert "GITHUB_SHA" in workflow
    assert '"ref": os.environ.get("GITHUB_REF"' in workflow
    assert "GITHUB_REF_NAME" in workflow
    assert "failed_steps" in workflow
    assert "GITHUB_EVENT_PATH" in workflow


def test_inline_fallback_runs_without_checked_out_helper(tmp_path):
    import os
    import subprocess
    import sys
    import textwrap
    from pathlib import Path

    workflow = Path(".github/workflows/brain-chat-company-workflow.yml").read_text(encoding="utf-8")
    lines = workflow.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "python3 - <<'PY'")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    script = textwrap.dedent("\n".join(lines[start + 1 : end]))

    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps({"action": "opened", "issue": {"number": 154}}),
        encoding="utf-8",
    )
    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
        if key in os.environ
    }
    env.update({
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_REPOSITORY": "madnessgate44-debug/brain",
        "GITHUB_SHA": "checkout-sha",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_NAME": "main",
        "GITHUB_RUN_ID": "98765",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": "Brain Chat Company Workflow",
        "GITHUB_EVENT_NAME": "issues",
        "GITHUB_SERVER_URL": "https://github.com",
        "RUNNER_OS": "Linux",
        "CHECKOUT_OUTCOME": "failure",
        "SETUP_PYTHON_OUTCOME": "success",
        "INSTALL_OUTCOME": "skipped",
        "LOCK_OUTCOME": "skipped",
        "RUN_OUTCOME": "skipped",
    })

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "brain-company-result.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "brain-company-result.md").read_text(encoding="utf-8")
    assert report["runtime"]["commit_sha"] == "checkout-sha"
    assert report["runtime"]["issue_number"] == 154
    assert report["failed_steps"] == [{"step": "checkout", "outcome": "failure"}]
    assert report["impact"]["repository_mutation_status"].startswith("UNKNOWN")
    assert "Commit SHA: checkout-sha" in markdown


def test_ensure_failure_reports_repairs_empty_json_object(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    markdown_path.write_text("pre-existing markdown report", encoding="utf-8")
    json_path.write_text("{}", encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert markdown_path.read_text(encoding="utf-8") == "pre-existing markdown report"
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "FAILED"


def test_ensure_failure_reports_repairs_invalid_utf8_json(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    markdown_path.write_text("pre-existing markdown report", encoding="utf-8")
    json_path.write_bytes(b"\\xff\\xfe")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert markdown_path.read_text(encoding="utf-8") == "pre-existing markdown report"
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "FAILED"


def test_ensure_failure_reports_repairs_zero_byte_markdown_preserves_valid_json(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"
    valid_report = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(valid_report)
    json_path.write_text(original_json, encoding="utf-8")
    markdown_path.write_bytes(b"")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    assert json_path.read_text(encoding="utf-8") == original_json
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Brain execution failure report" in markdown
    assert "Commit SHA: abc123" in markdown


# --- New Regression Tests for Iteration 8 Mandate ---


def test_status_only_json_with_existing_markdown_is_rejected_and_repaired(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"

    existing_md = "# Original Mission Summary\nAll tasks completed successfully."
    markdown_path.write_text(existing_md, encoding="utf-8")

    # Status-only JSON object (syntactically valid JSON, but structurally incomplete)
    json_path.write_text('{"status":"PASS"}', encoding="utf-8")

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is True
    # Existing Markdown must be preserved byte-for-byte
    assert markdown_path.read_text(encoding="utf-8") == existing_md
    # Incomplete status-only JSON must be replaced with conservative structured failure report
    repaired = json.loads(json_path.read_text(encoding="utf-8"))
    assert repaired["status"] == "FAILED"
    assert repaired["failure"]["type"] == "WorkflowBootstrapFailure"


def test_valid_fallback_report_preservation(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"

    fallback_data = build_bootstrap_failure_report(BASE_ENV, {"issue": {"number": 154}})
    original_json = json.dumps(fallback_data)
    valid_md = render_failure_markdown(fallback_data)

    json_path.write_text(original_json, encoding="utf-8")
    markdown_path.write_text(valid_md, encoding="utf-8")

    assert is_structurally_valid_report(fallback_data) is True

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is False
    assert json_path.read_text(encoding="utf-8") == original_json
    assert markdown_path.read_text(encoding="utf-8") == valid_md


def test_valid_mission_report_preservation(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"

    mission_data = {
        "status": "PASS",
        "base_commit": "abc123",
        "branch": "brain/mission-1",
        "stage_outcomes": {"developer": "success", "code_reviewer": "success"},
        "test_results": {"status": "PASS", "executed": True},
        "pull_request": {"url": "https://github.com/pull/1"},
        "post_pr_verification": {"passed": True},
        "report": "Mission completed successfully with all evidence."
    }
    original_json = json.dumps(mission_data)
    existing_md = "# Mission Success Report\nAll requirements met."

    json_path.write_text(original_json, encoding="utf-8")
    markdown_path.write_text(existing_md, encoding="utf-8")

    assert is_structurally_valid_report(mission_data) is True

    created = ensure_failure_reports(
        BASE_ENV,
        {"issue": {"number": 154}},
        markdown_path=markdown_path,
        json_path=json_path,
    )

    assert created is False
    assert json_path.read_text(encoding="utf-8") == original_json
    assert markdown_path.read_text(encoding="utf-8") == existing_md


def test_malformed_and_incomplete_json_repair_variants(tmp_path):
    markdown_path = tmp_path / "brain-company-result.md"
    json_path = tmp_path / "brain-company-result.json"

    existing_md = "# Existing Notes\nDo not overwrite me."

    for bad_json in [
        '{"status":""}',
        '{"status": "FAILED"}',
        '{"message": "missing status and context"}',
        '[]',
        '"just a string"',
    ]:
        markdown_path.write_text(existing_md, encoding="utf-8")
        json_path.write_text(bad_json, encoding="utf-8")

        created = ensure_failure_reports(
            BASE_ENV,
            {"issue": {"number": 154}},
            markdown_path=markdown_path,
            json_path=json_path,
        )

        assert created is True
        assert markdown_path.read_text(encoding="utf-8") == existing_md
        repaired = json.loads(json_path.read_text(encoding="utf-8"))
        assert repaired["status"] == "FAILED"
