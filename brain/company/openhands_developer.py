"""OpenHands-backed implementation stage for Brain's specialist workflow.

The upstream SDK is used as a tool-using coding agent. Brain retains ownership of
requirements, role order, GitHub writes, test execution, independent review, and release
gates. The adapter exposes file editing plus a local shell scoped to an isolated workspace,
so the developer can run the repository's own checks while it works. Brain's
GitHub Actions path remains the authoritative test evidence; a local run is advisory.

The workspace is a real `git clone` of the repository at its default branch, so the agent
sees the whole tree and can use git. When a clone is impossible (no repository, no git, no
network) the adapter falls back to seeding the files Brain already fetched.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from brain.company.agent_runner import AgentOutputError, load_role_skill
from brain.company.hooks import build_hook_config
from brain.company.settings import get_setting


_MAX_FILES = 30
_MAX_FILE_BYTES = 200_000
_MAX_TOTAL_BYTES = 2_200_000
_CHECKOUT_TIMEOUT_SECONDS = 300
_GIT_TIMEOUT_SECONDS = 60
_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


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


def _git_env() -> dict[str, str]:
    """Run git unattended: never prompt for a credential, never read a machine config."""
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "true",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }


def _git(
    args: list[str], cwd: Path, timeout: int = _GIT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=_git_env(),
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _clone_repository(
    root: Path, repository: str, ref: str | None, token: str, clone_url: str | None = None
) -> str | None:
    """Clone the real repository into ``root``; return the URL used, or None on failure."""
    url = clone_url or f"https://github.com/{repository}.git"
    command = ["git"]
    if token:
        # Per-invocation only: an extraheader never lands in .git/config, so the token
        # stays out of the checkout the agent can read.
        credential = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.extraheader=AUTHORIZATION: basic {credential}"]
    command += ["clone", "--depth", "1", "--single-branch"]
    if ref:
        command += ["--branch", ref]
    command += [url, "."]
    try:
        result = subprocess.run(
            command, cwd=str(root), env=_git_env(), capture_output=True, text=True,
            timeout=_CHECKOUT_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not (root / ".git").is_dir():
        return None
    return url


def _seed_workspace(root: Path, source_contents: dict[str, str]) -> None:
    for relative, text in source_contents.items():
        target = (root / relative).resolve()
        if root not in target.parents:
            raise AgentOutputError(f"Source path escaped the temporary workspace: {relative!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _prepare_workspace(
    root: Path,
    repository: str,
    source_contents: dict[str, str],
    *,
    token: str = "",
    ref: str | None = None,
    clone_url: str | None = None,
) -> tuple[str, str]:
    """Materialise the repository in ``root`` and report which mode was used.

    ``checkout`` is a real git clone of the repository at ``ref``: the agent sees the whole
    tree and can run git. ``seed`` is the fallback — only the files Brain already fetched,
    written into an empty directory — used when a clone is impossible.
    """
    if repository and _REPOSITORY_PATTERN.fullmatch(repository):
        url = _clone_repository(root, repository, ref, token, clone_url)
        if url:
            return "checkout", f"{url} @ {ref or 'HEAD'}"
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        detail = "git clone did not complete"
    else:
        detail = "no owner/repository supplied"
    _seed_workspace(root, source_contents)
    return "seed", detail


def _uses_native_gemini(base_url: str | None) -> bool:
    """Use Google's native Gemini API rather than its OpenAI-compatibility shim."""
    parsed = urlparse(base_url or "")
    return (
        parsed.hostname == "generativelanguage.googleapis.com"
        and parsed.path.rstrip("/").endswith("/openai")
    )


def _sdk_model_name(model: str, base_url: str | None) -> str:
    """Select the upstream LiteLLM provider for the configured API endpoint."""
    if _uses_native_gemini(base_url):
        normalized = model.removeprefix("openai/").removeprefix("gemini/")
        return f"gemini/{normalized}"
    if base_url and not model.startswith("openai/"):
        return f"openai/{model}"
    return model


