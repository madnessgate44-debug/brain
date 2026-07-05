"""Mission service."""

import logging
from typing import Optional, List, Tuple

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
    ):
        self.mission_repo = mission_repo
        self.event_repo = event_repo
        self.artifact_store = artifact_store
    
    async def create_mission(self, data: MissionCreate) -> MissionResponse:
        """Create a new mission."""
        # Validate input
        if not data.title or not data.objective:
            raise ValueError("Title and objective are required")
        
        # Create mission
        mission = await self.mission_repo.create(
            title=data.title,
            objective=data.objective,
            priority=data.priority or "MEDIUM",
            risk_level=data.risk_level or "LOW",
            max_loop_iterations=data.max_loop_iterations or 10,
            metadata_json=str(data.metadata) if data.metadata else None,
        )
        
        # Ensure session is fresh
        await self.mission_repo.session.flush()
        
        # Emit mission_created event
        await self.event_repo.append_event(
            mission_id=mission.id,
            event_type="mission_created",
            message=f"Mission '{data.title}' created",
            phase=MissionPhase.INTAKE.value,
            severity="INFO",
            payload_json=str({"title": data.title, "objective": data.objective}),
        )
        
        # Create mission artifact directory
        self.artifact_store.ensure_mission_dir(mission.id)
        
        logger.info(
            f"Mission {mission.id} created",
            extra={"mission_id": mission.id, "title": data.title}
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
        return [MissionResponse(**m.to_dict()) for m in missions], total
    
    async def start_mission(
        self,
        mission_id: str,
        runtime_registry: RuntimeRegistry,
    ) -> MissionResponse:
        """Start a mission."""
        mission = await self.mission_repo.get_by_id(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")
        
        # Check if mission can be started
        if mission.status in [MissionStatus.RUNNING.value, MissionStatus.COMPLETED.value]:
            raise RuntimeError(f"Mission {mission_id} is already {mission.status}")
        
        if mission.status == MissionStatus.FAILED.value:
            raise RuntimeError(f"Mission {mission_id} has failed and cannot be started")
        
        # Generate runtime ID
        runtime_id = generate_runtime_id()
        
        # Update mission state
        await self.mission_repo.update_phase(mission_id, MissionPhase.EXECUTE)
        await self.mission_repo.update_status(mission_id, MissionStatus.RUNNING)
        await self.mission_repo.attach_runtime(mission_id, runtime_id, utc_now())
        
        # Emit mission_started event
        await self.event_repo.append_event(
            mission_id=mission_id,
            event_type="mission_started",
            message=f"Mission started with runtime {runtime_id}",
            phase=MissionPhase.EXECUTE.value,
            severity="INFO",
            payload_json=str({"runtime_id": runtime_id}),
        )
        
        # Create runtime task
        runtime = MissionRuntime(
            mission_id=mission_id,
            runtime_id=runtime_id,
            mission_repo=self.mission_repo,
            event_repo=self.event_repo,
            max_iterations=mission.max_loop_iterations,
        )
        
        # Register and start runtime
        runtime_registry.register(runtime)
        await runtime_registry.start(mission_id)
        
        # Refresh mission
        updated_mission = await self.mission_repo.get_by_id(mission_id)
        
        logger.info(
            f"Mission {mission_id} started",
            extra={"mission_id": mission_id, "runtime_id": runtime_id}
        )
        
        return MissionResponse(**updated_mission.to_dict())