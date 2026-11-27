"""Regression tests for the OpenHands developer adapter's patch contract."""

import subprocess

import pytest

from brain.company.agent_runner import AgentOutputError
from brain.company.openhands_developer import (
    _collect_change_set,
    _collect_git_change_set,
    _developer_tools,
    _prepare_workspace,
    _safe_relative_path,
    _sdk_llm_kwargs,
    _sdk_model_name,
    _task_prompt,
    _uses_native_gemini,
)


def test_developer_task_prompt_includes_the_role_skill():
    prompt = _task_prompt("Do the work", {"repository_snapshot": {"source_contents": {}}})
    assert "ROLE SKILL (developer):" in prompt
    assert "Implementation Engineer" in prompt


def test_developer_task_prompt_allows_new_files_and_deletions():
    prompt = _task_prompt("Do the work", {"repository_snapshot": {"source_contents": {}}})
    assert "add new files" in prompt
    assert "delete files" in prompt


@pytest.mark.parametrize("path", ["../outside.py", "/tmp/outside.py", "src/../../outside.py", "brain\\unsafe.py"])
def test_openhands_adapter_rejects_unsafe_output_paths(path):
    with pytest.raises(AgentOutputError, match="unsafe repository path"):
        _safe_relative_path(path)


def test_safe_relative_path_accepts_github_workflows_ci_yml():
    assert _safe_relative_path(".github/workflows/ci.yml") == ".github/workflows/ci.yml"


def _seed(root, files):
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def test_collect_change_set_reports_edits(tmp_path):
    original = {"pkg/mod.py": "old\n"}
    _seed(tmp_path, original)
    (tmp_path / "pkg" / "mod.py").write_text("new\n", encoding="utf-8")
    changed = _collect_change_set(tmp_path, original)
    assert changed == [{"path": "pkg/mod.py", "content": "new\n"}]


def test_collect_change_set_accepts_an_unplanned_new_file(tmp_path):
    original = {"pkg/mod.py": "same\n"}
    _seed(tmp_path, original)
    _seed(tmp_path, {"pkg/brand_new.py": "print('hi')\n"})
    changed = _collect_change_set(tmp_path, original)
    assert {"path": "pkg/brand_new.py", "content": "print('hi')\n"} in changed


def test_collect_change_set_reports_a_deletion_as_a_marker(tmp_path):
    original = {"pkg/old.py": "dead\n", "pkg/keep.py": "same\n"}
    _seed(tmp_path, original)
    (tmp_path / "pkg" / "old.py").unlink()
    changed = _collect_change_set(tmp_path, original)
    assert changed == [{"path": "pkg/old.py", "deleted": True}]


def test_collect_change_set_carries_edits_additions_and_deletions_together(tmp_path):
    original = {"pkg/keep.py": "same\n", "pkg/dead.py": "gone\n"}
    _seed(tmp_path, original)
    (tmp_path / "pkg" / "keep.py").write_text("changed\n", encoding="utf-8")
    (tmp_path / "pkg" / "dead.py").unlink()
    _seed(tmp_path, {"pkg/added.py": "fresh\n"})
    by_path = {item["path"]: item for item in _collect_change_set(tmp_path, original)}
    assert by_path["pkg/keep.py"] == {"path": "pkg/keep.py", "content": "changed\n"}
    assert by_path["pkg/dead.py"] == {"path": "pkg/dead.py", "deleted": True}
    assert by_path["pkg/added.py"] == {"path": "pkg/added.py", "content": "fresh\n"}


def test_collect_change_set_raises_when_nothing_changed(tmp_path):
    original = {"pkg/mod.py": "same\n"}
    _seed(tmp_path, original)
    with pytest.raises(AgentOutputError, match="without producing any repository file changes"):
        _collect_change_set(tmp_path, original)


def test_collect_change_set_ignores_agent_state_directories(tmp_path):
    original = {"pkg/mod.py": "old\n"}
    _seed(tmp_path, original)
    (tmp_path / "pkg" / "mod.py").write_text("new\n", encoding="utf-8")
    _seed(tmp_path, {".openhands/state.json": "{}\n", ".git/HEAD": "ref\n"})
    changed = _collect_change_set(tmp_path, original)
    assert [item["path"] for item in changed] == ["pkg/mod.py"]


def test_developer_tools_grant_file_editor_and_local_shell():
    names = [tool.name for tool in _developer_tools("https://api.deepseek.com/v1")]
    assert "file_editor" in names
    assert "terminal" in names


