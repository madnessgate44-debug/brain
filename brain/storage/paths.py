"""Workspace path management."""

from pathlib import Path
from typing import List

from brain.core.config import WorkspaceConfig


class WorkspacePaths:
    """Workspace path utilities."""
    
    def __init__(self, config: WorkspaceConfig):
        self.config = config
        self.root = Path(config.root)
    
    def config_dir(self) -> Path:
        """Get config directory path."""
        return self.root / self.config.config_dir
    
    def db_dir(self) -> Path:
        """Get database directory path."""
        return self.root / self.config.db_dir
    
    def missions_dir(self) -> Path:
        """Get missions directory path."""
        return self.root / self.config.missions_dir
    
    def logs_dir(self) -> Path:
        """Get logs directory path."""
        return self.root / self.config.logs_dir
    
    def tmp_dir(self) -> Path:
        """Get temporary directory path."""
        return self.root / self.config.tmp_dir
    
    def mission_dir(self, mission_id: str) -> Path:
        """Get mission-specific directory path."""
        return self.missions_dir() / mission_id
    
    def mission_artifacts_dir(self, mission_id: str) -> Path:
        """Get mission artifacts directory path."""
        return self.mission_dir(mission_id) / "artifacts"
    
    def mission_work_dir(self, mission_id: str) -> Path:
        """Get mission work directory path."""
        return self.mission_dir(mission_id) / "work"
    
    def all_paths(self) -> List[Path]:
        """Get all workspace directories."""
        return [
            self.root,
            self.config_dir(),
            self.db_dir(),
            self.missions_dir(),
            self.logs_dir(),
            self.tmp_dir(),
        ]