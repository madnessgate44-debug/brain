import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def run_node(expression):
    if NODE is None:
        pytest.skip("Node.js is required to test the post-PR verification helper")
    script = (
        "const { selectMatchingWorkflowRuns, evaluatePostPrVerification } = "
        "require('./scripts/post_pr_verification.js');\n"
        + expression
    )
    result = subprocess.run(
        [NODE, "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_workflow_run_selection_requires_exact_branch_and_head_sha():
    result = run_node(
        """
        const runs = [
          {id: 1, head_branch: 'brain/mission-a', head_sha: 'old-sha', created_at: '2026-10-10T00:00:02Z'},
          {id: 2, head_branch: 'brain/mission-a', head_sha: 'expected-sha', created_at: '2026-10-10T00:00:03Z'},
          {id: 3, head_branch: 'brain/mission-b', head_sha: 'expected-sha', created_at: '2026-10-10T00:00:04Z'},
          {id: 4, head_branch: 'brain/mission-a', head_sha: 'expected-sha', created_at: '2026-10-09T23:59:59Z'}
        ];
        const selected = selectMatchingWorkflowRuns(
          runs, 'brain/mission-a', 'expected-sha', Date.parse('2026-10-10T00:00:00Z')
        );
        console.log(JSON.stringify(selected.map(run => run.id)));
        """
    )

    assert result == [2]


def test_post_pr_verification_fails_if_head_changes_after_checks():
    result = run_node(
        """
        const workflowIds = ['brain-ci.yml', 'tests.yml', 'browser-runtime-smoke.yml'];
        const outcomes = workflowIds.map(workflow => ({
          workflow, status: 'PASS', head_sha: 'expected-sha'
        }));
        console.log(JSON.stringify(evaluatePostPrVerification({
          expectedHeadSha: 'expected-sha',
          finalHeadSha: 'new-sha',
          outcomes,
          workflowIds
        })));
        """
    )

    assert result["passed"] is False
    assert result["head_stable"] is False
    assert result["workflows_passed"] is True
    assert result["expected_head_sha"] == "expected-sha"
    assert result["final_head_sha"] == "new-sha"


def test_post_pr_verification_passes_only_for_three_matching_runs_and_stable_head():
    result = run_node(
        """
        const workflowIds = ['brain-ci.yml', 'tests.yml', 'browser-runtime-smoke.yml'];
        const outcomes = workflowIds.map(workflow => ({
          workflow, status: 'PASS', head_sha: 'expected-sha'
        }));
        console.log(JSON.stringify(evaluatePostPrVerification({
          expectedHeadSha: 'expected-sha',
          finalHeadSha: 'expected-sha',
          outcomes,
          workflowIds
        })));
        """
    )

    assert result["passed"] is True
    assert result["head_stable"] is True
    assert result["workflows_passed"] is True


def test_post_pr_verification_rejects_missing_or_wrong_sha_workflow_results():
    result = run_node(
        """
        const workflowIds = ['brain-ci.yml', 'tests.yml', 'browser-runtime-smoke.yml'];
        const outcomes = [
          {workflow: 'brain-ci.yml', status: 'PASS', head_sha: 'expected-sha'},
          {workflow: 'tests.yml', status: 'PASS', head_sha: 'old-sha'}
        ];
        console.log(JSON.stringify(evaluatePostPrVerification({
          expectedHeadSha: 'expected-sha',
          finalHeadSha: 'expected-sha',
          outcomes,
          workflowIds
        })));
        """
    )

    assert result["passed"] is False
    assert result["head_stable"] is True
    assert result["workflows_passed"] is False


def test_workflow_wires_exact_head_recheck_and_run_sha_filter():
    workflow = (ROOT / ".github/workflows/brain-chat-company-workflow.yml").read_text(encoding="utf-8")

    assert "selectMatchingWorkflowRuns" in workflow
    assert "evaluatePostPrVerification" in workflow
    assert "expectedHeadSha" in workflow
    assert "finalHeadSha" in workflow
    assert "github.rest.pulls.get" in workflow
