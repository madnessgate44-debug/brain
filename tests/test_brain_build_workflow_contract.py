"""Contract tests for the owner-gated cross-repository build workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "brain-build.yml"


def test_cross_repository_build_workflow_has_exact_intake_and_retry():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "issues:" in workflow and "types: [opened]" in workflow
    assert "issue_comment:" in workflow and "types: [created]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.event.comment.body == '/brain retry'" in workflow
    assert "startsWith(github.event.comment.body, '/brain retry')" not in workflow
    assert "fromJSON(" in workflow and "format('{0}{1}'" in workflow
    assert r"(?=\s|$)" in workflow


def test_cross_repository_build_workflow_enforces_owner_and_single_explicit_token():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "github.event.comment.user.login == github.repository_owner" in workflow
    assert "github.event.issue.user.login == github.repository_owner" in workflow
    assert 'target.split("/", 1)[0].casefold() != owner.casefold()' in workflow
    assert "secrets.BRAIN_GITHUB_TOKEN || github.token" not in workflow
    assert "token: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    assert "persist-credentials: false" in workflow


def test_cross_repository_agent_uses_a_separate_workspace_and_is_pinned():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "mini-swe-agent==1.17.5" in workflow
    assert '"environment_class": "docker"' in workflow
    assert "brain-build-sandbox:local" in workflow
    assert "Prepare isolated agent workspace" in workflow
    assert "git -c core.hooksPath=/dev/null archive --format=tar HEAD" in workflow
    assert 'f"{os.environ[\'AGENT_WORKSPACE\']}:/workspace"' in workflow
    assert 'f"{os.environ[\'GITHUB_WORKSPACE\']}:/workspace"' not in workflow
    assert '(":ro" if os.environ["MISSION_COMMAND"] == "audit" else "")' in workflow
    assert "Reconstruct candidate diff in a trusted temporary repository" in workflow
    assert "rsync -a --delete --exclude='/.git'" in workflow
    assert 'git -C "$diff_workspace" -c core.hooksPath=/dev/null add -f -A' in workflow
    assert "git -c core.hooksPath=/dev/null apply --check /tmp/brain-build.patch" in workflow
    assert 'git -c core.hooksPath=/dev/null -c "http.extraheader=AUTHORIZATION: basic' in workflow
    assert "GH_TOKEN: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    agent_step = workflow.split("- name: Run bounded coding agent without GitHub credentials in sandbox", 1)[1].split("- name: Reconstruct candidate diff", 1)[0]
    assert "OPENAI_API_KEY: ${{ secrets.BRAIN_AI_API_KEY }}" in agent_step
    assert "BRAIN_GITHUB_TOKEN" not in agent_step
    assert "Never merge, deploy, or push." in agent_step


def test_secret_scan_handles_deleted_renamed_and_space_containing_paths():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '"--no-renames"' in workflow
    assert '"--name-only", "--no-renames", "-z", "HEAD"' in workflow
    assert '["git", "show", f"HEAD:{name}"]' in workflow
    assert "target.write_bytes(blob.stdout)" in workflow
    assert "Prepared changed-file scan input, including base contents for deleted paths" in workflow
    assert "zricethezav/gitleaks:v8.24.2" in workflow
    assert "--redact --exit-code 1" in workflow
    assert "tar --null -T -" not in workflow


def test_changed_file_and_warning_summaries_preserve_names():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "git diff --cached --name-only -z" in workflow
    assert "json.dumps(p[:8], ensure_ascii=True)" in workflow
    assert "paste -sd';' -" in workflow
    assert "tr '\\\\n'" not in workflow


def test_project_check_reporting_distinguishes_tests_smoke_and_none():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "BRAIN_CHECK_TYPE=tests" in workflow
    assert "BRAIN_CHECK_TYPE=smoke" in workflow
    assert "BRAIN_CHECK_TYPE=none" in workflow
    assert 'echo "check_type=$check_type" >> "$GITHUB_OUTPUT"' in workflow
    assert 'tests) check_summary="tests passed"' in workflow
    assert 'smoke) check_summary="smoke check passed; no tests detected"' in workflow
    assert 'none) check_summary="no tests/build/lint check configured"' in workflow
    assert "- Checks: ${check_summary}; gitleaks passed." in workflow
    assert "- Checks: ${check_summary}; gitleaks PASS" in workflow


def test_workflow_reports_failures_without_secrets_or_provider_bodies():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "report_failure:" in workflow
    assert "always()" in workflow
    assert "needs.prepare.result == 'failure' || needs.mission.result == 'failure'" in workflow
    assert "permissions:\n      issues: write" in workflow
    assert "Workflow run: ${process.env.RUN_URL}" in workflow
    assert "This report intentionally excludes secrets and provider response bodies." in workflow


def test_whitespace_validation_is_a_controlled_warning():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "git -C \"$diff_workspace\" -c core.hooksPath=/dev/null diff --cached --check -- ." in workflow
    assert "Whitespace errors detected in candidate changes" in workflow
    assert 'echo "WARN: whitespace errors detected in candidate changes."' in workflow


def test_cross_repository_build_has_project_checks_and_protected_path_gate():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "Run project-aware checks" in workflow
    assert "python -m pytest -q" in workflow
    assert "npm test -- --run" in workflow
    assert "Static HTML checks" in workflow
    assert "Protected workflow, environment, deployment, or credential-related changes detected" in workflow
    assert "human review and merge required" in workflow


def test_empty_target_initialization_and_shared_queue_are_explicit():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "Initialize an empty target repository through the Contents API" in workflow
    assert "repos/$TARGET_REPOSITORY/contents/README.md" in workflow
    assert "Acquire shared model-workflow queue lease" in workflow
    assert "Release shared model-workflow queue lease" in workflow
    assert "heads/brain-company-workflow-lock" in workflow


def test_target_preflight_checks_only_permissions_the_build_workflow_needs():
    workflow_path = ROOT / ".github" / "workflows" / "brain-build-preflight.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "startsWith(github.event.issue.body, '/brain preflight')" in workflow
    assert "secrets.BRAIN_GITHUB_TOKEN" in workflow
    assert "Contents: write failed" in workflow
    assert "Pull requests: write failed" in workflow
    assert "Issues: write failed" in workflow
    assert "Actions:write and Workflows:write are not required" in workflow
    assert "BRAIN_MESHMESH_GITHUB_TOKEN" not in workflow


def test_provider_rate_limit_and_preview_evidence_are_bounded():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "retryDelay" in workflow
    assert 'MSWEA_GLOBAL_CALL_LIMIT: "14"' in workflow
    assert "Capture isolated mobile and desktop previews for static HTML" in workflow
    assert "mobile-390x844.png" in workflow
    assert "desktop-1280x800.png" in workflow
    assert "route.abort()" in workflow


def test_legacy_remote_test_runner_no_longer_falls_back_to_control_token():
    workflow = (ROOT / ".github" / "workflows" / "brain-task-runner.yml").read_text(encoding="utf-8")
    assert "secrets.BRAIN_GITHUB_TOKEN || github.token" not in workflow
    assert "token: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    assert "BRAIN_GITHUB_TOKEN is required for target-repository checkout" in workflow
    assert "types: [opened, edited]" not in workflow


def test_secret_scan_is_a_required_gate_before_pr_publication():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "zricethezav/gitleaks:v8.24.2" in workflow
    assert "--redact --exit-code 1" in workflow
    assert "steps.gitleaks.outcome == 'success'" in workflow
