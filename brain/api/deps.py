"""API dependencies."""

import hmac
from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, HTTPException, Request, status

from brain.db.session import DatabaseSessionManager, get_db_session
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.repositories.approval_repository import ApprovalRepository
from brain.repositories.artifact_repository import ArtifactRepository
from brain.services.mission_service import MissionService
from brain.services.event_service import EventService
from brain.services.approval_service import ApprovalService
from brain.services.artifact_service import ArtifactService
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.storage.artifact_store import ArtifactStore
from brain.company.settings import get_setting


async def require_control_key(
    api_key: str | None = Header(default=None, alias="X-Brain-API-Key"),
) -> None:
    """Require the shared control key for mission and state-changing API routes."""
    expected_key = get_setting("BRAIN_CONTROL_API_KEY")
    if not expected_key or len(expected_key) < 24:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brain control API is disabled: configure BRAIN_CONTROL_API_KEY with at least 24 characters.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Brain control key.",
        )


async def get_db(request: Request) -> AsyncGenerator:
    """Get database session."""
    db_manager: DatabaseSessionManager = request.app.state.db_manager
    async with get_db_session(db_manager) as session:
        yield session


async def get_mission_repository(
    db=Depends(get_db)
) -> MissionRepository:
    """Get mission repository."""
    return MissionRepository(db)


async def get_event_repository(
    db=Depends(get_db)
) -> EventRepository:
    """Get event repository."""
    return EventRepository(db)


async def get_approval_repository(
    db=Depends(get_db)
) -> ApprovalRepository:
    """Get approval repository."""
    return ApprovalRepository(db)


async def get_artifact_repository(
    db=Depends(get_db)
) -> ArtifactRepository:
    """Get artifact repository."""
    return ArtifactRepository(db)


async def get_artifact_store(
    request: Request
) -> ArtifactStore:
    """Get artifact store."""
    config = request.app.state.config
    return ArtifactStore(config.workspace.root)


async def get_mission_service(
    request: Request,
    mission_repo: MissionRepository = Depends(get_mission_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    artifact_store: ArtifactStore = Depends(get_artifact_store),
) -> MissionService:
    """Get mission service with a session factory for background execution."""
    session_factory = request.app.state.db_manager.get_session_factory()
    return MissionService(mission_repo, event_repo, artifact_store, session_factory)


async def get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
) -> EventService:
    """Get event service."""
    return EventService(event_repo)


async def get_approval_service(
    approval_repo: ApprovalRepository = Depends(get_approval_repository),
    mission_repo: MissionRepository = Depends(get_mission_repository),
    event_repo: EventRepository = Depends(get_event_repository),
) -> ApprovalService:
    """Get approval service."""
    return ApprovalService(approval_repo, mission_repo, event_repo)


async def get_artifact_service(
    artifact_repo: ArtifactRepository = Depends(get_artifact_repository),
) -> ArtifactService:
    """Get artifact service."""
    return ArtifactService(artifact_repo)


async def get_runtime_registry(
    request: Request
) -> RuntimeRegistry:
    """Get runtime registry."""
    return request.app.state.boot_service.runtime_registry