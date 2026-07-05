"""Event schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from brain.domain.enums import EventSeverity


class EventCreate(BaseModel):
    """Event creation request."""
    mission_id: str
    event_type: str
    phase: Optional[str] = None
    severity: EventSeverity = EventSeverity.INFO
    message: str
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EventResponse(BaseModel):
    """Event response."""
    id: str
    mission_id: str
    created_at: str
    event_type: str
    phase: Optional[str]
    severity: str
    message: str
    payload_json: Optional[str]
    sequence_number: int