import json

from scripts.write_bootstrap_failure_report import (
    build_bootstrap_failure_report,
    ensure_failure_reports,
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
