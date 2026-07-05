"""SQLAlchemy ORM models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from brain.db.base import Base
from brain.core.clock import utc_now
from brain.domain.enums import (
    MissionPhase,
    MissionStatus,
    ApprovalStatus,
    EventSeverity,
    RuntimeLeaseStatus,
    ArtifactType,
)


class MissionModel(Base):
    """Mission ORM model."""
    
    __tablename__ = "missions"
    
    id = Column(String(64), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    
    title = Column(String(255), nullable=False)
    objective = Column(Text, nullable=False)
    
    phase = Column(String(32), nullable=False, default=MissionPhase.INTAKE.value)
    status = Column(String(32), nullable=False, default=MissionStatus.PENDING.value)
    
    priority = Column(String(16), nullable=False, default="MEDIUM")
    risk_level = Column(String(16), nullable=False, default="LOW")
    
    current_loop_iteration = Column(Integer, nullable=False, default=0)
    max_loop_iterations = Column(Integer, nullable=False, default=10)
    
    approval_state = Column(String(32), nullable=False, default=ApprovalStatus.NOT_REQUIRED.value)
    
    assigned_runtime_id = Column(String(64), nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    recovery_state = Column(String(64), nullable=True)
    
    metadata_json = Column(Text, nullable=True)
    error_summary = Column(Text, nullable=True)
    
    # Relationships
    events = relationship("MissionEventModel", backref="mission", cascade="all, delete-orphan")
    approvals = relationship("ApprovalModel", backref="mission", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactModel", backref="mission", cascade="all, delete-orphan")
    leases = relationship("RuntimeLeaseModel", backref="mission", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_missions_phase", "phase"),
        Index("idx_missions_status", "status"),
        Index("idx_missions_approval_state", "approval_state"),
        Index("idx_missions_updated_at", "updated_at"),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "title": self.title,
            "objective": self.objective,
            "phase": self.phase,
            "status": self.status,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "current_loop_iteration": self.current_loop_iteration,
            "max_loop_iterations": self.max_loop_iterations,
            "approval_state": self.approval_state,
            "assigned_runtime_id": self.assigned_runtime_id,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "recovery_state": self.recovery_state,
            "metadata_json": self.metadata_json,
            "error_summary": self.error_summary,
        }


class MissionEventModel(Base):
    """Mission event ORM model."""
    
    __tablename__ = "mission_events"
    
    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    
    event_type = Column(String(64), nullable=False)
    phase = Column(String(32), nullable=True)
    severity = Column(String(16), nullable=False, default=EventSeverity.INFO.value)
    message = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    
    sequence_number = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index("idx_mission_events_mission_seq", "mission_id", "sequence_number", unique=True),
        Index("idx_mission_events_mission_id", "mission_id"),
        Index("idx_mission_events_event_type", "event_type"),
        Index("idx_mission_events_created_at", "created_at"),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "event_type": self.event_type,
            "phase": self.phase,
            "severity": self.severity,
            "message": self.message,
            "payload_json": self.payload_json,
            "sequence_number": self.sequence_number,
        }


class ApprovalModel(Base):
    """Approval ORM model."""
    
    __tablename__ = "approvals"
    
    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    
    approval_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default=ApprovalStatus.PENDING.value)
    reason = Column(Text, nullable=True)
    
    requested_at = Column(DateTime, nullable=False, default=utc_now)
    responded_at = Column(DateTime, nullable=True)
    response_note = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    payload_json = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_approvals_mission_id", "mission_id"),
        Index("idx_approvals_status", "status"),
        Index("idx_approvals_requested_at", "requested_at"),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "approval_type": self.approval_type,
            "status": self.status,
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "response_note": self.response_note,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "payload_json": self.payload_json,
        }


class ArtifactModel(Base):
    """Artifact ORM model."""
    
    __tablename__ = "artifacts"
    
    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    
    artifact_type = Column(String(32), nullable=False)
    logical_name = Column(String(255), nullable=False)
    relative_path = Column(String(512), nullable=True)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    metadata_json = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_artifacts_mission_id", "mission_id"),
        Index("idx_artifacts_artifact_type", "artifact_type"),
        Index("idx_artifacts_created_at", "created_at"),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "artifact_type": self.artifact_type,
            "logical_name": self.logical_name,
            "relative_path": self.relative_path,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata_json": self.metadata_json,
        }


class RuntimeLeaseModel(Base):
    """Runtime lease ORM model."""
    
    __tablename__ = "runtime_leases"
    
    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    runtime_id = Column(String(64), nullable=False)
    
    leased_at = Column(DateTime, nullable=False, default=utc_now)
    heartbeat_at = Column(DateTime, nullable=False, default=utc_now)
    lease_status = Column(String(32), nullable=False, default=RuntimeLeaseStatus.ACTIVE.value)
    
    __table_args__ = (
        UniqueConstraint("mission_id", name="uq_runtime_leases_mission_id"),
        Index("idx_runtime_leases_mission_id", "mission_id"),
        Index("idx_runtime_leases_status", "lease_status"),
        Index("idx_runtime_leases_heartbeat_at", "heartbeat_at"),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "runtime_id": self.runtime_id,
            "leased_at": self.leased_at.isoformat() if self.leased_at else None,
            "heartbeat_at": self.heartbeat_at.isoformat() if self.heartbeat_at else None,
            "lease_status": self.lease_status,
        }