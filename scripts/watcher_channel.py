"""Deterministic core for the Watcher <-> ChatGPT GitHub issue-comment channel.

The live receiver is an OpenHands Cloud Automation watching issue #292 for
``issue_comment.created`` events. This module is the auditable, testable contract
that the receiver and any future GitHub Actions fallback share: fail-closed
matching, dedup by comment id, a reply loop guard, and the exact evidence fields
the acceptance test requires. It performs no network access and holds no secrets.

The acceptance test (issue #292) is: two consecutive handoffs complete without a
human opening a session. A reply may only claim RECEIVED when this module returns
``HANDLE`` and the receiver actually posted the reply.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol

MARKER = "@watcher"
TASK_PREFIX = "[TO-WATCHER]"
REPLY_PREFIX = "[TO-CHATGPT]"
DEFAULT_REPOSITORY = "madnessgate44-debug/brain"
# Canonical hub per docs/TICKETING_PROTOCOL.md (2026-11-07): issue #292. #240 is the
# legacy Day-1 channel, retained only in historical records. Override with BRAIN_HUB_ISSUE.
DEFAULT_ISSUE = int(os.environ.get("BRAIN_HUB_ISSUE", "292"))


class Decision(str, Enum):
    """Outcome of evaluating one incoming comment. Only ``HANDLE`` may reply."""

    HANDLE = "HANDLE"
    SKIP_MALFORMED = "SKIP_MALFORMED"
    SKIP_REPOSITORY = "SKIP_REPOSITORY"
    SKIP_ISSUE = "SKIP_ISSUE"
    SKIP_BOT = "SKIP_BOT"
    SKIP_LOOP = "SKIP_LOOP"
    SKIP_MARKER = "SKIP_MARKER"
    SKIP_DUPLICATE = "SKIP_DUPLICATE"


class SeenStore(Protocol):
    """Dedup store. ``claim`` returns True only for the first sighting of an id."""

    def claim(self, comment_id: int) -> bool:  # pragma: no cover - protocol
        ...


class InMemorySeenStore:
    """Reference dedup store. The live receiver uses the automation KV store."""

    def __init__(self) -> None:
        self._seen: set[int] = set()

    def claim(self, comment_id: int) -> bool:
        if comment_id in self._seen:
            return False
        self._seen.add(comment_id)
        return True


@dataclass(frozen=True)
class IncomingComment:
    """The subset of a GitHub ``issue_comment`` payload this channel needs."""

    comment_id: int
    body: str
    sender_login: str
    repository: str
    issue_number: int

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "IncomingComment":
        comment = event.get("comment") or {}
        repo = event.get("repository") or {}
        issue = event.get("issue") or {}
        sender = comment.get("user") or {}
        return cls(
            comment_id=comment.get("id"),
            body=comment.get("body") or "",
            sender_login=(sender.get("login") or ""),
            repository=(repo.get("full_name") or ""),
            issue_number=issue.get("number"),
        )


def evaluate(
    comment: IncomingComment,
    *,
    seen: SeenStore,
    repository: str = DEFAULT_REPOSITORY,
    issue_number: int = DEFAULT_ISSUE,
) -> Decision:
    """Decide whether this comment starts a Watcher run.

    Fail-closed order: malformed payload, wrong repository, wrong issue, bot
    sender, our own reply (loop guard), missing trigger marker, then dedup.
    Dedup is claimed last so a skipped comment never consumes an id.
    """
    if comment.comment_id is None or not comment.repository or comment.issue_number is None:
        return Decision.SKIP_MALFORMED
    if comment.repository.casefold() != repository.casefold():
        return Decision.SKIP_REPOSITORY
    if comment.issue_number != issue_number:
        return Decision.SKIP_ISSUE
    if comment.sender_login.casefold().endswith("[bot]"):
        return Decision.SKIP_BOT
    body = comment.body or ""
    if REPLY_PREFIX.casefold() in body.casefold():
        return Decision.SKIP_LOOP
    if MARKER.casefold() not in body.casefold() and TASK_PREFIX.casefold() not in body.casefold():
        return Decision.SKIP_MARKER
    if not seen.claim(int(comment.comment_id)):
        return Decision.SKIP_DUPLICATE
    return Decision.HANDLE


def assert_reply_is_loop_safe(body: str) -> None:
    """A Watcher reply must not contain the trigger marker, or it re-triggers."""
    if MARKER.casefold() in body.casefold():
        raise ValueError(f"reply must not contain the trigger marker {MARKER!r}")


def build_reply(
    *,
    handshake_id: str,
    source_comment_id: int,
    received_how: str,
    summary: str,
    run_id: str | None = None,
    conversation_id: str | None = None,
    automation_id: str | None = None,
    event: str = "issue_comment.created",
    timestamp: datetime | None = None,
    extra_lines: tuple[str, ...] = (),
) -> str:
    """Build one ``[TO-CHATGPT]`` reply carrying the required evidence fields.

    ``received_how`` must state the truth: ``automatic event`` (the receiver run
    fired with no human) or ``human-opened session``. Never claim RECEIVED unless
    the run exists.
    """
    stamp = (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lines = [
        REPLY_PREFIX,
        "",
        f"- handshake id: `{handshake_id}`",
        f"- source comment id: `{source_comment_id}`",
        f"- received how: {received_how}",
        f"- event: `{event}`",
        f"- automation id: `{automation_id}`" if automation_id else "- automation id: none",
        f"- automation run id: `{run_id}`" if run_id else "- automation run id: none",
        (
            f"- OpenHands conversation id: `{conversation_id}`"
            if conversation_id
            else "- OpenHands conversation id: none"
        ),
        f"- timestamp (UTC): `{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        "",
        summary.strip(),
    ]
    if extra_lines:
        lines.append("")
        lines.extend(extra_lines)
    body = "\n".join(lines)
    assert_reply_is_loop_safe(body)
    return body
