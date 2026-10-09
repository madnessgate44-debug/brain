"""Authenticated entry point for Brain browser missions."""

import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from brain.api.deps import get_mission_service, get_runtime_registry
from brain.company.settings import get_setting
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.runtime.workers.browser_worker import (
    BrowserPolicyError,
    browser_dispatch_payload,
    sign_browser_dispatch,
    validate_browser_actions,
)
from brain.schemas.mission import MissionCreate
from brain.services.mission_service import MissionService

router = APIRouter(prefix="/browser", tags=["browser"])


class BrowserTaskCreate(BaseModel):
    """A bounded browser mission submitted by an authenticated owner."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1, max_length=10_000)
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=25)
    owner_approved: bool = False


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def create_browser_task(
    data: BrowserTaskCreate,
    service: MissionService = Depends(get_mission_service),
    registry: RuntimeRegistry = Depends(get_runtime_registry),
    api_key: str | None = Header(default=None, alias="X-Brain-API-Key"),
):
    """Create and start a signed browser mission; never accept unsigned dispatches."""
    expected_key = get_setting("BRAIN_CONTROL_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser control is disabled until BRAIN_CONTROL_API_KEY is configured.",
        )
    if len(expected_key) < 24:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BRAIN_CONTROL_API_KEY must contain at least 24 characters for signed browser dispatch.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Brain control key.",
        )

    try:
        actions = validate_browser_actions(data.actions)
    except BrowserPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    mutating = any(action["op"] in {"click", "type", "press"} for action in actions)
    if mutating and not data.owner_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task contains mutating browser actions. Set owner_approved=true only after the owner explicitly approves this exact task.",
        )

    metadata = {
        "workflow_type": "browser",
        "browser_actions": actions,
        "browser_owner_approved": data.owner_approved,
        "browser_dispatch_signature": "",
    }
    try:
        mission = await service.create_mission(
            MissionCreate(
                title=data.title,
                objective=data.objective,
                risk_level="HIGH" if mutating else "LOW",
                metadata=metadata,
            )
        )
        payload = browser_dispatch_payload(
            mission.id, data.title, data.objective, actions, data.owner_approved
        )
        metadata["browser_dispatch_signature"] = sign_browser_dispatch(expected_key, payload)
        model = await service.mission_repo.get_by_id(mission.id)
        if model is None:
            raise RuntimeError("created browser mission could not be reloaded")
        model.metadata_json = json.dumps(metadata, ensure_ascii=False)
        await service.mission_repo.session.commit()
        started = await service.start_mission(mission.id, registry)
    except BrowserPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "mission_id": mission.id,
        "status": started.status.value,
        "message": "Browser task accepted. Inspect the mission events and artifacts for verified results.",
        "status_endpoint": f"/missions/{mission.id}",
        "events_endpoint": f"/missions/{mission.id}/events",
        "artifacts_endpoint": f"/missions/{mission.id}/artifacts",
    }
