"""Tests for the W7 skill check: the OS must require a skill check; roles must have skills."""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "skill_check.py"


@pytest.fixture(scope="module")
def sc():
    spec = importlib.util.spec_from_file_location("skill_check", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_check_passes_on_the_real_repo(sc):
    assert sc.main() == 0


def test_skill_check_fails_when_os_drops_the_clause(sc, tmp_path, monkeypatch):
    os_file = tmp_path / "ENGINEERING_EXECUTION_OS.md"
    os_file.write_text("# OS\nno skill clause here\n", encoding="utf-8")
    monkeypatch.setattr(sc, "OS", os_file)
    assert sc.main() == 1


def test_skill_check_fails_when_a_role_has_no_skill(sc, tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "developer.md").write_text("x", encoding="utf-8")
    roles = tmp_path / "roles.py"
    roles.write_text('SpecialistRole(key="developer")\nSpecialistRole(key="qa_engineer")\n', encoding="utf-8")
    monkeypatch.setattr(sc, "SKILLS_DIR", skills)
    monkeypatch.setattr(sc, "ROLES", roles)
    assert sc.main() == 1


def test_all_nine_roles_have_a_skill_file(sc):
    import re

    keys = re.findall(r'key="([a-z_]+)"', sc.ROLES.read_text(encoding="utf-8"))
    assert len(keys) == 9
    for key in keys:
        assert (sc.SKILLS_DIR / f"{key}.md").is_file(), key
