"""ID generation utilities."""

import uuid
import hashlib
from datetime import datetime
from typing import Optional


def generate_id(prefix: str = "", length: int = 32) -> str:
    """Generate a unique ID."""
    uid = uuid.uuid4().hex[:length - len(prefix)]
    return f"{prefix}{uid}" if prefix else uid


def generate_mission_id() -> str:
    """Generate a mission ID."""
    return generate_id("mis_")


def generate_event_id() -> str:
    """Generate an event ID."""
    return generate_id("evt_")


def generate_approval_id() -> str:
    """Generate an approval ID."""
    return generate_id("apr_")


def generate_artifact_id() -> str:
    """Generate an artifact ID."""
    return generate_id("art_")


def generate_runtime_id() -> str:
    """Generate a runtime ID."""
    return generate_id("rt_")


def generate_runtime_lease_id() -> str:
    """Generate a runtime lease ID."""
    return generate_id("rtl_")


def deterministic_id(prefix: str, *args) -> str:
    """Generate a deterministic ID from arguments."""
    content = "|".join(str(arg) for arg in args)
    digest = hashlib.sha256(content.encode()).hexdigest()
    return f"{prefix}{digest[:24]}"