FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Lean runtime (API + connector), then the OpenHands developer backend for the full
# Brain feature set. The connector and REST API do not import OpenHands at request time.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir openhands-sdk==1.54.0 openhands-tools==1.54.0

COPY . .

# The app creates its SQLite schema at boot. On hosts with an ephemeral disk the
# database lives under /app/workspace; point DATABASE__SQLITE_PATH at a mounted
# volume to persist missions across restarts.
RUN mkdir -p /app/workspace/db /app/workspace/logs

EXPOSE 8000

CMD ["sh", "-c", "uvicorn brain.connector.app:create_combined_app --factory --host 0.0.0.0 --port ${PORT}"]
