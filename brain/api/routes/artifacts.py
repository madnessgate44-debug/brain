"""Artifact API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from brain.schemas.artifact import ArtifactCreate, ArtifactResponse
from brain.services.artifact_service import ArtifactService
from brain.api.deps import get_artifact_service

router = APIRouter(prefix="/missions/{mission_id}/artifacts", tags=["artifacts"])


@router.get("", response_model=list[ArtifactResponse])
async def list_artifacts(
    mission_id: str,
    service: ArtifactService = Depends(get_artifact_service),
):
    """List artifacts for a mission."""
    artifacts = await service.list_artifacts(mission_id)
    return artifacts


@router.post("", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    mission_id: str,
    data: ArtifactCreate,
    service: ArtifactService = Depends(get_artifact_service),
):
    """Create an artifact for a mission."""
    try:
        artifact = await service.create_artifact(mission_id, data)
        return artifact
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))