from brain.company.read_only_audit import is_read_only_audit


def test_explicit_read_only_audit_bypasses_write_workflow():
    assert is_read_only_audit(
        "Perform a READ-ONLY, evidence-based audit and report findings only."
    )


def test_explicit_no_changes_request_is_audit_mode():
    assert is_read_only_audit("Inspect the repository and do not modify files.")


def test_ordinary_implementation_request_is_not_audit_mode():
    assert not is_read_only_audit(
        "Implement the requested feature, run tests, and open a pull request."
    )
