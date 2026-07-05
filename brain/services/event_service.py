"""Event service."""

import logging
from typing import List, Optional

from brain.repositories.event_repository import EventRepository
from brain.schemas.event import EventResponse, EventCreate
from brain.domain.enums import EventSeverity

logger = logging.getLogger("brain.services.event_service")


class EventService:
    """Service for event operations."""
    
    def __init__(self, event_repo: EventRepository):
        self.event_repo = event_repo
    
    async def list_events(
        self,
        mission_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EventResponse]:
        """List events for a mission."""
        events = await self.event_repo.list_for_mission(
            mission_id=mission_id,
            limit=limit,
            offset=offset,
        )
        return [EventResponse(**e.to_dict()) for e in events]
    
    async def create_event(self, data: EventCreate) -> EventResponse:
        """Create a new event."""
        event = await self.event_repo.append_event(
            mission_id=data.mission_id,
            event_type=data.event_type,
            message=data.message,
            severity=data.severity,
            phase=data.phase,
            payload_json=str(data.payload) if data.payload else None,
        )
        return EventResponse(**event.to_dict())