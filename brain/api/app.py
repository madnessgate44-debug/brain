"""FastAPI application factory."""

from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from brain.api.routes import health, missions, approvals, artifacts, events
from brain.core.config import load_config
from brain.core.logging import setup_logging
from brain.db.session import DatabaseSessionManager
from brain.services.boot_service import BootService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    config = app.state.config
    setup_logging(config)
    
    # Initialize database
    db_manager = DatabaseSessionManager(config.database.sqlite_path)
    app.state.db_manager = db_manager
    
    # Run boot service
    boot_service = BootService(config, db_manager)
    await boot_service.boot()
    app.state.boot_service = boot_service
    app.state.boot_started_at = boot_service.boot_started_at
    
    yield
    
    # Shutdown
    await db_manager.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    config = load_config()
    
    app = FastAPI(
        title="Brain V1 API",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Store config in app state
    app.state.config = config
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(health.router)
    app.include_router(missions.router)
    app.include_router(approvals.router)
    app.include_router(artifacts.router)
    app.include_router(events.router)
    
    return app