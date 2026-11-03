"""R4: the developer agent's PreToolUse hook fires on the real SDK event bus."""

from __future__ import annotations

from pathlib import Path

from brain.company.hooks import build_hook_config, hook_fired


def test_pre_tool_use_hook_fires_and_allows(tmp_path: Path) -> None:
    from openhands.sdk.hooks import HookEventType, HookManager

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_dir = tmp_path / "artifacts"

    config, log_path = build_hook_config(artifact_dir, workspace)
    assert not hook_fired(log_path)

    manager = HookManager(config=config, working_dir=str(workspace))
    assert manager.has_hooks(HookEventType.PRE_TOOL_USE)

    allowed, results = manager.run_pre_tool_use("terminal", {"command": "echo hi"})

    assert allowed is True
    assert results and results[0].success
    assert hook_fired(log_path, "terminal")


def test_hook_files_stay_outside_the_workspace(tmp_path: Path) -> None:
    """Hook artifacts must not be seen as agent output (unplanned file changes)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_dir = tmp_path / "artifacts"

    _, log_path = build_hook_config(artifact_dir, workspace)

    assert log_path.is_file() or log_path.parent == artifact_dir
    assert workspace not in log_path.parents
