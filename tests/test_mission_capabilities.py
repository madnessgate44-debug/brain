from brain.company.mission_capabilities import plan_capabilities


def test_read_only_mission_does_not_require_write_capability():
    plan = plan_capabilities("Audit Amina and report findings. Do not change files.")
    assert plan.mode == "read_only"
    assert "repository:write" not in plan.required_capabilities


def test_mutating_mission_requires_write_and_verification_capabilities():
    plan = plan_capabilities("Inspect the repository, fix defects, run tests, and open a pull request.")
    assert plan.mode == "mutating"
    assert "repository:write" in plan.required_capabilities
    assert "checks:run" in plan.required_capabilities
    assert "pull_request:create" in plan.required_capabilities


def test_read_only_is_the_default_when_no_mutation_is_requested():
    plan = plan_capabilities("Review architecture and explain risks.")
    assert plan.mode == "read_only"


def test_explicit_markdown_file_creation_is_mutating_even_without_pr_phrase():
    objective = """Documentation-only. Create exactly \`docs/BRAIN_E2E_DISPATCH_ACCEPTANCE.md\`
with exactly three lines. Do not modify workflow code, secrets, or deployment settings."""
    plan = plan_capabilities(objective)
    assert plan.mode == "mutating"
    assert "repository:write" in plan.required_capabilities
    assert "pull_request:create" in plan.required_capabilities


def test_multiline_read_only_audit_constraints_do_not_trigger_write_mode():
    objective = """Perform a READ-ONLY, evidence-based audit of the repository and report findings.
Required work: inspect source files, run safe non-mutating checks, and recommend remediations.
Hard constraints:
- Do NOT edit, create, delete, commit, or push files in the target repository.
- Do NOT create a branch or pull request.
- Do NOT merge, deploy, change settings, or modify secrets.
"""
    plan = plan_capabilities(objective)
    assert plan.mode == "read_only"
    assert "repository:write" not in plan.required_capabilities


def test_audit_mentions_of_build_and_commit_are_not_mutation_intent():
    objective = """Perform a READ-ONLY audit and report findings only.
Audit test/build/lint coverage and include the repository/branch/commit examined.
- Do NOT edit, create, delete, commit, or push files in the target repository.
- Do NOT create a branch or pull request.
"""
    plan = plan_capabilities(objective)
    assert plan.mode == "read_only"


def test_positive_change_request_still_requires_write_capability():
    plan = plan_capabilities("Inspect the repository and fix the identified defects.")
    assert plan.mode == "mutating"
    assert "repository:write" in plan.required_capabilities


def test_read_only_audit_with_negated_actions_in_same_paragraph_stays_read_only():
    objective = (
        "Audit the current repository. Do not edit files, create branches, commit, "
        "open PRs, merge, deploy, alter settings, or change secrets. Report findings only."
    )
    plan = plan_capabilities(objective)
    assert plan.mode == "read_only"
    assert "repository:write" not in plan.required_capabilities


def test_explicit_fix_request_remains_mutating_when_other_actions_are_forbidden():
    plan = plan_capabilities("Fix the identified defects, but do not merge or deploy.")
    assert plan.mode == "mutating"
    assert "repository:write" in plan.required_capabilities


def test_deploy_and_merge_mentions_without_targets_do_not_trigger_mutating_mode():
    plan = plan_capabilities("Audit the workflow logs for mentions of deploy and merge.")
    assert plan.mode == "read_only"
