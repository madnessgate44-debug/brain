"""Artifact service."""

import logging
from typing import List, Optional

from brain.repositories.artifact_repository import ArtifactRepository
from brain.schemas.artifact import ArtifactCreate, ArtifactResponse

logger = logging.getLogger("brain.services.artifact_service")


class ArtifactService:
    """Service for artifact operations."""
    
    def __init__(self, artifact_repo: ArtifactRepository):
        self.artifact_repo = artifact_repo
    
    async def create_artifact(
        self,
        mission_id: str,
        data: ArtifactCreate,
    ) -> ArtifactResponse:
        """Create a new artifact."""
        artifact = await self.artifact_repo.create(
            mission_id=mission_id,
            artifact_type=data.artifact_type,
            logical_name=data.logical_name,
            relative_path=data.relative_path,
            mime_type=data.mime_type,
            size_bytes=data.size_bytes,
            metadata_json=str(data.metadata) if data.metadata else None,
        )
        
        logger.info(
            f"Artifact {artifact.id} created for mission {mission_id}",
            extra={"artifact_id": artifact.id, "mission_id": mission_id}
        )
        
        return ArtifactResponse(**artifact.to_dict())
    
    async def list_artifacts(
        self,
        mission_id: str,
    ) -> List[ArtifactResponse]:
        """List artifacts for a mission."""
        artifacts = await self.artifact_repo.list_for_mission(mission_id)
        return [ArtifactResponse(**a.to_dict()) for a in artifacts]