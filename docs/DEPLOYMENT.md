# Deployment

Brain deploys as one process that serves both the REST API and the MCP connector
(`/mcp`). Two supported paths: a plain container host, and Vercel serverless.

## Live deployment (Vercel, free Hobby plan, no card)

| | |
| --- | --- |
| Base URL | `https://brain-one-pi.vercel.app` |
| Connector | `https://brain-one-pi.vercel.app/mcp` |
| Health | `https://brain-one-pi.vercel.app/health` |
| Connector status | `https://brain-one-pi.vercel.app/connector` |
| Vercel project | `forge-fe22/brain` |
| Entrypoint | `index.py` (module-level ASGI `app`) |

Runtime environment is set on the Vercel project (values are encrypted, never in
the repo):

| Variable | Value |
| --- | --- |
| `BRAIN_CONTROL_API_KEY` | the connector/API Bearer key (48 chars) |
| `BRAIN_AI_API_KEY` | model provider key |
| `BRAIN_AI_MODEL` | `gemini-3.5-flash-lite` |
| `BRAIN_AI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `BRAIN_PUBLIC_BASE_URL` | `https://brain-one-pi.vercel.app` |
| `WORKSPACE__ROOT` | `/tmp/brain/workspace` |
| `DATABASE__SQLITE_PATH` | `/tmp/brain/workspace/db/brain.db` |
| `LOGGING__LOG_FILE` | `/tmp/brain/workspace/logs/brain.log` |

Vercel's filesystem is read-only except `/tmp`, so the workspace and SQLite file
live under `/tmp`.

### Serverless limitation

Vercel's `/tmp` is ephemeral. Missions and artifacts persist only while the
function instance stays warm; a cold start begins with an empty database. Chat
through the connector is unaffected. For durable missions, deploy the container
(below) with a mounted volume and point `DATABASE__SQLITE_PATH` at it.

## Container host (durable)

```bash
docker build -t brain .
docker run -p 8000:8000 \
  -e BRAIN_CONTROL_API_KEY=<48-char-key> \
  -e BRAIN_AI_API_KEY=<model-key> \
  -e BRAIN_AI_MODEL=gemini-3.5-flash-lite \
  -v brain-data:/app/workspace \
  brain
```

The image installs the lean runtime plus the OpenHands developer backend, so the
full Brain feature set is available. `-v brain-data:/app/workspace` keeps missions
across restarts.

## Local run

```bash
pip install -r requirements.txt
export BRAIN_CONTROL_API_KEY=$(openssl rand -hex 24)
export BRAIN_AI_API_KEY=<model-key>
export BRAIN_AI_MODEL=gemini-3.5-flash-lite
export BRAIN_PUBLIC_BASE_URL=http://127.0.0.1:8000
uvicorn brain.connector.app:create_combined_app --factory --host 127.0.0.1 --port 8000
```

## Verifying a deployment

```bash
BASE=https://brain-one-pi.vercel.app
KEY=<control-key>

curl -s $BASE/health          # {"status":"healthy",...}
curl -s $BASE/connector       # {"key_configured":true,...}
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/mcp   # 401 without the key
```

Full MCP check is in `docs/CONNECTOR.md`.
