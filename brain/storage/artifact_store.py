"""Artifact storage management."""

import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from brain.storage.paths import WorkspacePaths
from brain.core.config import WorkspaceConfig

logger = logging.getLogger("brain.storage.artifact_store")


class ArtifactStore:
    """Artifact storage helper."""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.paths = WorkspacePaths(
            WorkspaceConfig(
                root=str(self.workspace_root),
                config_dir="config",
                db_dir="db",
                missions_dir="missions",
                logs_dir="logs",
                tmp_dir="tmp",
            )
        )
    
    def ensure_mission_dir(self, mission_id: str) -> Path:
        """Ensure mission directory exists and return its path."""
        mission_dir = self.paths.mission_dir(mission_id)
        mission_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        artifacts_dir = self.paths.mission_artifacts_dir(mission_id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        work_dir = self.paths.mission_work_dir(mission_id)
        work_dir.mkdir(parents=True, exist_ok=True)
        
        return mission_dir
    
    def get_artifact_path(
        self,
        mission_id: str,
        logical_name: str,
        ensure_dir: bool = True,
    ) -> Path:
        """Get the file path for an artifact."""
        artifacts_dir = self.paths.mission_artifacts_dir(mission_id)
        if ensure_dir:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize logical name for filesystem
        safe_name = "".join(c for c in logical_name if c.isalnum() or c in "._-")
        return artifacts_dir / safe_name
    
    def save_artifact(
        self,
        mission_id: str,
        logical_name: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Save an artifact to storage."""
        path = self.get_artifact_path(mission_id, logical_name)
        
        # Write content
        with open(path, "wb") as f:
            f.write(content)
        
        # Save metadata if provided
        if metadata:
            meta_path = path.with_suffix(path.suffix + ".meta")
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
        
        logger.info(
            f"Artifact saved: {logical_name} for mission {mission_id}",
            extra={"mission_id": mission_id, "logical_name": logical_name}
        )
        
        return path
    
    def load_artifact(
        self,
        mission_id: str,
        logical_name: str,
    ) -> Optional[bytes]:
        """Load an artifact from storage."""
        path = self.get_artifact_path(mission_id, logical_name, ensure_dir=False)
        if not path.exists():
            return None
        
        with open(path, "rb") as f:
            return f.read()
    
    def delete_artifact(
        self,
        mission_id: str,
        logical_name: str,
    ) -> bool:
        """Delete an artifact from storage."""
        path = self.get_artifact_path(mission_id, logical_name, ensure_dir=False)
        if not path.exists():
            return False
        
        path.unlink()
        
        # Delete metadata file if exists
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            meta_path.unlink()
        
        return True
    
    def delete_mission_artifacts(self, mission_id: str) -> None:
        """Delete all artifacts for a mission."""
        artifacts_dir = self.paths.mission_artifacts_dir(mission_id)
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)
            logger.info(
                f"Deleted artifacts for mission {mission_id}",
                extra={"mission_id": mission_id}
            )