"""Mission runtime implementation."""

import asyncio
import logging
from typing import Optional

from brain.repositories.mission_repository import MissionRepository
from brain.repositories.event_repository import EventRepository
from brain.domain.enums import MissionPhase, MissionStatus

logger = logging.getLogger("brain.runtime.mission_runtime")


class MissionRuntime:
    """Mission runtime for executing a mission."""
    
    def __init__(
        self,
        mission_id: str,
        runtime_id: str,
        mission_repo: MissionRepository,
        event_repo: EventRepository,
        max_iterations: int = 10,
    ):
        self.mission_id = mission_id
        self.runtime_id = runtime_id
        self.mission_repo = mission_repo
        self.event_repo = event_repo
        self.max_iterations = max_iterations
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def run(self) -> None:
        """Run the mission."""
        if self._running:
            return
        
        self._running = True
        logger.info(
            f"Mission runtime {self.runtime_id} starting",
            extra={"mission_id": self.mission_id, "runtime_id": self.runtime_id}
        )
        
        try:
            # Get current mission state
            mission = await self.mission_repo.get_by_id(self.mission_id)
            if not mission:
                raise RuntimeError(f"Mission {self.mission_id} not found")
            
            current_iteration = mission.current_loop_iteration
            
            # Stub runtime: Simulate mission execution
            while current_iteration < self.max_iterations and self._running:
                # Emit iteration started event
                await self.event_repo.append_event(
                    mission_id=self.mission_id,
                    event_type="mission_stub_iteration_started",
                    message=f"Starting stub iteration {current_iteration + 1}",
                    phase=MissionPhase.EXECUTE.value,
                    severity="DEBUG",
                    payload_json=str({"iteration": current_iteration + 1}),
                )
                
                # Simulate work
                await asyncio.sleep(2)
                
                # Increment iteration
                await self.mission_repo.increment_loop_iteration(self.mission_id)
                current_iteration += 1
                
                # Emit iteration completed event
                await self.event_repo.append_event(
                    mission_id=self.mission_id,
                    event_type="mission_stub_iteration_completed",
                    message=f"Completed stub iteration {current_iteration}",
                    phase=MissionPhase.EXECUTE.value,
                    severity="DEBUG",
                    payload_json=str({"iteration": current_iteration}),
                )
                
                # Check if we should stop
                if current_iteration >= self.max_iterations:
                    # Mark as completed
                    await self.mission_repo.mark_completed(self.mission_id)
                    
                    await self.event_repo.append_event(
                        mission_id=self.mission_id,
                        event_type="mission_phase_changed",
                        message="Mission completed after reaching max iterations",
                        phase=MissionPhase.COMPLETE.value,
                        severity="INFO",
                    )
                    
                    logger.info(
                        f"Mission {self.mission_id} completed after {current_iteration} iterations",
                        extra={"mission_id": self.mission_id, "iterations": current_iteration}
                    )
                    break
                
                # Check if mission was stopped externally
                mission = await self.mission_repo.get_by_id(self.mission_id)
                if mission.status != MissionStatus.RUNNING.value:
                    logger.info(
                        f"Mission {self.mission_id} stopped externally",
                        extra={"mission_id": self.mission_id}
                    )
                    break
            
        except Exception as e:
            logger.error(
                f"Mission runtime {self.runtime_id} failed: {e}",
                extra={"mission_id": self.mission_id},
                exc_info=True,
            )
            
            # Mark mission as failed
            await self.mission_repo.mark_failed(
                self.mission_id,
                f"Runtime failed: {str(e)}"
            )
            
            await self.event_repo.append_event(
                mission_id=self.mission_id,
                event_type="mission_failed",
                message=f"Mission failed: {str(e)}",
                phase=MissionPhase.FAILED.value,
                severity="ERROR",
            )
        
        finally:
            self._running = False
            logger.info(
                f"Mission runtime {self.runtime_id} finished",
                extra={"mission_id": self.mission_id, "runtime_id": self.runtime_id}
            )
    
    def start(self) -> None:
        """Start the runtime task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
    
    async def stop(self) -> None:
        """Stop the runtime."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass