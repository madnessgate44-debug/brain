"""OpenHands-backed implementation stage for Brain's specialist workflow.

The upstream SDK is used as a tool-using coding agent. Brain retains ownership of
requirements, role order, GitHub writes, test execution, independent review, and release
gates. This adapter deliberately exposes file editing only; repository commands and tests
are executed later by Brain's existing GitHub Actions verification path.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from brain.company.agent_runner import AgentOutputError


_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\."
    r"(?:py|md|yml|yaml|json|toml|ts|tsx|js|jsx|html|css)(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
_MAX_FILES = 30
_MAX_FILE_BYTES = 200_000
_MAX_TOTAL_BYTES = 2_200_000


def _safe_relative_path(raw_path: str) -> str:
    path = Path(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in raw_path.split("/"))
        or raw_path.startswith(".git/")
    ):
        raise AgentOutputError(f"OpenHands proposed an unsafe repository path: {raw_path!r}")
    return path.as_posix()


def _safe_request_paths(user_request: str) -> set[str]:
    """Keep only safe explicit path hints; unsafe examples in prose are not output paths."""
    safe_paths: set[str] = set()
    for match in _PATH_PATTERN.finditer(user_request):
        # The pattern can begin after the leading slash in an absolute path. Do not
        # normalize that suffix into a seemingly safe relative output path.
        if match.start() > 0 and user_request[match.start() - 1] in {"/", "\\\\"}:
            continue
        try:
            safe_paths.add(_safe_relative_path(match.group(0)))
        except AgentOutputError:
            continue
    return safe_paths


def _task_prompt(user_request: str, evidence: dict[str, Any]) -> str:
    snapshot = evidence.get("repository_snapshot", {})
    source_contents = snapshot.get("source_contents", {}) if isinstance(snapshot, dict) else {}
    file_plan = evidence.get("file_plan", [])
    acceptance = evidence.get("acceptance_criteria", [])
    architecture = evidence.get("architecture", "")
    return (
        "Implement the assigned change in the provided repository workspace. "
        "Use the file-editor tool to inspect and edit files. Do not claim tests were run; "
        "Brain will run the real repository checks after your patch is collected.\n\n"
        f"USER REQUEST:\n{user_request}\n\n"
        f"ACCEPTANCE CRITERIA:\n{acceptance!r}\n\n"
        f"ARCHITECTURE DECISIONS:\n{architecture}\n\n"
        f"PLANNED FILES:\n{file_plan!r}\n\n"
        f"AVAILABLE SOURCE PATHS:\n{sorted(source_contents) if isinstance(source_contents, dict) else []}\n\n"
        "Rules: implement the acceptance criteria, preserve unrelated behavior, add or update "
        "regression tests when appropriate, do not edit files outside the planned paths unless "
        "a necessary existing file is present in the workspace, do not add dependencies unless "
        "required by the architecture, and do not perform network access or external side effects. "
        "Make the actual file edits now. A verbal description without changed files is a failure."
    )


def _run_sdk_sync(
    user_request: str,
    evidence: dict[str, Any],
    provider: Any,
) -> dict[str, Any]:
    """Run the SDK in a temporary workspace and return only validated changed file contents."""
    try:
        from openhands.sdk import LLM, Agent, Conversation, Tool
        from openhands.tools.file_editor import FileEditorTool
    except ImportError as exc:
        raise AgentOutputError(
            "OpenHands developer backend is not installed; install Brain's declared dependencies."
        ) from exc

    snapshot = evidence.get("repository_snapshot", {})
    source_contents = snapshot.get("source_contents", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(source_contents, dict) or not source_contents:
        raise AgentOutputError("OpenHands developer backend requires complete source file contents.")

    original: dict[str, str] = {}
    for raw_path, text in source_contents.items():
        if not isinstance(raw_path, str) or not isinstance(text, str):
            continue
        path = _safe_relative_path(raw_path)
        if len(text.encode("utf-8")) > _MAX_FILE_BYTES:
            continue
        original[path] = text
    if not original:
        raise AgentOutputError("No usable source files were supplied to OpenHands.")

    planned = evidence.get("file_plan", [])
    planned_paths = {
        _safe_relative_path(path)
        for path in planned
        if isinstance(path, str) and path.strip()
    } if isinstance(planned, list) else set()
    request_paths = _safe_request_paths(user_request)
    allowed_new_paths = planned_paths | request_paths
    api_key = getattr(provider, "api_key", None)
    model = getattr(provider, "model", None)
    base_url = getattr(provider, "base_url", None)
    if not api_key or not model:
        raise AgentOutputError("OpenHands developer backend requires configured model credentials.")

    with tempfile.TemporaryDirectory(prefix="brain-openhands-") as temporary_dir:
        root = Path(temporary_dir).resolve()
        for relative, text in original.items():
            target = (root / relative).resolve()
            if root not in target.parents:
                raise AgentOutputError(f"Source path escaped the temporary workspace: {relative!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        llm = LLM(model=model, api_key=api_key, base_url=base_url)
        agent = Agent(llm=llm, tools=[Tool(name=FileEditorTool.name)])
        conversation = Conversation(agent=agent, workspace=str(root))
        conversation.send_message(_task_prompt(user_request, evidence))
        conversation.run()

        changed: list[dict[str, str]] = []
        total_bytes = 0
        for target in sorted(root.rglob("*")):
            if not target.is_file() or target.is_symlink():
                continue
            relative = target.relative_to(root).as_posix()
            if relative.startswith(".openhands/") or relative.startswith(".git/"):
                continue
            relative = _safe_relative_path(relative)
            current = target.read_text(encoding="utf-8")
            if relative in original and current == original[relative]:
                continue
            if relative not in original and relative not in allowed_new_paths:
                raise AgentOutputError(
                    f"OpenHands created an unplanned file: {relative!r}; add it to the architecture file plan."
                )
            encoded_size = len(current.encode("utf-8"))
            if encoded_size > _MAX_FILE_BYTES:
                raise AgentOutputError(f"OpenHands output exceeds the per-file limit: {relative}")
            total_bytes += encoded_size
            if total_bytes > _MAX_TOTAL_BYTES:
                raise AgentOutputError("OpenHands output exceeds the aggregate patch size limit.")
            changed.append({"path": relative, "content": current})

        deleted = sorted(set(original) - {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        })
        if deleted:
            raise AgentOutputError(
                "OpenHands deleted existing files; Brain's current patch contract does not support deletions: "
                + ", ".join(deleted[:10])
            )
        if not changed:
            raise AgentOutputError("OpenHands completed without producing any repository file changes.")
        if len(changed) > _MAX_FILES:
            raise AgentOutputError(f"OpenHands changed more than {_MAX_FILES} files.")

    return {
        "status": "PASS",
        "deliverables": {
            "change_set": {
                "summary": "Implement requirements with OpenHands SDK",
                "files": changed,
            },
            "implementation_notes": (
                f"OpenHands SDK produced {len(changed)} changed file(s) in an isolated temporary "
                "workspace using file-editing tools only. Tests were not run by this agent; Brain's "
                "GitHub Actions check runner must provide that evidence."
            ),
        },
        "findings": [],
        "blockers": [],
        "evidence_needed": [],
    }


async def run_openhands_developer(
    user_request: str,
    evidence: dict[str, Any],
    provider: Any,
) -> dict[str, Any]:
    """Execute the coding stage without blocking Brain's async mission runtime."""
    return await asyncio.to_thread(_run_sdk_sync, user_request, evidence, provider)
