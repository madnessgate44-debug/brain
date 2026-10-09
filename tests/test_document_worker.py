"""Tests for Brain's deterministic document worker."""

import pytest

from brain.runtime.workers.document_worker import build_mission_brief


def test_build_mission_brief_contains_real_mission_content() -> None:
    result = build_mission_brief("Market scan", "Compare three competitors.")

    assert result.startswith("# Mission Brief: Market scan")
    assert "Compare three competitors." in result
    assert "does not claim" in result
    assert len(result.encode("utf-8")) > 0


@pytest.mark.parametrize(
    ("title", "objective"),
    [("", "Objective"), ("Title", "  ")],
)
def test_build_mission_brief_rejects_empty_inputs(title: str, objective: str) -> None:
    with pytest.raises(ValueError):
        build_mission_brief(title, objective)
