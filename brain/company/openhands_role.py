"""OpenHands-backed investigative stage for Brain's non-developer specialists.

Before this existed, only `developer` reached a real agentic loop; the other company roles
called `provider.complete` once and answered from whatever evidence was pasted into the
prompt (agent_runner.py:412). That is the "1 of 9" gap: a reviewer that cannot open a file
is guessing.

Here every specialist gets the same thing the developer gets — a real OpenHands SDK
conversation with file and terminal tools, scoped to an isolated temporary copy of the
supplied source — and is told to investigate before it answers. It returns the role's own
JSON contract, which `agent_runner` validates exactly as it validates a single-shot answer,
so the release gates are unchanged.

The role is read-only by contract: any file it writes is discarded. Only its final message
is kept.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from brain.company.agent_runner import AgentOutputError, load_role_skill


_MAX_FILE_BYTES = 200_000
_MAX_WORKSPACE_BYTES = 2_200_000


def _safe_relative_path(raw_path: str) -> str:
    path = Path(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in raw_path.split("/"))
        or raw_path.startswith(".git/")
    ):
        raise AgentOutputError(f"Unsafe repository path: {raw_path!r}")
    return path.as_posix()


def _role_tools(base_url: str | None) -> list[Any]:
    """File and terminal tools, so the role can read and run checks while it investigates."""
    from openhands.sdk import Tool

    from brain.company.openhands_developer import _uses_native_gemini

    if _uses_native_gemini(base_url):
        from openhands.tools.gemini import GEMINI_FILE_TOOLS

        tools = list(GEMINI_FILE_TOOLS)
    else:
        from openhands.tools.file_editor import FileEditorTool

        tools = [Tool(name=FileEditorTool.name)]
    from openhands.tools.terminal import TerminalTool

    tools.append(Tool(name=TerminalTool.name))
    return tools


def _role_prompt(role_key: str, role_title: str, system_prompt: str, user_prompt: str) -> str:
    skill = load_role_skill(role_key)
    return (
        (f"ROLE SKILL ({role_key}):\n{skill}\n\n" if skill else "")
        + f"You are the {role_title} in a software company. You have a working copy of the "
        "repository and file/terminal tools. Investigate it before you answer: open the files "
        "the task depends on, and run read-only checks. Base every claim on what you actually "
        "read or ran; never claim a file was inspected or a check passed if it was not.\n\n"
        "You are read-only: do not modify the repository. Any change you make is discarded, "
        "and only your final message is kept.\n\n"
        "When you are done, reply with exactly one JSON object and nothing else — no markdown "
        "fences, no prose around it. The object must have keys: status, deliverables, findings, "
        "blockers, evidence_needed. `status` is PASS, NEEDS_WORK, or BLOCKED. `deliverables` "
        "must contain every required key. findings, blockers, evidence_needed must be arrays.\n\n"
        f"YOUR ROLE CONTRACT:\n{system_prompt}\n\n"
        f"TASK AND SUPPLIED EVIDENCE:\n{user_prompt}\n"
    )


def _final_agent_message(conversation: Any) -> str:
    """Return the text of the agent's last MessageEvent (its answer)."""
    from openhands.sdk.event.llm_convertible import MessageEvent

    texts: list[str] = []
    for event in conversation.state.events:
        if isinstance(event, MessageEvent) and getattr(event, "source", None) == "agent":
            parts = [
                block.text
                for block in (event.llm_message.content or [])
                if getattr(block, "text", None)
            ]
            if parts:
                texts.append("".join(parts))
    return texts[-1] if texts else ""


def _run_sdk_sync(
    role_key: str,
    role_title: str,
    system_prompt: str,
    user_prompt: str,
    evidence: dict[str, Any],
    provider: Any,
) -> str:
    try:
        from openhands.sdk import LLM, Agent, Conversation
    except ImportError as exc:
        raise AgentOutputError(
            "OpenHands specialist backend is not installed; install Brain's declared dependencies."
        ) from exc

    from brain.company.openhands_developer import _sdk_llm_kwargs

    snapshot = evidence.get("repository_snapshot", {})
    source_contents = snapshot.get("source_contents", {}) if isinstance(snapshot, dict) else {}
    original: dict[str, str] = {}
    total = 0
    for raw_path, text in (source_contents.items() if isinstance(source_contents, dict) else []):
        if not isinstance(raw_path, str) or not isinstance(text, str):
            continue
        encoded = len(text.encode("utf-8"))
        if encoded > _MAX_FILE_BYTES or total + encoded > _MAX_WORKSPACE_BYTES:
            continue
        original[_safe_relative_path(raw_path)] = text
        total += encoded

    api_key = getattr(provider, "api_key", None)
    model = getattr(provider, "model", None)
    base_url = getattr(provider, "base_url", None)
    if not api_key or not model:
        raise AgentOutputError("OpenHands specialist backend requires configured model credentials.")

    with tempfile.TemporaryDirectory(prefix="brain-role-") as temporary_dir:
        root = Path(temporary_dir).resolve()
        for relative, text in original.items():
            target = (root / relative).resolve()
            if root not in target.parents:
                raise AgentOutputError(f"Source path escaped the workspace: {relative!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        llm = LLM(**_sdk_llm_kwargs(model, api_key, base_url))
        agent = Agent(llm=llm, tools=_role_tools(base_url))
        conversation = Conversation(agent=agent, workspace=str(root))
        try:
            conversation.send_message(
                _role_prompt(role_key, role_title, system_prompt, user_prompt)
            )
            conversation.run()
            return _final_agent_message(conversation)
        finally:
            conversation.close()


async def run_openhands_role(
    role_key: str,
    role_title: str,
    system_prompt: str,
    user_prompt: str,
    evidence: dict[str, Any],
    provider: Any,
) -> str:
    """Investigate with tools, then return the role's JSON answer (unvalidated text)."""
    return await asyncio.to_thread(
        _run_sdk_sync, role_key, role_title, system_prompt, user_prompt, evidence, provider
    )
