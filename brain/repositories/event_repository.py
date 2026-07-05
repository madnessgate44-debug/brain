"""Event repository."""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from sqlalchemy.sql.expression import select as sa_select

from brain.db.models import MissionEventModel
from brain.core.ids import generate_event_id
from brain.core.clock import utc_now
from brain.domain.enums import EventSeverity


class EventRepository:
    """Event repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_next_sequence(self, mission_id: str) -> int:
        """Get next sequence number for a mission."""
        # Get max sequence number
        query = select(func.max(MissionEventModel.sequence_number)).where(
            MissionEventModel.mission_id == mission_id
        )
        result = await self.session.execute(query)
        max_seq = result.scalar()
        return (max_seq or 0) + 1
    
    async def append_event(
        self,
        mission_id: str,
        event_type: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        phase: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> MissionEventModel:
        """Append a new event to a mission."""
        sequence_number = await self.get_next_sequence(mission_id)
        
        event = MissionEventModel(
            id=generate_event_id(),
            mission_id=mission_id,
            event_type=event_type,
            phase=phase,
            severity=severity.value,
            message=message,
            payload_json=payload_json,
            sequence_number=sequence_number,
            created_at=utc_now(),
        )
        self.session.add(event)
        await self.session.flush()
        return event
    
    async def list_for_mission(
        self,
        mission_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MissionEventModel]:
        """List events for a mission ordered by sequence number."""
        query = (
            select(MissionEventModel)
            .where(MissionEventModel.mission_id == mission_id)
            .order_by(MissionEventModel.sequence_number.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_event_count(self, mission_id: str) -> int:
        """Get total event count for a mission."""
        query = select(func.count()).select_from(MissionEventModel).where(
            MissionEventModel.mission_id == mission_id
        )
        result = await self.session.execute(query)
        return result.scalar() or 0