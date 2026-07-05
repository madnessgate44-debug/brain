"""Mission repository."""

from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_

from brain.db.models import MissionModel
from brain.domain.enums import MissionPhase, MissionStatus
from brain.core.ids import generate_mission_id
from brain.core.clock import utc_now


class MissionRepository:
    """Mission repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        title: str,
        objective: str,
        priority: str = "MEDIUM",
        risk_level: str = "LOW",
        max_loop_iterations: int = 10,
        metadata_json: Optional[str] = None,
    ) -> MissionModel:
        """Create a new mission."""
        mission = MissionModel(
            id=generate_mission_id(),
            title=title,
            objective=objective,
            phase=MissionPhase.INTAKE.value,
            status=MissionStatus.PENDING.value,
            priority=priority,
            risk_level=risk_level,
            max_loop_iterations=max_loop_iterations,
            approval_state="NOT_REQUIRED",
            metadata_json=metadata_json,
            current_loop_iteration=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(mission)
        await self.session.flush()
        return mission
    
    async def get_by_id(self, mission_id: str) -> Optional[MissionModel]:
        """Get mission by ID."""
        query = select(MissionModel).where(MissionModel.id == mission_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[MissionStatus] = None,
    ) -> Tuple[List[MissionModel], int]:
        """List missions with pagination and optional status filter."""
        query = select(MissionModel)
        count_query = select(func.count()).select_from(MissionModel)
        
        if status is not None:
            query = query.where(MissionModel.status == status.value)
            count_query = count_query.where(MissionModel.status == status.value)
        
        # Order by created_at descending
        query = query.order_by(MissionModel.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        missions = result.scalars().all()
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()
        
        return missions, total
    
    async def update_phase(self, mission_id: str, phase: MissionPhase) -> None:
        """Update mission phase."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(phase=phase.value, updated_at=utc_now())
        )
    
    async def update_status(self, mission_id: str, status: MissionStatus) -> None:
        """Update mission status."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(status=status.value, updated_at=utc_now())
        )
    
    async def increment_loop_iteration(self, mission_id: str) -> None:
        """Increment loop iteration count."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                current_loop_iteration=MissionModel.current_loop_iteration + 1,
                updated_at=utc_now()
            )
        )
    
    async def attach_runtime(
        self,
        mission_id: str,
        runtime_id: str,
        heartbeat: Optional[datetime] = None,
    ) -> None:
        """Attach runtime to mission."""
        if heartbeat is None:
            heartbeat = utc_now()
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                assigned_runtime_id=runtime_id,
                last_heartbeat_at=heartbeat,
                updated_at=utc_now(),
            )
        )
    
    async def clear_runtime(self, mission_id: str) -> None:
        """Clear runtime from mission."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                assigned_runtime_id=None,
                last_heartbeat_at=None,
                updated_at=utc_now(),
            )
        )
    
    async def mark_failed(self, mission_id: str, error_summary: str) -> None:
        """Mark mission as failed."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                status=MissionStatus.FAILED.value,
                phase=MissionPhase.FAILED.value,
                error_summary=error_summary,
                updated_at=utc_now(),
            )
        )
    
    async def mark_completed(self, mission_id: str) -> None:
        """Mark mission as completed."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                status=MissionStatus.COMPLETED.value,
                phase=MissionPhase.COMPLETE.value,
                updated_at=utc_now(),
            )
        )
    
    async def update_approval_state(self, mission_id: str, approval_state: str) -> None:
        """Update mission approval state."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                approval_state=approval_state,
                updated_at=utc_now(),
            )
        )
    
    async def find_recoverable_missions(
        self,
        recoverable_phases: List[str],
    ) -> List[MissionModel]:
        """Find missions in recoverable phases."""
        # Find missions that are in recoverable phases and not already completed or failed
        query = select(MissionModel).where(
            and_(
                MissionModel.phase.in_(recoverable_phases),
                ~MissionModel.status.in_([
                    MissionStatus.COMPLETED.value,
                    MissionStatus.FAILED.value,
                    MissionStatus.CANCELLED.value,
                ])
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_recovery_state(
        self,
        mission_id: str,
        recovery_state: str,
    ) -> None:
        """Update mission recovery state."""
        await self.session.execute(
            update(MissionModel)
            .where(MissionModel.id == mission_id)
            .values(
                recovery_state=recovery_state,
                updated_at=utc_now(),
            )
        )