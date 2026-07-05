"""Mission schemas."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from brain.domain.enums import MissionPhase, MissionStatus


class MissionCreate(BaseModel):
    """Mission creation request."""
    title: str = Field(..., min_length=1, max_length=255)
    objective: str = Field(..., min_length=1)
    priority: Optional[str] = Field(default="MEDIUM", description="Priority level")
    risk_level: Optional[str] = Field(default="LOW", description="Risk level")
    max_loop_iterations: Optional[int] = Field(default=10, ge=1)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class MissionResponse(BaseModel):
    """Mission response."""
    id: str
    created_at: str
    updated_at: str
    title: str
    objective: str
    phase: MissionPhase
    status: MissionStatus
    priority: str
    risk_level: str
    current_loop_iteration: int
    max_loop_iterations: int
    approval_state: str
    assigned_runtime_id: Optional[str]
    last_heartbeat_at: Optional[str]
    recovery_state: Optional[str]
    metadata_json: Optional[str]
    error_summary: Optional[str]


class MissionListResponse(BaseModel):
    """Mission list response."""
    missions: List[MissionResponse]
    total: int
    limit: int
    offset: int


class MissionStartResponse(BaseModel):
    """Mission start response."""
    mission_id: str
    status: str
    phase: str
    runtime_id: Optional[str]
    message: str