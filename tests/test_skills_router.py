"""Tests for the skill router (find the relevant skill before starting work)."""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "skills.py"


@pytest.fixture(scope="module")
def sk():
    spec = importlib.util.spec_from_file_location("skills_router", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_router_discovers_the_skill_library(sk):
    assert len(sk.all_skills()) >= 10


def test_router_matches_a_pr_review(sk):
    names = [h["name"] for h in sk.suggest("review this PR for correctness and security")]
    assert names, "a PR review must match a review skill"


def test_router_matches_a_migration(sk, monkeypatch):
    # The repo ships no migration skill; the router must still rank one when it
    # is present. Inject it so the test does not depend on the machine's skill cache.
    skill = {
        "name": "database-migrations",
        "description": "Write a reversible database migration and change the schema.",
        "triggers": ["database migration"],
        "source": "test",
    }
    monkeypatch.setattr(sk, "all_skills", lambda: [skill])
    names = [h["name"] for h in sk.suggest("write a database migration and change the schema")]
    assert any("migration" in n for n in names)


def test_router_declaration_line_names_skills(sk):
    line = sk._line("review this PR")
    assert line.startswith("- Skills considered:")
    assert "score" in line


def test_router_declaration_says_none_when_nothing_matches(sk, monkeypatch):
    monkeypatch.setattr(sk, "all_skills", lambda: [])
    assert "none matched" in sk._line("qwertyuiop zxcvbnm")


def test_trigger_beats_description(sk):
    skill = {"name": "x", "description": "generic", "triggers": ["review this pr"]}
    assert sk.score(skill, "review this PR") >= 5
