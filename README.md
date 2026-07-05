# Brain V1

Brain is a standalone mission orchestration service that manages autonomous missions through planning, execution, and recovery.

## Sprint 1 Features

- ✅ Configuration management with environment overrides
- ✅ SQLite persistence with Alembic migrations (async)
- ✅ REST API for mission lifecycle
- ✅ Event logging with sequence ordering
- ✅ Approval workflow foundation
- ✅ Artifact metadata tracking
- ✅ Stub mission runtime
- ✅ Recovery service on boot

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd brain
uv pip install -e .

# Configure
cp .env.example .env

# Migrate database
alembic upgrade head

# Run server
uvicorn brain.api.app:create_app --host 0.0.0.0 --port 8000