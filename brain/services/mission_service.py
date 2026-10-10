"""Mission service."""

import logging
import json
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from brain.domain.enums import MissionPhase, MissionStatus
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.storage.artifact_store import ArtifactStore
from brain.schemas.mission import MissionCreate, MissionResponse
from brain.core.ids import generate_runtime_id
from brain.core.clock import utc_now
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.runtime.mission_runtime import MissionRuntime

logger = logging.getLogger("brain.services.mission_service")


class MissionService:
    """Service for mission operations."""

    def __init__(
        self,
        mission_repo: MissionRepository,
        event_repo: EventRepository,
        artifact_store: ArtifactStore,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.mission_repo = mission_repo
        self.event_repo = event_repo
        self.artifact_store = artifact_store
        self.session_factory = session_factory

    async def create_mission(self, data: MissionCreate) -> MissionResponse:
        """Create a new mission."""
        if not data.title or not data.objective:
            raise ValueError("Title and objective are required")

        mission = await self.mission_repo.create(
            title=data.title,
            objective=data.objective,
            priority=data.priority or "MEDIUM",
            risk_level=data.risk_level or "LOW",
            max_loop_iterations=data.max_loop_iterations or 10,
            metadata_json=json.dumps(data.metadata, ensure_ascii=False) if data.metadata else None,
        )
        await self.mission_repo.session.flush()
        await self.event_repo.append_event(
            mission_id=mission.id,
            event_type="mission_created",
            message=f"Mission '{data.title}' created",
            phase=MissionPhase.INTAKE.value,
            severity="INFO",
            payload_json=json.dumps({"title": data.title, "objective": data.objective}, ensure_ascii=False),
        )
        self.artifact_store.ensure_mission_dir(mission.id)

        logger.info(
            "Mission %s created",
            mission.id,
            extra={"mission_id": mission.id, "title": data.title},
        )
        return MissionResponse(**mission.to_dict())

    async def get_mission(self, mission_id: str) -> Optional[MissionResponse]:
        """Get mission by ID."""
        mission = await self.mission_repo.get_by_id(mission_id)
        if mission:
            return MissionResponse(**mission.to_dict())
        return None

    async def list_missions(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[MissionStatus] = None,
    ) -> Tuple[List[MissionResponse], int]:
        """List missions with pagination."""
        missions, total = await self.mission_repo.list(
            limit=limit,
            offset=offset,
            status=status,
        )
        return [MissionResponse(**mission.to_dict()) for mission in missions], total

    async def start_mission(
        self,
        mission_id: str,
        runtime_registry: RuntimeRegistry,
    ) -> MissionResponse:
        """Start a mission."""
        mission = await self.mission_repo.get_by_id(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")
        if mission.status != MissionStatus.PENDING.value:
            raise RuntimeError(
                f"Mission {mission_id} cannot be started from status {mission.status}; "
                "only PENDING missions can start. Paused missions require explicit resume support."
            )

        runtime_id = generate_runtime_id()
        heartbeat = utc_now()
        if not await self.mission_repo.try_start(mission_id, runtime_id, heartbeat):
            current = await self.mission_repo.get_by_id(mission_id)
            if current is None:
                raise ValueError(f"Mission {mission_id} not found")
            raise RuntimeError(
                f"Mission {mission_id} could not be started because its status changed to {current.status}"
            )
        await self.event_repo.append_event(
            mission_id=mission_id,
            event_type="mission_started",
            message=f"Mission started with runtime {runtime_id}",
            phase=MissionPhase.EXECUTE.value,
            severity="INFO",
            payload_json=json.dumps({"runtime_id": runtime_id}),
        )

        # Persist the running state before the independent background session reads it.
        await self.mission_repo.session.commit()

        runtime = MissionRuntime(
            mission_id=mission_id,
            runtime_id=runtime_id,
            session_factory=self.session_factory,
            artifact_store=self.artifact_store,
            max_iterations=mission.max_loop_iterations,
        )
        runtime_registry.register(runtime)
        await runtime_registry.start(mission_id)

        updated_mission = await self.mission_repo.get_by_id(mission_id)
        logger.info(
            "Mission %s started",
            mission_id,
            extra={"mission_id": mission_id, "runtime_id": runtime_id},
        )
        return MissionResponse(**updated_mission.to_dict())
