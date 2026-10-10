"""Event API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from brain.schemas.event import EventResponse
from brain.services.event_service import EventService
from brain.api.deps import get_event_service, require_control_key

router = APIRouter(
    prefix="/missions/{mission_id}/events",
    tags=["events"],
    dependencies=[Depends(require_control_key)],
)


@router.get("", response_model=list[EventResponse])
async def list_events(
    mission_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EventService = Depends(get_event_service),
):
    """List mission events ordered by sequence number."""
    events = await service.list_events(mission_id, limit=limit, offset=offset)
    return events