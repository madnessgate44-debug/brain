"""The role skill loader wires brain/company/skills/<role>.md into role prompts."""

from brain.company.agent_runner import _SKILLS_DIR, _skill_block, load_role_skill
from brain.company.roles import ROLE_CATALOG


def test_every_role_has_a_skill_file():
    missing = [role.key for role in ROLE_CATALOG if not (_SKILLS_DIR / f"{role.key}.md").is_file()]
    assert missing == []


def test_load_role_skill_returns_file_contents():
    text = load_role_skill("code_reviewer")
    assert "Independent Code Reviewer" in text
    assert text.strip() == text


def test_skill_block_wraps_skill_with_role_header():
    block = _skill_block("release_manager")
    assert block.startswith("\n\nROLE SKILL (release_manager):")
    assert "Release Manager" in block


def test_missing_skill_is_not_an_error():
    assert load_role_skill("no_such_role") == ""
    assert _skill_block("no_such_role") == ""
