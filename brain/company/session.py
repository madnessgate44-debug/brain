"""Durable conversation sessions (R5).

Wraps the SDK's create-or-resume so a mission's agent conversation survives a process
restart: its event log and base state are written under a stable directory keyed by
session id, and reopening with the same id restores the history. Auto-resuming a
mission is still forbidden (brain/services/recovery_service.py); this only makes the
conversation resumable when a caller chooses to.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Callable

_NAMESPACE = uuid.UUID("6f1e6b1a-6c2b-4b8e-9b0a-2f9c9f3c9a11")


def session_root() -> Path:
    """Where session state lives. Overridable so tests never touch the real store."""
    root = os.environ.get("BRAIN_SESSION_DIR")
    base = Path(root) if root else Path.cwd() / ".brain" / "sessions"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _conversation_id(session_id: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, session_id)


def is_resumable(session_id: str) -> bool:
    return (session_root() / _conversation_id(session_id).hex / "base_state.json").is_file()


def open_conversation(
    session_id: str,
    workspace: Path,
    agent_factory: Callable[[], Any],
) -> Any:
    """Create the conversation on first use, resume it afterwards.

    agent_factory is only called on the first (create) path; on resume the agent is
    restored from base_state.json, so the caller does not need the LLM credentials
    again just to read history.
    """
    from openhands.sdk import Conversation

    root = session_root()
    cid = _conversation_id(session_id)
    if is_resumable(session_id):
        return Conversation(
            agent=None, workspace=str(workspace), persistence_dir=str(root),
            conversation_id=cid, delete_on_close=False,
        )
    return Conversation(
        agent=agent_factory(), workspace=str(workspace), persistence_dir=str(root),
        conversation_id=cid, delete_on_close=False,
    )
