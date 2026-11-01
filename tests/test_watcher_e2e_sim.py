"""End-to-end simulation of the Watcher loop (offline, hermetic).

Runs scripts/e2e_sim.py, which drives the REAL loop.py / hub.py / shadow.py against
a local fake GitHub + Gemini server. Guards against regressions in the reply
envelope, the loop guard, the measured-timestamp rule, hub read/post, and the
Shadow self-audit path.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_watcher_e2e_sim_passes():
    p = subprocess.run(
        [sys.executable, "scripts/e2e_sim.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert p.returncode == 0, f"e2e sim failed:\n{p.stdout}\n{p.stderr}"
    assert "8/8 checks passed" in p.stdout, p.stdout
