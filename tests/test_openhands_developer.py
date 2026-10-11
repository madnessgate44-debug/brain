"""Regression tests for the OpenHands developer adapter's path boundary."""

import pytest

from brain.company.agent_runner import AgentOutputError
from brain.company.openhands_developer import _safe_relative_path, _safe_request_paths


@pytest.mark.parametrize("path", ["../outside.py", "/tmp/outside.py", "src/../../outside.py", "brain\\unsafe.py"])
def test_openhands_adapter_rejects_unsafe_output_paths(path):
    with pytest.raises(AgentOutputError, match="unsafe repository path"):
        _safe_relative_path(path)


def test_unsafe_path_examples_in_task_text_are_not_output_path_hints():
    assert _safe_request_paths(
        "Add a regression test for rejecting ../outside.py and /tmp/outside.py."
    ) == set()


def test_safe_explicit_path_in_task_text_is_preserved():
    assert _safe_request_paths("Update tests/test_feature.py") == {"tests/test_feature.py"}
