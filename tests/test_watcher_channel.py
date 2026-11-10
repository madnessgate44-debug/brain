"""Tests for the Watcher <-> ChatGPT channel protocol (scripts/watcher_channel.py).

These exercise the real decision logic used by the live issue_comment receiver:
fail-closed matching, dedup by comment id, and the reply loop guard.
"""

import pytest

from scripts.watcher_channel import (
    DEFAULT_REPOSITORY,
    Decision,
    InMemorySeenStore,
    IncomingComment,
    assert_reply_is_loop_safe,
    build_reply,
    evaluate,
)


def event(
    *,
    comment_id=1001,
    body="[TO-WATCHER] hello @watcher",
    login="madnessgate44-debug",
    repository=DEFAULT_REPOSITORY,
    issue=292,
):
    return {
        "comment": {"id": comment_id, "body": body, "user": {"login": login}},
        "repository": {"full_name": repository},
        "issue": {"number": issue},
    }


def test_accepts_marker_addressed_owner_comment():
    comment = IncomingComment.from_event(event())
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.HANDLE


def test_accepts_task_prefix_without_marker():
    comment = IncomingComment.from_event(event(body="[TO-WATCHER] status please"))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.HANDLE


def test_skips_comment_without_marker():
    comment = IncomingComment.from_event(event(body="just chatting, no marker"))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_MARKER


def test_skips_wrong_repository():
    comment = IncomingComment.from_event(event(repository="someone/else"))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_REPOSITORY


def test_skips_wrong_issue():
    comment = IncomingComment.from_event(event(issue=999))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_ISSUE


def test_skips_bot_sender_case_insensitively():
    comment = IncomingComment.from_event(event(login="openhands-ai[BOT]"))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_BOT


def test_skips_own_reply_to_prevent_loop():
    comment = IncomingComment.from_event(event(body="[TO-CHATGPT] done @watcher oops"))
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_LOOP


def test_dedup_claims_each_comment_id_once():
    seen = InMemorySeenStore()
    comment = IncomingComment.from_event(event(comment_id=4242))
    assert evaluate(comment, seen=seen) is Decision.HANDLE
    assert evaluate(comment, seen=seen) is Decision.SKIP_DUPLICATE


def test_distinct_comment_ids_each_handled():
    seen = InMemorySeenStore()
    first = IncomingComment.from_event(event(comment_id=1))
    second = IncomingComment.from_event(event(comment_id=2))
    assert evaluate(first, seen=seen) is Decision.HANDLE
    assert evaluate(second, seen=seen) is Decision.HANDLE


def test_skipped_comment_does_not_consume_id():
    seen = InMemorySeenStore()
    wrong_issue = IncomingComment.from_event(event(comment_id=7, issue=1))
    assert evaluate(wrong_issue, seen=seen) is Decision.SKIP_ISSUE
    # The same id on the right issue is still first-seen, so it is handled.
    fixed = IncomingComment.from_event(event(comment_id=7))
    assert evaluate(fixed, seen=seen) is Decision.HANDLE


def test_malformed_event_is_rejected():
    comment = IncomingComment.from_event({"comment": {}, "repository": {}, "issue": {}})
    assert evaluate(comment, seen=InMemorySeenStore()) is Decision.SKIP_MALFORMED


def test_reply_contains_required_evidence_fields():
    reply = build_reply(
        handshake_id="WATCHER-TEST-001",
        source_comment_id=6554141035,
        received_how="automatic event",
        summary="Read the message; acknowledged.",
        run_id="run-1",
        conversation_id="conv-1",
        automation_id="auto-1",
    )
    assert reply.startswith("[TO-CHATGPT]")
    for token in (
        "WATCHER-TEST-001",
        "6554141035",
        "automatic event",
        "run-1",
        "conv-1",
        "auto-1",
    ):
        assert token in reply


def test_reply_reports_human_opened_session_truthfully():
    reply = build_reply(
        handshake_id="WATCHER-TEST-002",
        source_comment_id=1,
        received_how="human-opened session",
        summary="Read the message in a human-opened session.",
    )
    assert "human-opened session" in reply


def test_reply_never_contains_trigger_marker():
    reply = build_reply(
        handshake_id="WATCHER-TEST-003",
        source_comment_id=1,
        received_how="automatic event",
        summary="body that mentions the marker only via assert",
    )
    assert_reply_is_loop_safe(reply)


def test_loop_guard_rejects_marker_in_reply():
    with pytest.raises(ValueError, match="trigger marker"):
        assert_reply_is_loop_safe("reply that leaks @watcher")
