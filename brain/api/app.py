"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from brain.api.routes import (
    health, missions, approvals, artifacts, events, company_workflows, browser, browser_planning, chat,
)
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

    try:
        yield
    finally:
        # Stop background mission tasks before disposing their database connections.
        # A cancelled runtime can be recovered on the next boot from persisted mission state.
        try:
            await boot_service.runtime_registry.stop_all()
        finally:
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

    # Never combine wildcard origins with credentialed requests. Deployments can
    # explicitly list trusted frontend origins via BRAIN_CORS_ORIGINS.
    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "BRAIN_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,https://madnessgate44-debug.github.io",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Brain-API-Key", "Authorization"],
    )

    # Register routes
    app.include_router(health.router)
    app.include_router(missions.router)
    app.include_router(approvals.router)
    app.include_router(approvals.mission_router)
    app.include_router(artifacts.router)
    app.include_router(events.router)
    app.include_router(company_workflows.router)
    app.include_router(browser.router)
    app.include_router(browser_planning.router)
    app.include_router(chat.router)

    return app
