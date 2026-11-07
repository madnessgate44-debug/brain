"""R5: a conversation survives a process restart (persist then resume)."""

from __future__ import annotations

from pathlib import Path

from brain.company import session


def _agent():
    from openhands.sdk import LLM, Agent

    return Agent(llm=LLM(model="gemini/gemini-2.5-flash", api_key="dummy"), tools=[])


def test_session_persists_then_resumes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIN_SESSION_DIR", str(tmp_path / "sessions"))
    ws = tmp_path / "ws"
    ws.mkdir()

    assert session.is_resumable("mission-1") is False

    first = session.open_conversation("mission-1", ws, _agent)
    first.send_message("hello from the first process")
    assert session.is_resumable("mission-1") is True

    # Simulate a restart: a new process reopens with the same id. The factory must not
    # be called on the resume path (no credentials needed to read history).
    def _boom():
        raise AssertionError("agent_factory must not run on the resume path")

    resumed = session.open_conversation("mission-1", ws, _boom)

    assert str(resumed.id) == str(first.id)
    assert len(list(resumed.state.events)) >= 1


def test_distinct_session_ids_are_isolated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIN_SESSION_DIR", str(tmp_path / "sessions"))
    ws = tmp_path / "ws"
    ws.mkdir()

    a = session.open_conversation("mission-a", ws, _agent)
    a.send_message("only in a")

    assert session.is_resumable("mission-a") is True
    assert session.is_resumable("mission-b") is False
