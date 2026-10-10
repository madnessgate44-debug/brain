"""Approval repository."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from brain.db.models import ApprovalModel
from brain.domain.enums import ApprovalStatus, ApprovalType
from brain.core.ids import generate_approval_id
from brain.core.clock import utc_now


class ApprovalRepository:
    """Approval repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        mission_id: str,
        approval_type: ApprovalType,
        reason: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        payload_json: Optional[str] = None,
    ) -> ApprovalModel:
        """Create a new approval request."""
        approval = ApprovalModel(
            id=generate_approval_id(),
            mission_id=mission_id,
            approval_type=approval_type.value,
            status=ApprovalStatus.PENDING.value,
            reason=reason,
            requested_at=utc_now(),
            expires_at=expires_at,
            payload_json=payload_json,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval
    
    async def get_by_id(self, approval_id: str) -> Optional[ApprovalModel]:
        """Get approval by ID."""
        query = select(ApprovalModel).where(ApprovalModel.id == approval_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_for_mission(
        self,
        mission_id: str,
    ) -> List[ApprovalModel]:
        """List approvals for a mission."""
        query = (
            select(ApprovalModel)
            .where(ApprovalModel.mission_id == mission_id)
            .order_by(ApprovalModel.requested_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def list_all(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[ApprovalModel]:
        """List recent approvals, optionally filtered by status."""
        query = select(ApprovalModel).order_by(ApprovalModel.requested_at.desc()).limit(limit)
        if status_filter:
            query = query.where(ApprovalModel.status == status_filter)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def expire_if_pending(self, approval_id: str) -> Optional[ApprovalModel]:
        """Atomically expire an approval only while it remains pending."""
        result = await self.session.execute(
            update(ApprovalModel)
            .where(
                ApprovalModel.id == approval_id,
                ApprovalModel.status == ApprovalStatus.PENDING.value,
            )
            .values(
                status=ApprovalStatus.EXPIRED.value,
                responded_at=utc_now(),
            )
        )
        await self.session.flush()
        if result.rowcount != 1:
            return None
        return await self.get_by_id(approval_id)

    async def respond(
        self,
        approval_id: str,
        approved: bool,
        response_note: Optional[str] = None,
    ) -> Optional[ApprovalModel]:
        """Respond to an approval request."""
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        result = await self.session.execute(
            update(ApprovalModel)
            .where(
                ApprovalModel.id == approval_id,
                ApprovalModel.status == ApprovalStatus.PENDING.value,
            )
            .values(
                status=status.value,
                responded_at=utc_now(),
                response_note=response_note,
            )
        )
        await self.session.flush()
        if result.rowcount != 1:
            return None
        return await self.get_by_id(approval_id)