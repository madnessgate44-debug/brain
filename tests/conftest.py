"""Pytest configuration."""

import os
from pathlib import Path

import pytest

# Ensure workspace directories exist for tests
from brain.core.config import load_config
from brain.storage.paths import WorkspacePaths


@pytest.fixture(autouse=True, scope="session")
def setup_workspace():
    """Set up workspace for tests."""
    # Isolate the app's database as well as its artifact workspace from local data.
    previous_db_path = os.environ.get("DATABASE__SQLITE_PATH")
    os.environ["DATABASE__SQLITE_PATH"] = "./test_workspace/db/brain.db"
    config = load_config()
    # Use a test workspace
    config.workspace.root = "./test_workspace"
    paths = WorkspacePaths(config.workspace)
    
    for path in paths.all_paths():
        path.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Cleanup
    import shutil
    if Path("./test_workspace").exists():
        shutil.rmtree("./test_workspace")