# Brain Connector (MCP)

One URL and one key that adds Brain to any chat client that supports a custom
connector: ChatGPT, Claude, Gemini, OpenHands, and any other MCP client.

## Live

```
https://brain-one-pi.vercel.app/mcp
```

Send the key as `Authorization: Bearer <BRAIN_CONTROL_API_KEY>`. See
`docs/DEPLOYMENT.md` for the deployment details and how to run your own.

## What it is

Brain speaks the Model Context Protocol (MCP) over HTTP (streamable HTTP) at:

```
<BRAIN_PUBLIC_BASE_URL>/mcp
```

The client discovers Brain's tools at runtime. Nothing is wired by hand.

## Authentication

A single Bearer key, the same `BRAIN_CONTROL_API_KEY` the REST API uses. One key
to remember, for both the API and the connector.

```
Authorization: Bearer <BRAIN_CONTROL_API_KEY>
```

The key must be at least 24 characters. Requests without it, or with the wrong
key, get `401`. When the key is not configured, the connector answers `503` and
stays off.

## Tools

| Tool | Purpose |
| --- | --- |
| `brain_chat` | Send a message to Brain's configured model; returns the reply. |
| `brain_create_mission` | Create a mission from a title and objective. |
| `brain_start_mission` | Start a created mission so its runtime executes. |
| `brain_get_mission` | Read one mission's phase and status. |
| `brain_list_missions` | List recent missions, newest first. |
| `brain_list_artifacts` | List the artifacts a mission produced. |

## Adding it to a client

### Claude (and other MCP clients)

Add a custom connector with:

- URL: `https://<host>/mcp`
- Header: `Authorization: Bearer <BRAIN_CONTROL_API_KEY>`

### ChatGPT (Developer mode / connectors)

Add a custom connector pointing at the same URL and header. ChatGPT uses the
MCP streamable-HTTP transport.

### Gemini

Add the same URL and header where the client accepts an MCP server.

### Local test with the MCP client

```bash
BRAIN_CONTROL_API_KEY=... python - <<'PY'
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client(
        "http://127.0.0.1:8000/mcp",
        headers={"Authorization": "Bearer <key>"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print([t.name for t in (await session.list_tools()).tools])

asyncio.run(main())
PY
```

## Checking readiness

`GET /connector` returns the connector status without exposing the key:

```json
{"server": "brain", "base_url": "...", "key_configured": true,
 "model": "...", "mcp_path": "/mcp", "transport": "streamable-http"}
```

## How it is served

`brain.connector.app:create_combined_app` serves the REST API and the connector in
one process: `/mcp` goes to the connector, every other path to the REST API. The
connector tools call the same FastAPI endpoints the REST clients use, in-process,
so there is no second execution path and no duplicated logic.

## Environment

| Variable | Meaning |
| --- | --- |
| `BRAIN_CONTROL_API_KEY` | The Bearer key. Required, at least 24 characters. |
| `BRAIN_PUBLIC_BASE_URL` | Public base URL of the deployment, used for status and docs. |
| `BRAIN_AI_API_KEY` | Model provider key. |
| `BRAIN_AI_MODEL` | Model name. |
| `BRAIN_AI_BASE_URL` | OpenAI-compatible model base URL. |

## Security

- The key is read from the environment and never written to a file, log, or response.
- The connector disables DNS-rebinding host checks because the public host name is
  not known at build time; the Bearer key is the guard. Do not run the connector on
  a host without the key set.
- No service here needs a card or a payment.
