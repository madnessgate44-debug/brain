"""The live routing code must target the canonical hub, not the legacy Day-1 channel.

Brain's ticketing protocol moved the durable hub to issue #292 (docs/TICKETING_PROTOCOL.md,
2026-11-07). Several modules still hardcoded the old #240: the bridge helper (`hub.py`), the
bridge loop (`loop.py`), the channel core (`watcher_channel.py`), and Shadow's report
(`shadow/report.py`). This guards the reconciliation so a future edit cannot silently point
the live receiver back at the retired channel. Historical #240 records are intentionally
preserved elsewhere and are not asserted here.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = 292


def _load(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolves string annotations via sys.modules, so register first.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_bridge_hub_defaults_to_canonical_issue():
    hub = _load("bridge_hub_recon", ROOT / "watcher" / "bridge" / "hub.py")
    assert hub.HUB == CANONICAL
    assert hub.REPO == "madnessgate44-debug/brain"


def test_bridge_loop_defaults_to_canonical_issue():
    loop = _load("bridge_loop_recon", ROOT / "watcher" / "bridge" / "loop.py")
    assert loop.ISSUE == CANONICAL


def test_channel_core_defaults_to_canonical_issue():
    channel = _load("watcher_channel_recon", ROOT / "scripts" / "watcher_channel.py")
    assert channel.DEFAULT_ISSUE == CANONICAL


def test_shadow_report_defaults_to_canonical_issue():
    report = _load("shadow_report_recon", ROOT / "shadow" / "report.py")
    assert report.HUB_ISSUE == CANONICAL


def test_brain_hub_issue_env_override_is_honoured():
    """The env var is read at import, so assert it in a fresh interpreter."""
    hub_path = ROOT / "watcher" / "bridge" / "hub.py"
    code = (
        "import importlib.util\n"
        f"p = {str(hub_path)!r}\n"
        "s = importlib.util.spec_from_file_location('h', p)\n"
        "m = importlib.util.module_from_spec(s)\n"
        "s.loader.exec_module(m)\n"
        "print(m.HUB)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={"BRAIN_HUB_ISSUE": "999", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "999"


def test_current_protocol_docs_name_the_canonical_hub():
    workflow = (ROOT / "docs" / "WORKFLOW.md").read_text(encoding="utf-8")
    assert "brain#292" in workflow
    # The header must not call the retired #240 the single reference hub.
    assert "single reference for how a ticket looks on hub `madnessgate44-debug/brain#240`" not in workflow


def test_watcher_daily_workflow_no_longer_routes_to_240():
    text = (ROOT / ".github" / "workflows" / "watcher-daily.yml").read_text(encoding="utf-8")
    assert "#240" not in text
    assert "hub #292" in text
