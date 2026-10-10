"""Recovery service."""

import logging
from datetime import timedelta

from brain.core.config import Config
from brain.core.clock import utc_now
from brain.domain.enums import MissionPhase, MissionStatus
from brain.db.session import DatabaseSessionManager, get_db_session
from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.runtime.runtime_registry import RuntimeRegistry

logger = logging.getLogger("brain.services.recovery_service")


class RecoveryService:
    """Service responsible for recovering missions after restart."""
    
    def __init__(
        self,
        config: Config,
        db_manager: DatabaseSessionManager,
        runtime_registry: RuntimeRegistry,
    ):
        self.config = config
        self.db_manager = db_manager
        self.runtime_registry = runtime_registry
        self.recoverable_phases = config.recovery.recoverable_phases
    
    async def recover(self) -> None:
        """Run recovery process for all missions."""
        logger.info(
            "Starting recovery process",
            extra={
                "recoverable_phases": self.recoverable_phases,
            }
        )
        
        async with get_db_session(self.db_manager) as session:
            mission_repo = MissionRepository(session)
            event_repo = EventRepository(session)
            
            # Find missions in recoverable phases
            heartbeat_cutoff = utc_now() - timedelta(
                seconds=self.config.recovery.orphan_detection_grace_period_seconds
            )
            recoverable_missions = await mission_repo.find_recoverable_missions(
                self.recoverable_phases,
                heartbeat_cutoff=heartbeat_cutoff,
            )
            
            if not recoverable_missions:
                logger.info("No recoverable missions found")
                return
            
            logger.info(
                f"Found {len(recoverable_missions)} recoverable missions",
                extra={"count": len(recoverable_missions)}
            )
            
            # Process each recoverable mission
            for mission in recoverable_missions:
                await self._recover_mission(mission, mission_repo, event_repo)
            
            await session.commit()
        
        logger.info("Recovery process completed")
    
    async def _recover_mission(
        self,
        mission,
        mission_repo: MissionRepository,
        event_repo: EventRepository,
    ) -> None:
        """Recover a single mission."""
        mission_id = mission.id
        phase = mission.phase
        
        logger.info(
            f"Recovering mission {mission_id}",
            extra={
                "mission_id": mission_id,
                "phase": phase,
                "status": mission.status,
            }
        )
        
        # Emit recovery_started event
        await event_repo.append_event(
            mission_id=mission_id,
            event_type="recovery_started",
            message=f"Recovery started for mission in phase {phase}",
            phase=phase,
            severity="INFO",
        )
        
        try:
            # Handle based on phase
            if phase == MissionPhase.WAITING_FOR_APPROVAL.value:
                # Keep mission paused, waiting for approval
                await mission_repo.update_status(
                    mission_id,
                    MissionStatus.PAUSED
                )
                await mission_repo.update_recovery_state(
                    mission_id,
                    "recovered_waiting_for_approval"
                )
                
            elif phase in [MissionPhase.EXECUTE.value, MissionPhase.VALIDATE.value, MissionPhase.REPAIR.value]:
                # Checkpoint resume is not implemented. Never make an interrupted
                # mission restartable by replaying side effects from the beginning.
                await mission_repo.update_status(
                    mission_id,
                    MissionStatus.PAUSED
                )
                await mission_repo.clear_runtime(mission_id)
                await mission_repo.update_recovery_state(
                    mission_id,
                    f"recovery_requires_manual_review_from_{phase}"
                )
                
            else:
                # Unknown recoverable phase
                await mission_repo.mark_failed(
                    mission_id,
                    f"Recovered from unknown phase: {phase}"
                )
                await mission_repo.update_recovery_state(
                    mission_id,
                    f"recovery_failed_unknown_phase_{phase}"
                )
            
            # Emit an explicit warning when the mission cannot safely resume.
            active_interruption = phase in {
                MissionPhase.EXECUTE.value,
                MissionPhase.VALIDATE.value,
                MissionPhase.REPAIR.value,
            }
            await event_repo.append_event(
                mission_id=mission_id,
                event_type="recovery_completed",
                message=(
                    f"Mission paused for manual review after interruption in {phase}; "
                    "automatic checkpoint resume is not implemented."
                    if active_interruption
                    else f"Recovery completed for mission in phase {phase}"
                ),
                phase=phase,
                severity="WARNING" if active_interruption else "INFO",
            )
            
            logger.info(
                f"Mission {mission_id} recovered successfully",
                extra={"mission_id": mission_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to recover mission {mission_id}: {e}",
                extra={"mission_id": mission_id},
                exc_info=True,
            )
            
            # Mark mission as failed
            await mission_repo.mark_failed(
                mission_id,
                f"Recovery failed: {str(e)}"
            )
            
            # Emit failure event
            await event_repo.append_event(
                mission_id=mission_id,
                event_type="mission_failed",
                message=f"Mission failed during recovery: {str(e)}",
                phase=phase,
                severity="ERROR",
            )