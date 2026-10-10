"""Approval service."""

import logging
from typing import Optional

from brain.domain.enums import ApprovalStatus, EventSeverity, MissionPhase
from brain.repositories.approval_repository import ApprovalRepository
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.schemas.approval import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalResponseCreate,
)
from brain.core.clock import parse_iso

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

    async def list_approvals(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> list[ApprovalRequestResponse]:
        """List recent approval requests for the authenticated owner."""
        approvals = await self.approval_repo.list_all(status_filter=status_filter, limit=limit)
        return [ApprovalRequestResponse(**approval.to_dict()) for approval in approvals]

    async def create_approval_request(
        self,
        mission_id: str,
        data: ApprovalRequestCreate,
    ) -> ApprovalRequestResponse:
        """Create an approval request for an existing mission."""
        mission = await self.mission_repo.get_by_id(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        expires_at = parse_iso(data.expires_at) if data.expires_at else None
        approval = await self.approval_repo.create(
            mission_id=mission_id,
            approval_type=data.approval_type,
            reason=data.reason,
            expires_at=expires_at,
            payload_json=str(data.payload) if data.payload else None,
        )
        await self.mission_repo.update_approval_state(
            mission_id, ApprovalStatus.PENDING.value
        )
        await self.event_repo.append_event(
            mission_id=mission_id,
            event_type="approval_requested",
            message="Approval requested: " + data.approval_type.value,
            phase=MissionPhase.WAITING_FOR_APPROVAL.value,
            severity=EventSeverity.INFO,
            payload_json=str({"approval_id": approval.id, "reason": data.reason}),
        )
        return ApprovalRequestResponse(**approval.to_dict())

    async def respond_to_approval(
        self,
        approval_id: str,
        data: ApprovalResponseCreate,
    ) -> ApprovalRequestResponse:
        """Record an approval decision and update the mission's approval state."""
        approval = await self.approval_repo.get_by_id(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        if approval.status != ApprovalStatus.PENDING.value:
            raise RuntimeError(f"Approval {approval_id} is already {approval.status}")

        updated = await self.approval_repo.respond(
            approval_id=approval_id,
            approved=data.approved,
            response_note=data.response_note,
        )
        if updated is None:
            raise ValueError(f"Approval {approval_id} not found")

        mission_state = (
            ApprovalStatus.APPROVED.value if data.approved else ApprovalStatus.REJECTED.value
        )
        await self.mission_repo.update_approval_state(approval.mission_id, mission_state)
        await self.event_repo.append_event(
            mission_id=approval.mission_id,
            event_type="approval_responded",
            message="Approval " + mission_state.lower(),
            phase=MissionPhase.WAITING_FOR_APPROVAL.value,
            severity=EventSeverity.INFO,
            payload_json=str({
                "approval_id": approval_id,
                "approved": data.approved,
                "response_note": data.response_note,
            }),
        )
        logger.info(
            "Approval %s responded: %s",
            approval_id,
            mission_state,
            extra={"approval_id": approval_id, "mission_id": approval.mission_id},
        )
        return ApprovalRequestResponse(**updated.to_dict())
