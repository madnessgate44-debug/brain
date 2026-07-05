"""Custom exceptions for Brain."""

from typing import Optional, Any


class BrainError(Exception):
    """Base exception for Brain."""
    pass


class ConfigurationError(BrainError):
    """Configuration error."""
    pass


class DatabaseError(BrainError):
    """Database error."""
    pass


class MissionNotFoundError(BrainError):
    """Mission not found error."""
    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        super().__init__(f"Mission {mission_id} not found")


class InvalidMissionStateError(BrainError):
    """Invalid mission state transition error."""
    def __init__(self, message: str, current_state: Optional[str] = None):
        self.current_state = current_state
        super().__init__(message)


class ApprovalError(BrainError):
    """Approval error."""
    def __init__(self, message: str, approval_id: Optional[str] = None):
        self.approval_id = approval_id
        super().__init__(message)


class RuntimeError(BrainError):
    """Runtime error."""
    def __init__(self, message: str, mission_id: Optional[str] = None):
        self.mission_id = mission_id
        super().__init__(message)


class ArtifactError(BrainError):
    """Artifact error."""
    def __init__(self, message: str, mission_id: Optional[str] = None):
        self.mission_id = mission_id
        super().__init__(message)


class RecoveryError(BrainError):
    """Recovery error."""
    def __init__(self, message: str, mission_id: Optional[str] = None):
        self.mission_id = mission_id
        super().__init__(message)