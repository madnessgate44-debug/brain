""""Boot service."""

import logging
from pathlib import Path
from datetime import datetime

from brain.core.config import Config
from brain.db.session import DatabaseSessionManager
from brain.services.recovery_service import RecoveryService
from brain.runtime.runtime_registry import RuntimeRegistry
from brain.storage.paths import WorkspacePaths
from brain.core.clock import utc_now

logger = logging.getLogger("brain.services.boot_service")


class BootService:
    """Service responsible for application boot sequence."""

    def __init__(self, config: Config, db_manager: DatabaseSessionManager):
        self.config = config
        self.db_manager = db_manager
        self.runtime_registry = RuntimeRegistry()
        self.boot_started_at = None
        self.boot_completed = False

    async def boot(self) -> None:
        """Prepare workspace and database before recovering missions."""
        self.boot_started_at = utc_now()
        logger.info("Starting boot sequence", extra={
            "instance_id": self.config.system.instance_id,
            "environment": self.config.system.environment,
        })

        try:
            self._ensure_workspace()
            self.db_manager.get_session_factory()

            if not await self.db_manager.check_connectivity():
                raise RuntimeError("Database connectivity check failed")

            # A fresh deployment must have its ORM tables before recovery queries run.
            # create_all is additive: it creates missing tables and does not rewrite existing ones.
            await self.db_manager.initialize_schema()

            if self.config.recovery.auto_recover:
                logger.info("Running recovery service")
                recovery_service = RecoveryService(
                    self.config,
                    self.db_manager,
                    self.runtime_registry,
                )
                await recovery_service.recover()

            self.boot_completed = True
            duration = (utc_now() - self.boot_started_at).total_seconds()
            logger.info("Boot completed successfully", extra={
                "duration_seconds": duration,
                "instance_id": self.config.system.instance_id,
            })
        except Exception as exc:
            logger.error("Boot failed: %s", exc, exc_info=True)
            raise

    def _ensure_workspace(self) -> None:
        """Ensure workspace directories exist."""
        workspace_paths = WorkspacePaths(self.config.workspace)
        for path in workspace_paths.all_paths():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured workspace directory: %s", path)
"