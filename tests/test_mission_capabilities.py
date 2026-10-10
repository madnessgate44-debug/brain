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
