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