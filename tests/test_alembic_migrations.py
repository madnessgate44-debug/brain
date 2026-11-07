"""The documented `alembic upgrade head` setup step must actually run."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_environment_is_complete():
    """`alembic upgrade head` cannot run without env.py and script.py.mako."""
    assert (ROOT / "alembic" / "env.py").is_file()
    assert (ROOT / "alembic" / "script.py.mako").is_file()


def test_alembic_upgrade_head_creates_schema(tmp_path):
    db_path = tmp_path / "brain.db"
    env = {**os.environ, "DATABASE__SQLITE_PATH": str(db_path)}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    connection = sqlite3.connect(db_path)
    try:
        names = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
    finally:
        connection.close()
    assert {"missions", "mission_events", "approvals", "artifacts", "runtime_leases"} <= names
