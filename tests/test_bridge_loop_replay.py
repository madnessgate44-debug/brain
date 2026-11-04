"""The bridge loop must not replay a reply it has already posted.

Regression: the daily workflow runs `loop.py --once` in CI, where the checkout is
thrown away, so the `last_seen_id` written to state.json never reaches main. The
loop kept reading a pinned value, treated the same counterpart comment as new on
every run, and re-posted the identical reply once a day (hub #240, 2026-11-02..04).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "watcher", "bridge"))

import loop  # noqa: E402


def _our_reply(ack_id: int) -> dict:
    return {
        "id": ack_id + 1,
        "body": (
            "## T19 · reply\n"
            f"**ACK** got `{ack_id}` (GitHub time 2026-11-01T19:00:21Z); staying on T19.\n"
            "— Watcher · 2026-11-01T19:01:00Z · _AI agent (OpenHands) on behalf of the owner._\n"
        ),
    }


def _counterpart(cid: int) -> dict:
    return {"id": cid, "body": "## WATCHER REQUEST — HOSSAM / COPILOT\n**Ticket ID:** HOS-001"}


def test_last_ack_id_reads_the_high_water_mark():
    comments = [
        _our_reply(6556303579),
        _counterpart(6562445652),
        _our_reply(6562445652),
    ]
    assert loop.last_ack_id(comments) == 6562445652


def test_last_ack_id_ignores_counterpart_acks():
    comments = [_counterpart(6562445652)]
    assert loop.last_ack_id(comments) == 0


def test_stale_state_does_not_replay_an_answered_comment():
    comments = [_counterpart(6562445652), _our_reply(6562445652)]

    # What main did before the fix: state pinned, so the answered comment looked new.
    assert loop.newest_counterpart(comments, 6556428043) is not None

    # After the fix the thread's own high-water mark wins.
    recovered = max(6556428043, loop.last_ack_id(comments))
    assert loop.newest_counterpart(comments, recovered) is None


def test_a_genuinely_new_counterpart_is_still_answered():
    comments = [_counterpart(6562445652), _our_reply(6562445652), _counterpart(6562445653)]
    recovered = max(6556428043, loop.last_ack_id(comments))
    assert loop.newest_counterpart(comments, recovered)["id"] == 6562445653
