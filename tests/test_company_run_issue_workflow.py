"""Tests for company run issue workflow utilities and regression tests."""

import pytest
from brain.company.run_issue_workflow import build_audit_source_chunks


def test_build_audit_source_chunks_uses_real_newlines():
    sources = {
        "brain/company/run_issue_workflow.py": "line one\nline two\nline three",
        "README.md": "header\nbody",
    }
    chunks = build_audit_source_chunks(sources)
    assert len(chunks) > 0
    context = chunks[0]["source_context"]
    
    # Verify no literal escaped backslash-n sequences exist
    assert "\\n" not in context
    
    # Verify actual newlines separate each FILE/L line
    lines = context.splitlines()
    assert len(lines) == 5
    assert lines[0] == "README.md:1:header"
    assert lines[1] == "README.md:2:body"
    assert lines[2] == "brain/company/run_issue_workflow.py:1:line one"
    assert lines[3] == "brain/company/run_issue_workflow.py:2:line two"
    assert lines[4] == "brain/company/run_issue_workflow.py:3:line three"


def test_build_audit_source_chunks_empty():
    chunks = build_audit_source_chunks({})
    assert len(chunks) == 1
    assert chunks[0]["source_context"] == "(No source files provided)"
