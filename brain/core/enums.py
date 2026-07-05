"""Domain enums."""

from enum import Enum


class MissionPhase(str, Enum):
    """Mission execution phases."""
    INTAKE = "INTAKE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VALIDATE = "VALIDATE"
    REPAIR = "REPAIR"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionStatus(str, Enum):
    """Mission execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, Enum):
    """Approval status values."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class EventSeverity(str, Enum):
    """Event severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RuntimeLeaseStatus(str, Enum):
    """Runtime lease status values."""
    ACTIVE = "ACTIVE"
    LOST = "LOST"
    RELEASED = "RELEASED"


class ArtifactType(str, Enum):
    """Artifact types."""
    DOCUMENTATION = "DOCUMENTATION"
    SOURCE_CODE = "SOURCE_CODE"
    TEST_REPORT = "TEST_REPORT"
    LOG = "LOG"
    METRIC = "METRIC"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    OTHER = "OTHER"


class ApprovalType(str, Enum):
    """Approval request types."""
    PLAN_REVIEW = "PLAN_REVIEW"
    EXECUTION_REVIEW = "EXECUTION_REVIEW"
    CHANGE_REQUEST = "CHANGE_REQUEST"
    RESOURCE_RELEASE = "RESOURCE_RELEASE"
    OTHER = "OTHER"