"""Tests for the swarmchat-coordination skill's bootstrap script.

These exercise the real SwarmChat server when the package is installed, and skip
cleanly when it is not (CI does not depend on swarmchat). No mocks: a real server is
started in a temporary data directory and a real blocking wait is observed.
"""

import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("swarmchat")

SCRIPT = Path(__file__).resolve().parents[1] / "watcher" / "skills" / "swarmchat-coordination" / "scripts" / "swarm_setup.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def swarm(tmp_path):
    """Run the bootstrap script to completion and return its result."""
    port = _free_port()
    data = tmp_path / "data"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--data", str(data), "--port", str(port),
         "--agents", "watcher,shadow", "--demo"],
        capture_output=True, text=True, timeout=90,
    )
    yield data, port, proc
    # Stop the server the script left running.
    subprocess.run(["pkill", "-f", f"swarmchat serve --data {data}"], check=False)
    shutil.rmtree(data, ignore_errors=True)


def test_setup_writes_private_env(swarm):
    data, _, proc = swarm
    assert proc.returncode == 0, proc.stdout + proc.stderr
    env_file = data / "agents.env"
    assert env_file.exists()
    mode = env_file.stat().st_mode & 0o777
    assert mode == 0o600, f"agents.env must be private, got {oct(mode)}"
    body = env_file.read_text()
    assert "SWARMCHAT_SERVER=" in body
    assert "SWARMCHAT_TOKEN_WATCHER=" in body and "SWARMCHAT_TOKEN_SHADOW=" in body


def test_blocking_wait_demo_passes(swarm):
    _, _, proc = swarm
    assert "blocking wait (watcher -> shadow): PASS" in proc.stdout, proc.stdout + proc.stderr
