"""Mission runtime implementation."""

import asyncio
import logging
from typing import Optional

from brain.domain.enums import MissionPhase, MissionStatus
from brain.repositories.event_repository import EventRepository
from brain.repositories.mission_repository import MissionRepository
from brain.runtime.workers.document_worker import build_mission_brief
from brain.storage.artifact_store import ArtifactStore

logger = logging.getLogger("brain.runtime.mission_runtime")


class MissionRuntime:
    """Execute a mission through a registered, deterministic first worker."""

    def __init__(
        self,
        mission_id: str,
        runtime_id: str,
        mission_repo: MissionRepository,
        event_repo: EventRepository,
        artifact_store: ArtifactStore,
        max_iterations: int = 10,
    ):
        self.mission_id = mission_id
        self.runtime_id = runtime_id
        self.mission_repo = mission_repo
        self.event_repo = event_repo
        self.artifact_store = artifact_store
        # Retained for constructor compatibility and future bounded multi-step workers.
        self.max_iterations = max_iterations
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Generate a real mission brief artifact and settle mission state."""
        if self._running:
            return

        self._running = True
        logger.info(
            "Mission runtime %s starting",
            self.runtime_id,
            extra={"mission_id": self.mission_id, "runtime_id": self.runtime_id},
        )

        try:
            mission = await self.mission_repo.get_by_id(self.mission_id)
            if not mission:
                raise RuntimeError(f"Mission {self.mission_id} not found")

            if mission.status != MissionStatus.RUNNING.value:
                logger.info(
                    "Mission %s is no longer running; execution skipped",
                    self.mission_id,
                    extra={"mission_id": self.mission_id},
                )
                return

            await self.event_repo.append_event(
                mission_id=self.mission_id,
                event_type="worker_started",
                message="Deterministic document worker started",
                phase=MissionPhase.EXECUTE.value,
                severity="INFO",
                payload_json='{"worker":"document_worker"}',
            )

            content = build_mission_brief(mission.title, mission.objective)
            artifact_path = self.artifact_store.save_artifact(
                mission_id=self.mission_id,
                logical_name="mission-brief.md",
                content=content.encode("utf-8"),
                metadata={
                    "mission_id": self.mission_id,
                    "runtime_id": self.runtime_id,
                    "worker": "document_worker",
                    "claims_external_work": False,
                },
            )

            await self.event_repo.append_event(
                mission_id=self.mission_id,
                event_type="artifact_created",
                message="Mission brief artifact created",
                phase=MissionPhase.VALIDATE.value,
                severity="INFO",
                payload_json=(
                    '{"artifact":"mission-brief.md",'
                    '"worker":"document_worker",'
                    '"claims_external_work":false}'
                ),
            )

            await self.mission_repo.mark_completed(self.mission_id)
            await self.event_repo.append_event(
                mission_id=self.mission_id,
                event_type="mission_phase_changed",
                message="Mission completed; mission brief artifact created",
                phase=MissionPhase.COMPLETE.value,
                severity="INFO",
                payload_json='{"artifact":"mission-brief.md"}',
            )

            logger.info(
                "Mission %s completed with artifact %s",
                self.mission_id,
                artifact_path.name,
                extra={"mission_id": self.mission_id, "artifact": str(artifact_path)},
            )
        except asyncio.CancelledError:
            logger.info(
                "Mission runtime %s cancelled",
                self.runtime_id,
                extra={"mission_id": self.mission_id},
            )
            raise
        except Exception as exc:
            logger.exception(
                "Mission runtime %s failed",
                self.runtime_id,
                extra={"mission_id": self.mission_id},
            )
            await self.mission_repo.mark_failed(self.mission_id, f"Runtime failed: {exc}")
            await self.event_repo.append_event(
                mission_id=self.mission_id,
                event_type="mission_failed",
                message=f"Mission failed: {exc}",
                phase=MissionPhase.FAILED.value,
                severity="ERROR",
            )
        finally:
            self._running = False
            logger.info(
                "Mission runtime %s finished",
                self.runtime_id,
                extra={"mission_id": self.mission_id, "runtime_id": self.runtime_id},
            )

    def start(self) -> None:
        """Start the runtime task if it is not already active."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        """Stop the runtime task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
