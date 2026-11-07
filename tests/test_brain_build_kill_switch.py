from pathlib import Path


def test_brain_build_requires_explicit_enable_switch():
    workflow = Path(".github/workflows/brain-build.yml").read_text(encoding="utf-8")
    prepare = workflow.split("  prepare:\n", 1)[1].split("\n  mission:", 1)[0]
    condition = prepare.split("    runs-on:", 1)[0]
    assert "vars.BRAIN_BUILD_ENABLED == 'true' &&" in condition
