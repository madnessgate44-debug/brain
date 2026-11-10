"""docs/LOOP.md grants a merge only when the Shadow audit returns Verified.

The Shadow workflow used to fail only on REJECTED, so a BLOCKED audit (no model route
configured) produced a *green* check that read as "audited" while nothing was audited —
the exact "optimise for what is easy to prove" habit in watcher/knowledge/WEAKNESSES.md.
This pins the gate: only VERIFIED passes, everything else fails closed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHADOW_AUDIT = ROOT / ".github" / "workflows" / "shadow-audit.yml"
WATCHER_DAILY = ROOT / ".github" / "workflows" / "watcher-daily.yml"


def _steps(workflow: Path) -> list[dict]:
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return data["jobs"]["audit"]["steps"] if workflow is SHADOW_AUDIT else data["jobs"]["cycle"]["steps"]


def _gate_step() -> dict:
    for step in _steps(SHADOW_AUDIT):
        if "Gate the merge" in step.get("name", ""):
            return step
    raise AssertionError("no merge-gate step found in shadow-audit.yml")


def _run_gate(verdict: str) -> subprocess.CompletedProcess:
    script = _gate_step()["run"]
    return subprocess.run(
        ["bash", "-c", script],
        env={"VERDICT": verdict, "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )


def test_gate_runs_even_when_the_audit_fails():
    # If the gate were skipped on a failed audit step, a BLOCKED verdict would never be judged.
    assert _gate_step().get("if") == "always()"


def test_only_verified_passes_the_gate():
    assert _run_gate("VERIFIED").returncode == 0


def test_blocked_and_other_verdicts_fail_closed():
    for verdict in ("BLOCKED", "REJECTED", "PARTIAL", ""):
        result = _run_gate(verdict)
        assert result.returncode == 1, f"verdict {verdict!r} should fail the gate"
        assert "::error::" in result.stdout


def test_watcher_daily_runs_the_readiness_checks():
    # BLOCKER_REGISTER B6: the Phase-1 checks must run in the daily cycle, not only by hand.
    script = WATCHER_DAILY.read_text(encoding="utf-8")
    assert "watcher/knowledge/tools/purpose_audit.py" in script
    assert "scripts/agent_status.py" in script
    assert "scripts/skill_check.py" in script
