"""Focused formatting tests for persisted mission diagnostics."""

from brain.runtime.mission_runtime import _format_failure_report_markdown


def test_failure_report_markdown_uses_real_line_breaks():
    lines = ["# Mission failed", "", "## Impact", "- Tests status: failed", "- Success claimed: no"]

    report = _format_failure_report_markdown(lines).decode("utf-8")

    assert report.splitlines() == lines
    assert report.count("\n") == len(lines)
    assert "\\n" not in report
    assert report.endswith("\n")
