"""Recovery service tests."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from brain.db.models import Base
from brain.services.recovery_service import RecoveryService
from brain.core.config import Config
from brain.db.session import DatabaseSessionManager
from brain.runtime.runtime_registry import RuntimeRegistry


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
async def test_recovery_normalizes_running_missions_once_and_does_not_reprocess_paused_or_pending(db_manager):
    from brain.domain.enums import MissionPhase, MissionStatus
    from brain.repositories.mission_repository import MissionRepository
    from brain.db.session import get_db_session

    config = Config()
    config.recovery.auto_recover = True
    config.recovery.recoverable_phases = ["EXECUTE", "VALIDATE", "REPAIR", "WAITING_FOR_APPROVAL"]
    recovery = RecoveryService(config, db_manager, RuntimeRegistry())

    async with get_db_session(db_manager) as session:
        repository = MissionRepository(session)
        waiting = await repository.create("Approval wait", "Wait for owner approval")
        await repository.update_phase(waiting.id, MissionPhase.WAITING_FOR_APPROVAL)
        await repository.update_status(waiting.id, MissionStatus.RUNNING)
        executing = await repository.create("Interrupted execution", "Resume after restart")
        await repository.update_phase(executing.id, MissionPhase.EXECUTE)
        await repository.update_status(executing.id, MissionStatus.RUNNING)
        await session.commit()
        waiting_id, executing_id = waiting.id, executing.id

    await recovery.recover()

    async with get_db_session(db_manager) as session:
        repository = MissionRepository(session)
        waiting_after = await repository.get_by_id(waiting_id)
        executing_after = await repository.get_by_id(executing_id)
        assert waiting_after.status == MissionStatus.PAUSED.value
        assert executing_after.status == MissionStatus.PENDING.value
        assert await repository.find_recoverable_missions(config.recovery.recoverable_phases) == []
