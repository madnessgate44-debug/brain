"""Contract tests for the owner-gated cross-repository build workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "brain-build.yml"


def test_cross_repository_build_workflow_has_explicit_intake_and_retry():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "issues:" in workflow and "types: [opened]" in workflow
    assert "issue_comment:" in workflow and "types: [created]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "startsWith(github.event.comment.body, '/brain retry')" in workflow
    assert "startsWith(github.event.issue.body, '/brain build')" in workflow
    assert "startsWith(github.event.issue.body, '/brain fix')" in workflow
    assert "startsWith(github.event.issue.body, '/brain audit')" in workflow


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
    assert "GH_TOKEN: ${{ secrets.BRAIN_GITHUB_TOKEN }}" in workflow
    agent_step = workflow.split("- name: Run bounded coding agent without GitHub credentials in sandbox", 1)[1].split("- name: Run project-aware checks", 1)[0]
    assert "OPENAI_API_KEY: ${{ secrets.BRAIN_AI_API_KEY }}" in agent_step
    assert "BRAIN_GITHUB_TOKEN" not in agent_step
    assert "Never merge, deploy, or push." in agent_step


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
    assert "MSWEA_GLOBAL_CALL_LIMIT: \"14\"" in workflow
    assert "Capture isolated mobile and desktop previews for static HTML" in workflow
    assert "mobile-390x844.png" in workflow
    assert "desktop-1280x800.png" in workflow
    assert "route.abort()" in workflow
