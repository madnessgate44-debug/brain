"""Recovery service tests."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from brain.db.models import Base
from brain.services.recovery_service import RecoveryService
from brain.core.config import Config
from brain.db.session import DatabaseSessionManager
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.domain.enums import MissionPhase, MissionStatus
from brain.repositories.mission_repository import MissionRepository


@pytest.fixture
async def db_manager():
    """Create test database manager."""
    # Use in-memory SQLite for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    manager = DatabaseSessionManager(":memory:")
    manager._engine = engine
    return manager


@pytest.mark.asyncio
async def test_recovery_service(db_manager):
    """Test recovery service."""
    config = Config()
    config.recovery.auto_recover = True
    config.recovery.recoverable_phases = ["EXECUTE", "VALIDATE", "REPAIR"]
    
    registry = RuntimeRegistry()
    recovery = RecoveryService(config, db_manager, registry)
    
    # Run recovery (should handle no missions gracefully)
    await recovery.recover()
    
    # Verify recovery ran without errors
    # This is a basic test; more comprehensive testing would require
    # setting up missions in recoverable states


@pytest.mark.asyncio
async def test_interrupted_active_mission_is_paused_instead_of_replayed(db_manager):
    config = Config()
    config.recovery.auto_recover = True
    config.recovery.recoverable_phases = ["EXECUTE", "VALIDATE", "REPAIR"]

    async with db_manager.get_session_factory()() as session:
        repo = MissionRepository(session)
        mission = await repo.create(
            title="Interrupted mission",
            objective="Avoid replaying external side effects",
        )
        mission_id = mission.id
        await repo.update_phase(mission_id, MissionPhase.EXECUTE)
        await repo.update_status(mission_id, MissionStatus.RUNNING)
        await session.commit()

    recovery = RecoveryService(config, db_manager, RuntimeRegistry())
    await recovery.recover()

    async with db_manager.get_session_factory()() as session:
        recovered = await MissionRepository(session).get_by_id(mission_id)

    assert recovered is not None
    assert recovered.status == MissionStatus.PAUSED.value
    assert recovered.phase == MissionPhase.EXECUTE.value
    assert recovered.assigned_runtime_id is None
    assert recovered.recovery_state == "recovery_requires_manual_review_from_EXECUTE"



@pytest.mark.asyncio
async def test_recovery_does_not_pause_a_mission_with_a_recent_heartbeat(db_manager):
    config = Config()
    config.recovery.auto_recover = True
    config.recovery.recoverable_phases = ["EXECUTE", "VALIDATE", "REPAIR"]
    config.recovery.orphan_detection_grace_period_seconds = 300

    async with db_manager.get_session_factory()() as session:
        repo = MissionRepository(session)
        mission = await repo.create(
            title="Recently active mission",
            objective="Do not interrupt a live runtime",
        )
        mission_id = mission.id
        started = await repo.try_start(mission_id, "runtime_live")
        assert started is True
        await session.commit()

    recovery = RecoveryService(config, db_manager, RuntimeRegistry())
    await recovery.recover()

    async with db_manager.get_session_factory()() as session:
        recovered = await MissionRepository(session).get_by_id(mission_id)

    assert recovered is not None
    assert recovered.status == MissionStatus.RUNNING.value
    assert recovered.assigned_runtime_id == "runtime_live"
    assert recovered.recovery_state is None