def _sdk_llm_kwargs(model: str, api_key: str, base_url: str | None) -> dict[str, Any]:
    """Build provider-specific kwargs, avoiding Gemini's incompatible OpenAI shim."""
    if _uses_native_gemini(base_url):
        # The upstream OpenHands SDK example uses gemini/<model> with Google's native
        # provider. This preserves Gemini tool-call metadata such as thought_signature.
        return {
            "model": _sdk_model_name(model, base_url),
            "api_key": api_key,
            "base_url": None,
        }
    return {
        "model": _sdk_model_name(model, base_url),
        "api_key": api_key,
        "base_url": base_url,
        "caching_prompt": False,
        "prompt_cache_retention": None,
        "reasoning_effort": None,
        "enable_encrypted_reasoning": False,
        "capability_overrides": {
            "supports_prompt_cache_key": False,
            "supports_reasoning_effort": False,
            "supports_sampling_params": False,
        },
    }


def _developer_tools(base_url: str | None) -> list[Any]:
    """File-editing tools plus a local shell, scoped to the isolated temporary workspace.

    The shell lets the developer run the repository's own checks while it works. It runs
    inside the temporary workspace only; Brain re-runs the checks authoritatively.
    """
    from openhands.sdk import Tool

    if _uses_native_gemini(base_url):
        # Gemini-native file tools avoid routing native tool calls through the
        # OpenAI-compatible file_editor schema (matches the upstream example).
        from openhands.tools.gemini import GEMINI_FILE_TOOLS

        tools = list(GEMINI_FILE_TOOLS)
    else:
        from openhands.tools.file_editor import FileEditorTool

        tools = [Tool(name=FileEditorTool.name)]
    from openhands.tools.terminal import TerminalTool

    tools.append(Tool(name=TerminalTool.name))
    return tools


def _task_prompt(
    user_request: str, evidence: dict[str, Any], workspace_mode: str = "seed"
) -> str:
    snapshot = evidence.get("repository_snapshot", {})
    source_contents = snapshot.get("source_contents", {}) if isinstance(snapshot, dict) else {}
    file_plan = evidence.get("file_plan", [])
    acceptance = evidence.get("acceptance_criteria", [])
    architecture = evidence.get("architecture", "")
    skill = load_role_skill("developer")
    if workspace_mode == "checkout":
        workspace = (
            "The workspace is a full git checkout of the repository at its default branch. "
            "Read any file in the tree, not only the paths listed below, and use git "
            "(status, diff, log) to inspect what changed.\n\n"
        )
    else:
        workspace = ""
    return (
        (f"ROLE SKILL (developer):\n{skill}\n\n" if skill else "")
        + "Implement the assigned change in the provided repository workspace. "
        + workspace
        + "Use the provided file tools to inspect and edit files, and the terminal tool to run "
        "the repository's own check commands locally. Report exactly what you ran and its output. "
        "Brain re-runs the repository checks authoritatively after your patch is collected, so do "
        "not claim Brain's checks passed.\n\n"
        f"USER REQUEST:\n{user_request}\n\n"
        f"ACCEPTANCE CRITERIA:\n{acceptance!r}\n\n"
        f"ARCHITECTURE DECISIONS:\n{architecture}\n\n"
        f"PLANNED FILES:\n{file_plan!r}\n\n"
        f"AVAILABLE SOURCE PATHS:\n{sorted(source_contents) if isinstance(source_contents, dict) else []}\n\n"
        "Rules: implement the acceptance criteria and preserve unrelated behavior. You may edit "
        "any file present in the workspace, add new files the change needs, and delete files the "
        "change makes obsolete (remove them with the shell, e.g. `rm path`). Every change is "
        "reviewed independently before release, so make the change you judge correct. Add or update "
        "regression tests when appropriate, do not add dependencies unless required by the "
        "architecture, and do not perform network access or external side effects. "
        "You may run the repository's own test, lint, and build commands locally; never run "
        "commands that reach the network. "
        "Make the actual file edits now. A verbal description without changed files is a failure."
    )


def _collect_change_set(root: Path, original: dict[str, str]) -> list[dict[str, Any]]:
    """Diff the workspace against the seeded files and return the change set.

    Bounded by file count and size, but not by kind: an agent may edit existing files, add new
    files the change needs, and delete files the change makes obsolete. Deletions travel as
    ``{"path", "deleted": True}`` for the write gateway to remove.
    """
    changed: list[dict[str, Any]] = []
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
        encoded_size = len(current.encode("utf-8"))
        if encoded_size > _MAX_FILE_BYTES:
            raise AgentOutputError(f"OpenHands output exceeds the per-file limit: {relative}")
        total_bytes += encoded_size
        if total_bytes > _MAX_TOTAL_BYTES:
            raise AgentOutputError("OpenHands output exceeds the aggregate patch size limit.")
        changed.append({"path": relative, "content": current})

    present = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    for relative in sorted(set(original) - present):
        changed.append({"path": relative, "deleted": True})

    if not changed:
        raise AgentOutputError("OpenHands completed without producing any repository file changes.")
    if len(changed) > _MAX_FILES:
        raise AgentOutputError(f"OpenHands changed more than {_MAX_FILES} files.")
    return changed


