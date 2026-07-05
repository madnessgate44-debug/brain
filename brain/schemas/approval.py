"""Approval schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from brain.domain.enums import ApprovalStatus, ApprovalType


class ApprovalRequestCreate(BaseModel):
    """Approval request creation."""
    approval_type: ApprovalType
    reason: Optional[str] = Field(None, description="Reason for approval")
    expires_at: Optional[str] = Field(None, description="Expiration time")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional data")


class ApprovalRequestResponse(BaseModel):
    """Approval request response."""
    id: str
    mission_id: str
    approval_type: str
    status: ApprovalStatus
    reason: Optional[str]
    requested_at: str
    responded_at: Optional[str]
    response_note: Optional[str]
    expires_at: Optional[str]
    payload_json: Optional[str]


class ApprovalResponseCreate(BaseModel):
    """Approval response creation."""
    approved: bool = Field(..., description="Whether to approve or reject")
    response_note: Optional[str] = Field(None, description="Response note")