def test_developer_tools_use_gemini_file_tools_plus_shell_on_native_gemini():
    names = [
        tool.name
        for tool in _developer_tools("https://generativelanguage.googleapis.com/v1beta/openai")
    ]
    assert "terminal" in names
    assert "file_editor" not in names
    assert "read_file" in names


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


def _git(path, *args):
    return subprocess.run(
        ["git", *args], cwd=str(path), capture_output=True, text=True, check=True
    )


def _repo_with_commit(path):
    """A real git repository with one commit; returns its HEAD sha."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.test")
    _git(path, "config", "user.name", "Test")
    (path / "pkg").mkdir(exist_ok=True)
    (path / "pkg" / "mod.py").write_text("old\n", encoding="utf-8")
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "base")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def test_prepare_workspace_checks_out_the_whole_repository(tmp_path):
    """W3: the developer sees the real tree, not only the files Brain happened to fetch."""
    origin = tmp_path / "origin"
    head = _repo_with_commit(origin)
    root = tmp_path / "work"
    root.mkdir()

    mode, detail = _prepare_workspace(
        root, "owner/repo", {"pkg/mod.py": "old\n"}, ref="main", clone_url=str(origin)
    )

    assert mode == "checkout"
    assert detail.startswith(str(origin))
    assert (root / ".git").is_dir()
    assert _git(root, "rev-parse", "HEAD").stdout.strip() == head
    assert (root / "README.md").is_file(), "a file outside the fetched snapshot must be present"


def test_prepare_workspace_falls_back_to_the_fetched_snapshot(tmp_path):
    root = tmp_path / "work"
    root.mkdir()

    mode, detail = _prepare_workspace(
        root,
        "owner/repo",
        {"pkg/mod.py": "old\n"},
        ref="main",
        clone_url=str(tmp_path / "missing"),
    )

    assert mode == "seed"
    assert "clone" in detail
    assert (root / "pkg" / "mod.py").read_text(encoding="utf-8") == "old\n"
    assert not (root / ".git").exists()


def test_prepare_workspace_never_writes_the_token_into_git_config(tmp_path):
    origin = tmp_path / "origin"
    _repo_with_commit(origin)
    root = tmp_path / "work"
    root.mkdir()

    mode, _ = _prepare_workspace(
        root,
        "owner/repo",
        {},
        token="ghs_example_token_value",
        ref="main",
        clone_url=str(origin),
    )

    assert mode == "checkout"
    assert "ghs_example_token_value" not in (root / ".git" / "config").read_text(encoding="utf-8")


def _checkout(tmp_path):
    origin = tmp_path / "origin"
    _repo_with_commit(origin)
    root = tmp_path / "work"
    root.mkdir()
    mode, _ = _prepare_workspace(root, "owner/repo", {}, ref="main", clone_url=str(origin))
    assert mode == "checkout"
    return root


def test_git_change_set_reports_edits_additions_and_deletions(tmp_path):
    root = _checkout(tmp_path)
    (root / "pkg" / "mod.py").write_text("new\n", encoding="utf-8")
    (root / "README.md").unlink()
    (root / "pkg" / "added.py").write_text("fresh\n", encoding="utf-8")

    by_path = {item["path"]: item for item in _collect_git_change_set(root)}

    assert by_path == {
        "pkg/mod.py": {"path": "pkg/mod.py", "content": "new\n"},
        "README.md": {"path": "README.md", "deleted": True},
        "pkg/added.py": {"path": "pkg/added.py", "content": "fresh\n"},
    }


def test_git_change_set_ignores_agent_state_directories(tmp_path):
    root = _checkout(tmp_path)
    (root / "pkg" / "mod.py").write_text("new\n", encoding="utf-8")
    (root / ".openhands").mkdir()
    (root / ".openhands" / "state.json").write_text("{}\n", encoding="utf-8")

    changed = _collect_git_change_set(root)

    assert [item["path"] for item in changed] == ["pkg/mod.py"]


def test_git_change_set_raises_when_nothing_changed(tmp_path):
    root = _checkout(tmp_path)

    with pytest.raises(AgentOutputError, match="without producing any repository file changes"):
        _collect_git_change_set(root)


def test_developer_task_prompt_describes_the_checkout():
    prompt = _task_prompt(
        "Do the work", {"repository_snapshot": {"source_contents": {}}}, "checkout"
    )
    assert "full git checkout" in prompt
