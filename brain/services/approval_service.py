"""Approval service."""

import json
import logging
from datetime import timezone
from typing import Optional

from brain.domain.enums import ApprovalStatus, EventSeverity, MissionPhase, MissionStatus
from brain.repositories.approval_repository import ApprovalRepository
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.schemas.approval import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalResponseCreate,
)
from brain.core.clock import parse_iso, utc_now

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
        if mission.status != MissionStatus.PENDING.value:
            raise ValueError(
                "Approval requests must be created before mission execution; "
                f"mission status is {mission.status}."
            )

        expires_at = parse_iso(data.expires_at) if data.expires_at else None
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= utc_now():
                raise ValueError("Approval expiration must be in the future.")
        approval = await self.approval_repo.create(
            mission_id=mission_id,
            approval_type=data.approval_type,
            reason=data.reason,
            expires_at=expires_at,
            payload_json=json.dumps(data.payload, ensure_ascii=False) if data.payload else None,
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
            payload_json=json.dumps({"approval_id": approval.id, "reason": data.reason}, ensure_ascii=False),
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

        expires_at = approval.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= utc_now():
                expired = await self.approval_repo.expire_if_pending(approval_id)
                if expired is None:
                    current = await self.approval_repo.get_by_id(approval_id)
                    if current is None:
                        raise ValueError(f"Approval {approval_id} not found")
                    raise RuntimeError(f"Approval {approval_id} is already {current.status}")
                await self.mission_repo.update_approval_state(
                    approval.mission_id, ApprovalStatus.EXPIRED.value
                )
                await self.event_repo.append_event(
                    mission_id=approval.mission_id,
                    event_type="approval_expired",
                    message="Approval expired before a response was recorded",
                    phase=MissionPhase.WAITING_FOR_APPROVAL.value,
                    severity=EventSeverity.WARNING,
                    payload_json=json.dumps({"approval_id": approval_id}, ensure_ascii=False),
                )
                return ApprovalRequestResponse(**expired.to_dict())

        updated = await self.approval_repo.respond(
            approval_id=approval_id,
            approved=data.approved,
            response_note=data.response_note,
        )
        if updated is None:
            current = await self.approval_repo.get_by_id(approval_id)
            if current is None:
                raise ValueError(f"Approval {approval_id} not found")
            raise RuntimeError(f"Approval {approval_id} is already {current.status}")

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
            payload_json=json.dumps({
                "approval_id": approval_id,
                "approved": data.approved,
                "response_note": data.response_note,
            }, ensure_ascii=False),
        )
        logger.info(
            "Approval %s responded: %s",
            approval_id,
            mission_state,
            extra={"approval_id": approval_id, "mission_id": approval.mission_id},
        )
        return ApprovalRequestResponse(**updated.to_dict())
