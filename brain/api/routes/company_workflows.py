"""Authenticated endpoint for starting a software-company workflow."""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from brain.api.deps import get_mission_service, get_runtime_registry
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.schemas.mission import MissionCreate
from brain.services.mission_service import MissionService

router = APIRouter(prefix="/company-workflows", tags=["company-workflows"])


class CompanyWorkflowCreate(BaseModel):
    """Input for a repository-specific software-company mission."""

    title: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1)
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_company_workflow(
    data: CompanyWorkflowCreate,
    service: MissionService = Depends(get_mission_service),
    registry: RuntimeRegistry = Depends(get_runtime_registry),
    api_key: str | None = Header(default=None, alias="X-Brain-API-Key"),
):
    """Queue the specialist pipeline and return the durable mission identifier."""
    expected_key = os.getenv("BRAIN_CONTROL_API_KEY", "")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Company workflow control is disabled until BRAIN_CONTROL_API_KEY is configured.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Brain control key.",
        )

    try:
        mission = await service.create_mission(
            MissionCreate(
                title=data.title,
                objective=data.objective,
                metadata={
                    "workflow_type": "software_company",
                    "repository": data.repository,
                },
            )
        )
        started = await service.start_mission(mission.id, registry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "mission_id": mission.id,
        "status": started.status.value,
        "repository": data.repository,
        "message": "Company workflow queued. Check mission events and artifacts for verified progress.",
        "status_endpoint": f"/missions/{mission.id}",
        "events_endpoint": f"/missions/{mission.id}/events",
        "artifacts_endpoint": f"/missions/{mission.id}/artifacts",
    }
