"""Lifecycle hooks for the developer agent (R4).

Wires a real PreToolUse hook to the SDK event bus, so every tool the developer agent
runs is observed and logged before it executes. The hook is a standalone script (no
Brain imports) run by the SDK's own hook executor with the event JSON on stdin; it
appends one JSON line to a log and answers `{"decision": "allow"}`.

The hook script and its log live outside the agent's workspace, so they never appear
as an unplanned file change.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPT = '''\
"""Brain PreToolUse hook: log the event, then allow the tool to run."""
import datetime
import json
import sys

LOG = {log_path!r}


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {{}}
    line = json.dumps({{
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event.get("event_type"),
        "tool": event.get("tool_name"),
    }})
    try:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\\n")
    except OSError:
        pass
    print(json.dumps({{"decision": "allow"}}))


if __name__ == "__main__":
    main()
'''


def build_hook_config(artifact_dir: Path, workspace: Path) -> tuple[Any, Path]:
    """Create the hook script and return (HookConfig, log_path).

    artifact_dir must be outside `workspace` so hook files are not seen as agent output.
    """
    from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher, HookType

    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / "hooks.log"
    script_path = artifact_dir / "pre_tool_use_hook.py"
    script_path.write_text(_SCRIPT.format(log_path=str(log_path)), encoding="utf-8")

    definition = HookDefinition(
        type=HookType.COMMAND,
        name="brain-log-pre-tool-use",
        command=f'"{sys.executable}" "{script_path}"',
        timeout=10,
    )
    config = HookConfig(pre_tool_use=[HookMatcher(matcher=".*", hooks=[definition])])
    return config, log_path


def hook_fired(log_path: Path, tool_name: str | None = None) -> bool:
    """True if the hook logged at least one event (optionally for a specific tool)."""
    if not log_path.is_file():
        return False
    text = log_path.read_text(encoding="utf-8")
    if tool_name is None:
        return bool(text.strip())
    return f'"tool": "{tool_name}"' in text
