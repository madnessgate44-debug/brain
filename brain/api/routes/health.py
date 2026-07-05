"""Health check endpoint."""

from datetime import datetime
from fastapi import APIRouter, Request

from brain.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    config = request.app.state.config
    db_manager = request.app.state.db_manager
    
    # Check database connectivity
    db_healthy = await db_manager.check_connectivity()
    
    boot_started_at = getattr(request.app.state, "boot_started_at", None)
    
    return HealthResponse(
        status="healthy" if db_healthy else "degraded",
        version=request.app.version,
        database_connected=db_healthy,
        instance_id=config.system.instance_id,
        started_at=boot_started_at.isoformat() if boot_started_at else None,
        uptime_seconds=(
            (datetime.utcnow() - boot_started_at).total_seconds()
            if boot_started_at
            else 0
        ),
    )