"""Regression tests for the OpenHands developer adapter's path boundary."""

import pytest

from brain.company.agent_runner import AgentOutputError
from brain.company.openhands_developer import _safe_relative_path, _safe_request_paths, _sdk_model_name, _sdk_llm_kwargs, _uses_native_gemini


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


def test_google_openai_compatible_url_uses_native_gemini_provider():
    url = "https://generativelanguage.googleapis.com/v1beta/openai"
    assert _uses_native_gemini(url)
    assert _sdk_model_name("gemini-3.5-flash-lite", url) == "gemini/gemini-3.5-flash-lite"
    assert _sdk_model_name("openai/gemini-3.5-flash-lite", url) == "gemini/gemini-3.5-flash-lite"


def test_non_google_custom_endpoint_uses_openai_compatible_provider():
    assert not _uses_native_gemini("https://api.deepseek.com/v1")
    assert _sdk_model_name("deepseek-chat", "https://api.deepseek.com/v1") == "openai/deepseek-chat"


def test_openai_compatible_model_prefix_is_not_duplicated():
    assert _sdk_model_name("openai/custom-model", "https://example.test/v1") == "openai/custom-model"


def test_model_name_without_custom_endpoint_is_preserved():
    assert _sdk_model_name("gpt-4.1", None) == "gpt-4.1"


def test_native_gemini_kwargs_omit_openai_compatibility_fields():
    kwargs = _sdk_llm_kwargs(
        "gemini-3.5-flash-lite",
        "test-key",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    assert kwargs == {
        "model": "gemini/gemini-3.5-flash-lite",
        "api_key": "test-key",
        "base_url": None,
    }


def test_generic_custom_endpoint_keeps_conservative_optional_fields():
    kwargs = _sdk_llm_kwargs(
        "deepseek-chat",
        "test-key",
        "https://api.deepseek.com/v1",
    )
    assert kwargs["model"] == "openai/deepseek-chat"
    assert kwargs["caching_prompt"] is False
    assert kwargs["prompt_cache_retention"] is None
    assert kwargs["reasoning_effort"] is None
    assert kwargs["enable_encrypted_reasoning"] is False
    assert kwargs["capability_overrides"] == {
        "supports_prompt_cache_key": False,
        "supports_reasoning_effort": False,
        "supports_sampling_params": False,
    }
