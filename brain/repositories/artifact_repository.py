"""Artifact repository."""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from brain.db.models import ArtifactModel
from brain.domain.enums import ArtifactType
from brain.core.ids import generate_artifact_id
from brain.core.clock import utc_now


class ArtifactRepository:
    """Artifact repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        mission_id: str,
        artifact_type: ArtifactType,
        logical_name: str,
        relative_path: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        metadata_json: Optional[str] = None,
    ) -> ArtifactModel:
        """Create a new artifact record."""
        artifact = ArtifactModel(
            id=generate_artifact_id(),
            mission_id=mission_id,
            artifact_type=artifact_type.value,
            logical_name=logical_name,
            relative_path=relative_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            metadata_json=metadata_json,
            created_at=utc_now(),
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact
    
    async def list_for_mission(
        self,
        mission_id: str,
    ) -> List[ArtifactModel]:
        """List artifacts for a mission."""
        query = (
            select(ArtifactModel)
            .where(ArtifactModel.mission_id == mission_id)
            .order_by(ArtifactModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()