"""Contract tests for the owner-gated cross-repository build workflow."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "brain-build.yml"


def test_cross_repository_build_workflow_has_explicit_intake_and_retry():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "issues:" in workflow and "types: [opened]" in workflow
    assert "issue_comment:" in workflow and "types: [created]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.event.comment.body == '/brain retry'" in workflow
    assert "startsWith(github.event.comment.body, '/brain retry')" not in workflow
    assert all(x in workflow for x in ("fromJSON(", "format('{0}{1}'", r"(?=\s|$)"))


def test_cross_repository_build_workflow_enforces_owner_and_single_explicit_token():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "github.event.comment.user.login == github.repository_owner" in workflow
    assert "github.event.issue.user.login == github.repository_owner" in workflow
    assert 'target.split("/", 1)[0].casefold() != owner.casefold()' in workflow
    assert "secrets.BRAIN_GITHUB_TOKEN || github.token" not in workflow
    assert "token: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    assert "persist-credentials: false" in workflow


def test_cross_repository_agent_is_pinned_and_sandboxed_without_github_token():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "mini-swe-agent==1.17.5" in workflow
    assert '"environment_class": "docker"' in workflow
    assert "brain-build-sandbox:local" in workflow
    assert all(x in workflow for x in (
        "Prepare isolated agent workspace",
        "git -c core.hooksPath=/dev/null archive --format=tar HEAD",
        'f"{os.environ[\'AGENT_WORKSPACE\']}:/workspace"',
        '(":ro" if os.environ["MISSION_COMMAND"] == "audit" else "")',
        "Reconstruct candidate diff in a trusted temporary repository",
        "rsync -a --delete --exclude='/.git'",
        'git -C "$diff_workspace" -c core.hooksPath=/dev/null add -f -A',
        "git -c core.hooksPath=/dev/null apply --check /tmp/brain-build.patch",
        'git -c core.hooksPath=/dev/null -c "http.extraheader=AUTHORIZATION: basic',
    ))
    assert 'f"{os.environ[\'GITHUB_WORKSPACE\']}:/workspace"' not in workflow
    assert "GH_TOKEN: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    agent_step = workflow.split("- name: Run bounded coding agent without GitHub credentials in sandbox", 1)[1].split("- name: Reconstruct candidate diff", 1)[0]
    assert "OPENAI_API_KEY: ${{ secrets.BRAIN_AI_API_KEY }}" in agent_step
    assert "BRAIN_GITHUB_TOKEN" not in agent_step
    assert "Never merge, deploy, or push." in agent_step
    assert '2>&1 | tee "$final_log"' not in workflow and ' > "$final_log" 2>&1' in workflow
    assert "raw agent/provider output is suppressed from workflow logs" in workflow
    artifact_section = workflow.split("Upload sanitized mission evidence", 1)[1]
    assert all(x not in artifact_section for x in ("/tmp/brain-build-agent.log", "/tmp/brain-build-agent-*.log"))


def test_secret_scan_handles_deleted_renamed_and_space_containing_paths():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert all(x in workflow for x in ('"--name-only", "--no-renames", "-z", "HEAD"', '["git", "show", f"HEAD:{name}"]', "target.write_bytes(blob.stdout)", "Prepared changed-file scan input, including base contents for deleted paths", "zricethezav/gitleaks:v8.24.2", "--redact --exit-code 1"))
    assert "tar --null -T -" not in workflow


def test_project_check_reporting_distinguishes_tests_smoke_and_none():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert all(x in workflow for x in (
        "check_type=tests", "check_type=smoke", "check_type=none",
        'python -c \'import json; s=json.load(open("package.json", encoding="utf-8"))',
        'echo "check_type=$check_type" >> "$GITHUB_OUTPUT"',
        'tests) check_summary="tests passed"', 'smoke) check_summary="smoke check passed; no tests detected"',
        'none) check_summary="no tests/build/lint check configured"', "- Checks: ${check_summary}; gitleaks passed.",
        "- Checks: %s; gitleaks PASS", "Project checks passed (type=$check_type); raw command output is suppressed.",
        "Project checks failed (type=$check_type, exit=$result); raw command output is suppressed.",
    ))
    assert "BRAIN_CHECK_TYPE=" not in workflow and "cat /tmp/brain-checks.log" not in workflow
    assert 'if [ "$check_type" = "none" ]; then' in workflow and "raw command output is suppressed" in workflow
    artifacts = workflow.split("Upload sanitized mission evidence", 1)[1]
    assert all(x not in artifacts for x in ("/tmp/brain-checks.log", "/tmp/brain-check-install.log"))


def test_workflow_reports_failures_without_secrets_or_provider_bodies():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert all(x in workflow for x in (
        "report_failure:",
        "always()",
        "needs.prepare.result == 'failure' || needs.mission.result == 'failure'",
        "failed_step: ${{ steps.mission_lock.outcome",
        "steps.initialize.outcome == 'failure' && 'target repository access/initialization'",
        "FAILED_STEP: ${{ needs.mission.outputs.failed_step }}",
        "permissions:\\n      issues: write",
        "github.event_name == 'workflow_dispatch' && github.actor == github.repository_owner",
        "if (issueNumber)",
        "await core.summary",
        "Workflow run: ${process.env.RUN_URL}",
        "This report intentionally excludes secrets and provider response bodies.",
    ))
    assert r"].join('\\n');" in workflow

def test_cross_repository_build_has_project_checks_and_protected_path_gate():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert all(x in workflow for x in (
        "Run project-aware checks",
        'rsync -a --delete --exclude=\'/.git\' "$GITHUB_WORKSPACE/" "$check_workspace/"',
        'rsync -a --delete --exclude=\'/.git\' "$GITHUB_WORKSPACE/" "$preview_workspace/"',
        '-v "$check_workspace:/workspace"', '-v "$preview_workspace:/workspace"',
        'cp "$preview_workspace/.brain/preview/"*.png "$GITHUB_WORKSPACE/.brain/preview/"',
        "python -m pytest -q", "npm test -- --run", "Static HTML checks",
        "Protected workflow, environment, deployment, or credential-related changes detected",
        "steps.agent.outcome == 'success' && steps.candidate.outcome == 'success'",
        "steps.checks.outcome == 'success' && steps.gitleaks.outcome == 'success'",
        "grep -izEq", "git diff --name-only --no-renames -z HEAD | grep -izEq",
    ))
    assert '-v "$GITHUB_WORKSPACE:/workspace"' not in workflow
    assert "human review and merge required" in workflow
    assert "json.dumps(p[:8], ensure_ascii=True)" in workflow
    assert 'git -C "$diff_workspace" -c core.hooksPath=/dev/null diff --cached --check -- .' in workflow
    assert "Whitespace errors detected in candidate changes" in workflow
    gate = re.search(r"grep -izEq '([^']+)'", workflow)
    assert gate is not None
    protected = re.compile(gate.group(1), re.IGNORECASE)
    protected_examples = (".github/workflows/release.yml", ".github/actions/build/action.yml", ".env.production", "service/.npmrc", "CODEOWNERS", "Dockerfile.dev", "docker-compose.prod.yaml", "infra/main.tf", "deploy/helm/values.yaml", "secrets/provider-key.json", "certs/service.pem")
    allowed_examples = ("src/brain/main.py", "README.md", "tests/test_brain_build_workflow_contract.py")
    assert all(protected.search(x) for x in protected_examples) and all(not protected.search(x) for x in allowed_examples)


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
    assert "MSWEA_GLOBAL_CALL_LIMIT: \"14\"" in workflow
    assert all(x in workflow for x in (
        "Capture isolated mobile and desktop previews for static HTML", "mobile-390x844.png",
        "desktop-1280x800.png", "route.abort()", "id: preview", "continue-on-error: true",
        "hashFiles('*.html') != ''", 'PREVIEW_OUTCOME: ${{ steps.preview.outcome }}', "preview capture failed",
    ))


def test_legacy_remote_test_runner_no_longer_falls_back_to_control_token():
    workflow = (ROOT / ".github" / "workflows" / "brain-task-runner.yml").read_text(encoding="utf-8")
    assert "secrets.BRAIN_GITHUB_TOKEN || github.token" not in workflow
    assert "token: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    assert "BRAIN_GITHUB_TOKEN is required for target-repository checkout" in workflow
    assert "types: [opened, edited]" not in workflow
