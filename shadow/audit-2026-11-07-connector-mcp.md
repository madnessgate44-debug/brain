# Shadow audit — MCP connector (PR #242)

Auditor: OpenHands agent (Shadow role), on behalf of the owner.
Scope: PR #242, `feat/connector-mcp` → `main`.
Rule applied: `docs/LOOP.md` owner grant — merge when CI is green and this audit returns Verified.
Owner instruction this session: "merge all and push all that you did not merge yet."

## What the PR adds

One URL and one Bearer key that any MCP-capable chat client (ChatGPT, Claude, Gemini,
OpenHands) can add. The connector speaks MCP over streamable HTTP at `/mcp`; every other
path stays on the REST API.

| File | Change |
|---|---|
| `brain/connector/{__init__,app,client,settings}.py` | MCP server, combined ASGI app, HTTP client, settings. |
| `brain/api/routes/connector.py` | `GET /connector` readiness (never exposes the key value). |
| `brain/api/app.py`, `brain/api/routes/__init__.py` | Register the connector router. |
| `index.py`, `requirements.txt`, `pyproject.toml` | Serve REST+MCP from one serverless app; add `mcp`. |
| `Dockerfile`, `docs/CONNECTOR.md`, `docs/DEPLOYMENT.md` | Deploy path and docs. |
| `tests/test_connector_mcp.py` | 7 tests over a real ASGI transport. |

## Changes made during this merge (not in the original branch)

1. **Merged `main` (e1ae43b) into the branch.** The branch was 57 commits behind; conflicts
   were `.gitignore` (took `main`), `index.py` (took the connector's combined app), and
   `requirements.txt` (took `main`'s comment + kept `mcp`). `vercel.json` was already identical.
2. **Pinned `mcp>=1.10.0,<2`.** The branch declared `mcp>=1.10.0` unbounded. `mcp` 2.x renamed
   `FastMCP` to `MCPServer` (`mcp.server.fastmcp` no longer exists), so an unpinned install
   breaks the connector at import. Verified: with `mcp<2`, `from mcp.server.fastmcp import
   FastMCP` succeeds.
3. **Updated `tests/test_vercel_entrypoint.py`.** It asserted `index.py`'s `app` is a `FastAPI`;
   the connector makes it a `CombinedApp`. Replaced with an ASGI-contract assertion plus a
   check that the REST app is still served.

## Checks

- **Technical only:** yes. A connector and its tests; no spend, no goal change.
- **Security:** the `/mcp` mount is guarded by a constant-time (`hmac.compare_digest`) Bearer
  check against `BRAIN_CONTROL_API_KEY`; it returns 503 when the key is unset or under 24
  chars, 401 on a wrong key. The readiness endpoint reports only `key_configured: bool`.
  The connector is one surface with one key, matching the existing REST control key.
- **Full test suite on head `36fc126`:** `364 passed, 2 skipped`.
- **Functional check (real ASGI transport):** `GET /health` → 200; `GET /connector` → 200;
  `POST /mcp` without a key → **401**; `POST /mcp` with the key → **200** (MCP `initialize`
  handshake returns a JSON-RPC result).

## Verdict

**Verified.** Merge as a merge commit (the repo's established style).

## Note on scope

This merges the connector because the owner asked for everything unmerged to be merged. It is
additive and behind a key; it does not alter existing REST behaviour except the CORS method
list, which is broadened from GET/POST to the full verb set (the connector and its clients need
PUT/PATCH/DELETE). The CORS origin allow-list is unchanged.
