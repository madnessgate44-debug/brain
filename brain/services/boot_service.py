"""Boot service."""

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
    
    def __init__(
        self,
        config: Config,
        db_manager: DatabaseSessionManager,
    ):
        self.config = config
        self.db_manager = db_manager
        self.runtime_registry = RuntimeRegistry()
        self.boot_started_at = None
        self.boot_completed = False
    
    async def boot(self) -> None:
        """Execute boot sequence."""
        self.boot_started_at = utc_now()
        logger.info("Starting boot sequence", extra={
            "instance_id": self.config.system.instance_id,
            "environment": self.config.system.environment,
        })
        
        try:
            # 1. Ensure workspace directories exist
            logger.debug("Ensuring workspace directories exist")
            self._ensure_workspace()
            
            # 2. Initialize database engine/session
            logger.debug("Initializing database")
            self.db_manager.get_session_factory()
            
            # 3. Verify DB connectivity
            logger.debug("Verifying database connectivity")
            if not await self.db_manager.check_connectivity():
                raise RuntimeError("Database connectivity check failed")
            
            # 4. Run recovery service if enabled
            if self.config.recovery.auto_recover:
                logger.info("Running recovery service")
                recovery_service = RecoveryService(
                    self.config,
                    self.db_manager,
                    self.runtime_registry,
                )
                await recovery_service.recover()
            
            # 5. Log successful boot completion
            self.boot_completed = True
            duration = (utc_now() - self.boot_started_at).total_seconds()
            logger.info(
                "Boot completed successfully",
                extra={
                    "duration_seconds": duration,
                    "instance_id": self.config.system.instance_id,
                }
            )
            
        except Exception as e:
            logger.error(f"Boot failed: {e}", exc_info=True)
            raise
    
    def _ensure_workspace(self) -> None:
        """Ensure workspace directories exist."""
        workspace_paths = WorkspacePaths(self.config.workspace)
        
        # Create all directories
        for path in workspace_paths.all_paths():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {path}")