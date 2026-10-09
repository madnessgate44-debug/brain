"""Mission runtime implementation."""

import asyncio
import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from brain.domain.enums import ArtifactType, EventSeverity, MissionPhase, MissionStatus
from brain.repositories.artifact_repository import ArtifactRepository
from brain.repositories.event_repository import EventRepository
from brain.repositories.mission_repository import MissionRepository
from brain.runtime.workers.document_worker import build_mission_brief
from brain.storage.artifact_store import ArtifactStore
from brain.company.engine import CompanyWorkflowEngine
from brain.company.github_gateway import GitHubRepositoryGateway
from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.tools import GitHubCompanyTools

logger = logging.getLogger("brain.runtime.mission_runtime")


class MissionRuntime:
    """Execute a mission using a runtime-owned database session."""

    def __init__(
        self,
        mission_id: str,
        runtime_id: str,
        session_factory: async_sessionmaker[AsyncSession],
        artifact_store: ArtifactStore,
        max_iterations: int = 10,
    ):
        self.mission_id = mission_id
        self.runtime_id = runtime_id
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.max_iterations = max_iterations
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Generate a mission brief, register it, and persist the final mission state."""
        if self._running:
            return

        self._running = True
        try:
            async with self.session_factory() as session:
                mission_repo = MissionRepository(session)
                event_repo = EventRepository(session)
                artifact_repo = ArtifactRepository(session)

                mission = await mission_repo.get_by_id(self.mission_id)
                if not mission:
                    raise RuntimeError(f"Mission {self.mission_id} not found")
                if mission.status != MissionStatus.RUNNING.value:
                    logger.info("Mission %s is no longer running; execution skipped", self.mission_id)
                    return

                metadata = {}
                if mission.metadata_json:
                    try:
                        metadata = json.loads(mission.metadata_json)
                    except (TypeError, json.JSONDecodeError):
                        metadata = {}

                if metadata.get("workflow_type") == "software_company":
                    repository = metadata.get("repository")
                    if not isinstance(repository, str) or "/" not in repository:
                        raise RuntimeError(
                            "Software-company missions require metadata.repository in owner/repository format."
                        )
                    await event_repo.append_event(
                        mission_id=self.mission_id,
                        event_type="company_workflow_started",
                        message="Software-company workflow started",
                        phase=MissionPhase.PLAN.value,
                        severity=EventSeverity.INFO,
                        payload_json=json.dumps({"repository": repository}),
                    )
                    gateway = GitHubRepositoryGateway()
                    tools = GitHubCompanyTools(gateway=gateway)
                    engine = CompanyWorkflowEngine(
                        SpecialistAgentRunner(OpenAICompatibleProvider()),
                        tools,
                    )
                    result = await engine.run(mission.objective, repository)
                    for role_key, role_output in result["role_outputs"].items():
                        role_name = f"role-{role_key}.json"
                        role_bytes = json.dumps(role_output, ensure_ascii=False, indent=2).encode("utf-8")
                        role_path = self.artifact_store.save_artifact(
                            mission_id=self.mission_id,
                            logical_name=role_name,
                            content=role_bytes,
                            metadata={"role": role_key, "workflow_type": "software_company"},
                        )
                        await artifact_repo.create(
                            mission_id=self.mission_id,
                            artifact_type=ArtifactType.EXECUTION,
                            logical_name=role_name,
                            relative_path=str(role_path.relative_to(self.artifact_store.workspace_root)),
                            mime_type="application/json",
                            size_bytes=len(role_bytes),
                            metadata_json=json.dumps({"role": role_key}),
                        )
                        await event_repo.append_event(
                            mission_id=self.mission_id,
                            event_type="specialist_completed",
                            message=f"Specialist completed: {role_key}",
                            phase=MissionPhase.VALIDATE.value,
                            severity=EventSeverity.INFO,
                            payload_json=json.dumps({
                                "role": role_key,
                                "status": role_output.get("status"),
                            }),
                        )

                    report_name = "software-company-report.json"
                    report_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
                    report_path = self.artifact_store.save_artifact(
                        mission_id=self.mission_id,
                        logical_name=report_name,
                        content=report_bytes,
                        metadata={"workflow_type": "software_company", "repository": repository},
                    )
                    await artifact_repo.create(
                        mission_id=self.mission_id,
                        artifact_type=ArtifactType.TEST_REPORT,
                        logical_name=report_name,
                        relative_path=str(report_path.relative_to(self.artifact_store.workspace_root)),
                        mime_type="application/json",
                        size_bytes=len(report_bytes),
                        metadata_json=json.dumps({
                            "workflow_type": "software_company",
                            "repository": repository,
                            "pull_request": result.get("pull_request"),
                        }),
                    )
                    await event_repo.append_event(
                        mission_id=self.mission_id,
                        event_type="company_workflow_ready_for_review",
                        message="All workflow gates passed; pull request awaits human review",
                        phase=MissionPhase.WAITING_FOR_APPROVAL.value,
                        severity=EventSeverity.INFO,
                        payload_json=json.dumps({
                            "repository": repository,
                            "pull_request": result.get("pull_request"),
                            "branch": result.get("branch"),
                        }),
                    )
                    await mission_repo.update_phase(
                        self.mission_id, MissionPhase.WAITING_FOR_APPROVAL
                    )
                    await mission_repo.update_status(self.mission_id, MissionStatus.PAUSED)
                    await session.commit()
                    logger.info(
                        "Software-company workflow for mission %s is ready for human review",
                        self.mission_id,
                    )
                    return

                if metadata.get("workflow_type") == "browser":
                    from brain.company.settings import get_setting
                    from brain.runtime.workers.browser_worker import (
                        BrowserPolicyError,
                        BrowserWorker,
                        browser_dispatch_payload,
                        verify_browser_dispatch,
                    )

                    actions = metadata.get("browser_actions")
                    owner_approved = metadata.get("browser_owner_approved") is True
                    signature = metadata.get("browser_dispatch_signature", "")
                    secret = get_setting("BRAIN_CONTROL_API_KEY")
                    try:
                        payload = browser_dispatch_payload(
                            self.mission_id,
                            mission.title,
                            mission.objective,
                            actions,
                            owner_approved,
                        )
                        if not verify_browser_dispatch(secret, payload, signature):
                            raise BrowserPolicyError("Browser dispatch signature is missing or invalid.")
                        await event_repo.append_event(
                            mission_id=self.mission_id,
                            event_type="browser_worker_started",
                            message="Authenticated browser worker started",
                            phase=MissionPhase.EXECUTE.value,
                            severity=EventSeverity.INFO,
                            payload_json=json.dumps({
                                "worker": "browser_worker",
                                "requested_actions": len(actions) if isinstance(actions, list) else 0,
                            }),
                        )
                        result = await BrowserWorker().execute(actions, owner_approved=owner_approved)
                        report_name = "browser-execution-report.json"
                        report_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
                        report_path = self.artifact_store.save_artifact(
                            mission_id=self.mission_id,
                            logical_name=report_name,
                            content=report_bytes,
                            metadata={
                                "mission_id": self.mission_id,
                                "runtime_id": self.runtime_id,
                                "worker": "browser_worker",
                                "workflow_type": "browser",
                                "claims_external_work": True,
                            },
                        )
                        await artifact_repo.create(
                            mission_id=self.mission_id,
                            artifact_type=ArtifactType.EXECUTION,
                            logical_name=report_name,
                            relative_path=str(report_path.relative_to(self.artifact_store.workspace_root)),
                            mime_type="application/json",
                            size_bytes=len(report_bytes),
                            metadata_json=json.dumps({
                                "worker": "browser_worker",
                                "workflow_type": "browser",
                                "status": result.get("status"),
                            }),
                        )
                        await event_repo.append_event(
                            mission_id=self.mission_id,
                            event_type="browser_worker_completed",
                            message="Browser execution report stored",
                            phase=MissionPhase.VALIDATE.value,
                            severity=EventSeverity.INFO if result.get("status") == "succeeded" else EventSeverity.ERROR,
                            payload_json=json.dumps({
                                "artifact": report_name,
                                "status": result.get("status"),
                                "completed_actions": result.get("completed_actions"),
                                "requested_actions": result.get("requested_actions"),
                            }),
                        )
                        if result.get("status") != "succeeded":
                            raise RuntimeError(
                                f"Browser worker did not complete all actions; report artifact: {report_name}"
                            )
                        await mission_repo.mark_completed(self.mission_id)
                        await event_repo.append_event(
                            mission_id=self.mission_id,
                            event_type="mission_phase_changed",
                            message="Browser mission completed with an execution report",
                            phase=MissionPhase.COMPLETE.value,
                            severity=EventSeverity.INFO,
                            payload_json=json.dumps({"artifact": report_name}),
                        )
                        await session.commit()
                        logger.info("Browser mission %s completed", self.mission_id)
                        return
                    except BrowserPolicyError:
                        raise
                    except Exception:
                        raise

                await event_repo.append_event(
                    mission_id=self.mission_id,
                    event_type="worker_started",
                    message="Deterministic document worker started",
                    phase=MissionPhase.EXECUTE.value,
                    severity=EventSeverity.INFO,
                    payload_json=json.dumps({"worker": "document_worker"}),
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
                relative_path = str(artifact_path.relative_to(self.artifact_store.workspace_root))
                await artifact_repo.create(
                    mission_id=self.mission_id,
                    artifact_type=ArtifactType.DOCUMENTATION,
                    logical_name="mission-brief.md",
                    relative_path=relative_path,
                    mime_type="text/markdown",
                    size_bytes=len(content.encode("utf-8")),
                    metadata_json=json.dumps({
                        "runtime_id": self.runtime_id,
                        "worker": "document_worker",
                        "claims_external_work": False,
                    }),
                )

                await event_repo.append_event(
                    mission_id=self.mission_id,
                    event_type="artifact_created",
                    message="Mission brief artifact created and registered",
                    phase=MissionPhase.VALIDATE.value,
                    severity=EventSeverity.INFO,
                    payload_json=json.dumps({
                        "artifact": "mission-brief.md",
                        "worker": "document_worker",
                        "claims_external_work": False,
                    }),
                )
                await mission_repo.mark_completed(self.mission_id)
                await event_repo.append_event(
                    mission_id=self.mission_id,
                    event_type="mission_phase_changed",
                    message="Mission completed; mission brief artifact created",
                    phase=MissionPhase.COMPLETE.value,
                    severity=EventSeverity.INFO,
                    payload_json=json.dumps({"artifact": "mission-brief.md"}),
                )
                await session.commit()

                logger.info(
                    "Mission %s completed with artifact %s",
                    self.mission_id,
                    artifact_path.name,
                    extra={"mission_id": self.mission_id, "artifact": str(artifact_path)},
                )
        except asyncio.CancelledError:
            logger.info("Mission runtime %s cancelled", self.runtime_id)
            raise
        except Exception as exc:
            logger.exception("Mission runtime %s failed", self.runtime_id)
            try:
                async with self.session_factory() as failure_session:
                    mission_repo = MissionRepository(failure_session)
                    event_repo = EventRepository(failure_session)
                    await mission_repo.mark_failed(self.mission_id, f"Runtime failed: {exc}")
                    await event_repo.append_event(
                        mission_id=self.mission_id,
                        event_type="mission_failed",
                        message=f"Mission failed: {exc}",
                        phase=MissionPhase.FAILED.value,
                        severity=EventSeverity.ERROR,
                    )
                    await failure_session.commit()
            except Exception:
                logger.exception("Unable to persist failure state for mission %s", self.mission_id)
        finally:
            self._running = False

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
