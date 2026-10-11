"""Regression tests for the OpenHands developer adapter's path boundary."""

import pytest

from brain.company.agent_runner import AgentOutputError
from brain.company.openhands_developer import _safe_relative_path, _safe_request_paths, _sdk_model_name


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


def test_custom_endpoint_forces_openai_compatible_model_routing():
    assert _sdk_model_name(
        "gemini-3.5-flash-lite",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ) == "openai/gemini-3.5-flash-lite"


def test_openai_compatible_model_prefix_is_not_duplicated():
    assert _sdk_model_name("openai/custom-model", "https://example.test/v1") == "openai/custom-model"


def test_model_name_without_custom_endpoint_is_preserved():
    assert _sdk_model_name("gpt-4.1", None) == "gpt-4.1"