def _collect_git_change_set(root: Path) -> list[dict[str, Any]]:
    """Read the agent's changes from git in a full checkout.

    Diffing a checkout against the fetched snapshot would report every file Brain did not
    fetch as new, so the change set comes from `git status` instead. Same bounds and path
    rules as `_collect_change_set`; a path that no longer exists travels as a deletion marker.
    """
    result = _git(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"], root
    )
    if result.returncode != 0:
        raise AgentOutputError(
            f"git status failed in the checkout: {result.stderr.strip()[:300]}"
        )
    changed: list[dict[str, Any]] = []
    total_bytes = 0
    for entry in result.stdout.split("\0"):
        if len(entry) < 4:
            continue
        relative = entry[3:]
        if relative.startswith((".openhands/", ".git/")):
            continue
        relative = _safe_relative_path(relative)
        target = root / relative
        if not target.is_file() or target.is_symlink():
            changed.append({"path": relative, "deleted": True})
            continue
        try:
            current = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AgentOutputError(f"OpenHands changed a non-text file: {relative}") from exc
        encoded_size = len(current.encode("utf-8"))
        if encoded_size > _MAX_FILE_BYTES:
            raise AgentOutputError(f"OpenHands output exceeds the per-file limit: {relative}")
        total_bytes += encoded_size
        if total_bytes > _MAX_TOTAL_BYTES:
            raise AgentOutputError("OpenHands output exceeds the aggregate patch size limit.")
        changed.append({"path": relative, "content": current})

    if not changed:
        raise AgentOutputError("OpenHands completed without producing any repository file changes.")
    if len(changed) > _MAX_FILES:
        raise AgentOutputError(f"OpenHands changed more than {_MAX_FILES} files.")
    return sorted(changed, key=lambda item: item["path"])


def _run_sdk_sync(
    user_request: str,
    evidence: dict[str, Any],
    provider: Any,
) -> dict[str, Any]:
    """Run the SDK in a temporary workspace and return only validated changed file contents."""
    try:
        from openhands.sdk import LLM, Agent, Conversation
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

    api_key = getattr(provider, "api_key", None)
    model = getattr(provider, "model", None)
    base_url = getattr(provider, "base_url", None)
    if not api_key or not model:
        raise AgentOutputError("OpenHands developer backend requires configured model credentials.")

    with tempfile.TemporaryDirectory(prefix="brain-openhands-") as temporary_dir:
        root = Path(temporary_dir).resolve()
        repository = evidence.get("repository") or snapshot.get("repository")
        base_ref = snapshot.get("default_branch")
        workspace_mode, workspace_detail = _prepare_workspace(
            root,
            repository if isinstance(repository, str) else "",
            original,
            token=get_setting("BRAIN_GITHUB_TOKEN"),
            ref=base_ref if isinstance(base_ref, str) and base_ref else None,
        )

        llm = LLM(**_sdk_llm_kwargs(model, api_key, base_url))
        agent = Agent(llm=llm, tools=_developer_tools(base_url))
        hook_dir = Path(tempfile.mkdtemp(prefix="brain-hooks-"))
        hook_config, hook_log = build_hook_config(hook_dir, root)
        conversation = Conversation(
            agent=agent, workspace=str(root), hook_config=hook_config
        )
        conversation.send_message(_task_prompt(user_request, evidence, workspace_mode))
        conversation.run()

        changed = (
            _collect_git_change_set(root)
            if workspace_mode == "checkout"
            else _collect_change_set(root, original)
        )

    if workspace_mode == "checkout":
        workspace_note = f"a git checkout of {workspace_detail}"
    else:
        workspace_note = f"a seeded temporary workspace ({workspace_detail})"
    return {
        "status": "PASS",
        "deliverables": {
            "change_set": {
                "summary": "Implement requirements with OpenHands SDK",
                "files": changed,
            },
            "implementation_notes": (
                f"OpenHands SDK produced {len(changed)} changed file(s) in {workspace_note}. "
                "The developer agent may have run local commands there; those runs are "
                "advisory. Brain's GitHub Actions check runner provides the authoritative evidence."
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
