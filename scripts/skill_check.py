#!/usr/bin/env python3
"""W7 check: do we consult the skills we were given, and does the OS require it?

The owner installed a large skill library and asked why it is not used before each task. This
check makes the answer mechanical instead of a promise:

  1. The controlling procedure (ENGINEERING_EXECUTION_OS.md) must require a skill check in its
     TOOL DECLARATION, so every turn has to name the skills it considered.
  2. Every one of the nine company roles must have a skill file, so the roles are not bare.

Exit 0 when both hold; exit 1 with the exact missing item otherwise.

    python3 scripts/skill_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OS = REPO / "ENGINEERING_EXECUTION_OS.md"
SKILLS_DIR = REPO / "brain" / "company" / "skills"
ROLES = REPO / "brain" / "company" / "roles.py"


def main() -> int:
    problems: list[str] = []

    os_text = OS.read_text(encoding="utf-8") if OS.is_file() else ""
    if "Skills considered" not in os_text:
        problems.append(
            f"{OS.name}: TOOL DECLARATION does not require a 'Skills considered' line (W7 open)"
        )
    if "Skill check (mandatory)" not in os_text:
        problems.append(f"{OS.name}: no mandatory skill-check clause (W7 open)")
    if "scripts/skills.py" not in os_text:
        problems.append(
            f"{OS.name}: the OS does not require the skill router (scripts/skills.py) (W7 open)"
        )

    # The router must actually find skills and rank them, or the check is hollow.
    router = REPO / "scripts" / "skills.py"
    if not router.is_file():
        problems.append("scripts/skills.py is missing (no skill router)")
    else:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_skills_router", router)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found = mod.all_skills()
        if len(found) < 10:
            problems.append(f"skill router found only {len(found)} skills (expected the library)")
        hits = mod.suggest("review this PR for correctness and security")
        if not hits:
            problems.append("skill router matched no skill for a PR review (routing is broken)")

    role_keys: list[str] = []
    if ROLES.is_file():
        import re

        role_keys = re.findall(r'key="([a-z_]+)"', ROLES.read_text(encoding="utf-8"))
    if not role_keys:
        problems.append(f"{ROLES.name}: no role keys found (cannot verify skills)")
    for key in role_keys:
        if not (SKILLS_DIR / f"{key}.md").is_file():
            problems.append(f"role '{key}' has no skill file (brain/company/skills/{key}.md)")

    if problems:
        print("FAIL - W7 (we do not consult the skills we were given)")
        for p in problems:
            print(f"  [ ] {p}")
        return 1

    print(f"OK - skill check required by the OS; all {len(role_keys)} roles have a skill file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
