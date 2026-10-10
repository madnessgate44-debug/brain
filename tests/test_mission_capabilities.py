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
