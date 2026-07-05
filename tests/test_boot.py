"""Boot service tests."""

import pytest
from pathlib import Path

from brain.api.app import create_app
from brain.core.config import load_config


def test_app_creation():
    """Test FastAPI app creation."""
    app = create_app()
    assert app is not None
    assert app.title == "Brain V1 API"


def test_config_loading():
    """Test configuration loading."""
    config = load_config()
    assert config is not None
    assert config.system.instance_id is not None
    assert config.database.sqlite_path is not None


def test_workspace_creation(tmp_path):
    """Test workspace directory creation."""
    config = load_config()
    # Override workspace root for testing
    config.workspace.root = str(tmp_path / "workspace")
    
    from brain.storage.paths import WorkspacePaths
    paths = WorkspacePaths(config.workspace)
    
    for path in paths.all_paths():
        path.mkdir(parents=True, exist_ok=True)
        assert path.exists()