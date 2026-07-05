"""Pytest configuration."""

import pytest
from pathlib import Path

# Ensure workspace directories exist for tests
from brain.core.config import load_config
from brain.storage.paths import WorkspacePaths


@pytest.fixture(autouse=True, scope="session")
def setup_workspace():
    """Set up workspace for tests."""
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