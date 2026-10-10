"use strict";

function selectMatchingWorkflowRuns(runs, branch, expectedHeadSha, dispatchStartedAt) {
  if (!Array.isArray(runs)) return [];
  return runs
    .filter((item) =>
      item &&
      item.head_branch === branch &&
      item.head_sha === expectedHeadSha &&
      Date.parse(item.created_at) >= dispatchStartedAt
    )
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

function evaluatePostPrVerification({ expectedHeadSha, finalHeadSha, outcomes, workflowIds }) {
  const items = Array.isArray(outcomes) ? outcomes : [];
  const required = Array.isArray(workflowIds) ? workflowIds : [];
  const headStable = Boolean(expectedHeadSha && finalHeadSha === expectedHeadSha);
  const workflowsPassed = required.length > 0 && required.every((workflow) => {
    const outcome = items.find((item) => item.workflow === workflow);
    return Boolean(
      outcome &&
      outcome.status === "PASS" &&
      outcome.head_sha === expectedHeadSha
    );
  });

  return {
    passed: headStable && workflowsPassed,
    head_stable: headStable,
    workflows_passed: workflowsPassed,
    expected_head_sha: expectedHeadSha || null,
    final_head_sha: finalHeadSha || null
  };
}

module.exports = {
  selectMatchingWorkflowRuns,
  evaluatePostPrVerification
};
