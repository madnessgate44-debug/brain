""""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

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
        self.sqlite_path = sqlite_path
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        """Get or create async engine."""
        if self._engine is None:
            connection_string = f"sqlite+aiosqlite:///{self.sqlite_path}"
            self._engine = create_async_engine(
                connection_string,
                echo=False,
                connect_args={"check_same_thread": False, "timeout": 30},
            )

            @event.listens_for(self._engine.sync_engine, "connect")
            def connect_listener(dbapi_connection, connection_record):
                apply_pragmas(dbapi_connection)

        return self._engine

    def get_session_factory(self):
        """Get or create async session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self._get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    async def initialize_schema(self) -> None:
        """Create any missing ORM tables before services query the database."""
        # Import models so all mapped tables are registered on Base.metadata.
        from brain.db import models  # noqa: F401
        from brain.db.base import Base

        engine = self._get_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def check_connectivity(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


@asynccontextmanager
async def get_db_session(manager: DatabaseSessionManager) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and commit or roll back the request transaction."""
    async with manager.get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
"