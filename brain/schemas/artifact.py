"""Artifact schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from brain.domain.enums import ArtifactType


class ArtifactCreate(BaseModel):
    """Artifact creation request."""
    artifact_type: ArtifactType
    logical_name: str = Field(..., min_length=1, max_length=255)
    relative_path: Optional[str] = Field(None, max_length=512)
    mime_type: Optional[str] = Field(None, max_length=128)
    size_bytes: Optional[int] = Field(None, ge=0)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    """Artifact response."""
    id: str
    mission_id: str
    artifact_type: str
    logical_name: str
    relative_path: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    created_at: str
    metadata_json: Optional[str]