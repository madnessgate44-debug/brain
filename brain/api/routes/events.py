"""Event API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from brain.schemas.event import EventResponse
from brain.services.event_service import EventService
from brain.api.deps import get_event_service

router = APIRouter(prefix="/missions/{mission_id}/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    mission_id: str,
    limit: int = 100,
    offset: int = 0,
    service: EventService = Depends(get_event_service),
):
    """List mission events ordered by sequence number."""
    events = await service.list_events(mission_id, limit=limit, offset=offset)
    return events