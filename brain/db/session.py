"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import event, text

from brain.db.pragmas import apply_pragmas


class DatabaseSessionManager:
    """Database session manager."""
    
    def __init__(self, sqlite_path: str):
        """Initialize database session manager."""
        self.sqlite_path = sqlite_path
        self._engine = None
        self._session_factory = None
    
    def _get_engine(self):
        """Get or create async engine."""
        if self._engine is None:
            # SQLite uses aiosqlite
            connection_string = f"sqlite+aiosqlite:///{self.sqlite_path}"
            self._engine = create_async_engine(
                connection_string,
                echo=False,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                }
            )
            
            # Apply SQLite pragmas
            @event.listens_for(self._engine.sync_engine, "connect")
            def connect_listener(dbapi_connection, connection_record):
                apply_pragmas(dbapi_connection)
        
        return self._engine
    
    def get_session_factory(self):
        """Get or create async session factory."""
        if self._session_factory is None:
            engine = self._get_engine()
            self._session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory
    
    async def close(self):
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
    
    async def check_connectivity(self) -> bool:
        """Check database connectivity."""
        try:
            session_factory = self.get_session_factory()
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


@asynccontextmanager
async def get_db_session(manager: DatabaseSessionManager) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session."""
    session_factory = manager.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()