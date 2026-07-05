"""Time utilities."""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as ISO string."""
    if dt is None:
        return None
    return dt.isoformat()


def parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string."""
    if iso_str is None:
        return None
    return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))