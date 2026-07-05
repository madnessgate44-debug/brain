"""Common schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    database_connected: bool = Field(..., description="Database connectivity")
    instance_id: str = Field(..., description="Instance identifier")
    started_at: Optional[str] = Field(None, description="Service start time")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")


class PaginationParams(BaseModel):
    """Pagination parameters."""
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")