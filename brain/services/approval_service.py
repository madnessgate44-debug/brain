"""Approval service."""

import logging
from typing import Optional

from brain.domain.enums import ApprovalStatus, MissionPhase, MissionStatus
from brain.repositories.approval_repository import ApprovalRepository
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.schemas.approval import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalResponseCreate,
)
from brain.core.clock import utc_now, parse_iso

logger = logging.getLogger("brain.services.approval_service")


class ApprovalService:
    """Service for approval operations."""
    
    def __init__(
        self,
        approval_repo: ApprovalRepository,
        mission_repo: MissionRepository,
        event_repo: EventRepository,
    ):
        self.approval_repo = approval_repo
        self.mission_repo = mission_repo
        self.event_repo = event_repo
    
    async def create_approval_request(
        self,
        mission_id: str,
        data: ApprovalRequestCreate,
    ) -> ApprovalRequestResponse:
        """Create an approval request for a mission."""
        # Verify mission exists
        mission = await self.mission_repo.get_by_id(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")
        
        # Parse expires_at if provided
        expires_at = None
        if data.expires_at:
            expires_at = parse_iso(data.expires_at)
        
        # Create approval
        approval = await self.approval_repo.create(
            mission_id=mission_id,
            approval_type=data.approval_type,
            reason=data.reason,
            expires_at=expires_at,
            payload_json=str(data.payload) if data.payload else None,
        )
        
        # Update mission approval state
        await self.mission_repo.update_approval