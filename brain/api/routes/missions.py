"""Mission API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from brain.domain.enums import MissionStatus
from brain.schemas.mission import (
    MissionCreate,
    MissionResponse,
    MissionListResponse,
    MissionStartResponse,
)
from brain.services.mission_service import MissionService
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.api.deps import get_mission_service, get_runtime_registry

router = APIRouter(prefix="/missions", tags=["missions"])


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    data: MissionCreate,
    service: MissionService = Depends(get_mission_service),
):
    """Create a new mission."""
    try:
        mission = await service.create_mission(data)
        return mission
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=MissionListResponse)
async def list_missions(
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[MissionStatus] = None,
    service: MissionService = Depends(get_mission_service),
):
    """List missions with pagination."""
    missions, total = await service.list_missions(
        limit=limit,
        offset=offset,
        status=status_filter
    )
    return MissionListResponse(
        missions=missions,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: str,
    service: MissionService = Depends(get_mission_service),
):
    """Get mission details."""
    mission = await service.get_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found"
        )
    return mission


@router.post("/{mission_id}/start", response_model=MissionStartResponse)
async def start_mission(
    mission_id: str,
    service: MissionService = Depends(get_mission_service),
    registry: RuntimeRegistry = Depends(get_runtime_registry),
):
    """Start a mission."""
    try:
        mission = await service.start_mission(mission_id, registry)
        return MissionStartResponse(
            mission_id=mission_id,
            status=mission.status.value,
            phase=mission.phase.value,
            runtime_id=mission.assigned_runtime_id,
            message="Mission started successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))