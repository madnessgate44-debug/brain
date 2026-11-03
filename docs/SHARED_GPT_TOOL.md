# The shared-GPT tool: one endpoint that fronts Brain and Forge

Goal: a single tool a "shared GPT" can call, which routes work to either **Brain** (the mission
orchestrator in this repo) or **Forge** (the deterministic coding agent in `madnessgate44-debug/Firstborn`).
This document records what exists today, verified, and the exact wiring that is missing.

## 1. What exists today (verified 2026-11-02)

### Brain
- Deployed at `https://brain-one-pi.vercel.app`, serving **OpenAPI 3.1** at `/openapi.json` (HTTP 200).
- Paths on the live deployment: `/health`, `/missions` (+ start/detail), `/approvals`,
  `/missions/{id}/artifacts`, `/missions/{id}/events`, `/company-workflows`, `/browser/tasks`,
  `/browser/plan`, `/chat`, `/connector`.
- Auth: `X-Brain-API-Key` header checked with `hmac.compare_digest` against `BRAIN_CONTROL_API_KEY`
  (`brain/api/routes/company_workflows.py` uses `require_control_key`).
- `/company-workflows` is the natural entry: `POST {title, objective, repository}` queues the
  specialist pipeline and returns `mission_id` + status/events/artifacts endpoints.
- Caveat [V]: the live build is the **stale 2026-11-01** build (its `/openapi.json` still lists
  `/connector`, which is not in `main`). The serverless entrypoint fix (PR #271) is not merged, so
  fresh `main` deploys fail. Treat "the live API runs a mission end to end" as UNVERIFIED.

### Forge (Firstborn)
- `README.md` states the design goal directly: Forge "is designed to be driven by a supervising
  controller (a human operator or a 'shared GPT' orchestrator) over two stable interfaces: a GitHub
  Actions workflow and a local HTTP API."
- **MCP server** `src/mcp/forreyra-server.ts`: 10 tools (`browser_open/view/click/type/press/
  scroll/extract/query/screenshot/close`). Transport is **stdio only** — the client must spawn the
  process. It is not a remote endpoint.
- **HTTP API** `server.ts` (Express, default port 3000): `/api/health`, `/api/github/inspect`,
  `POST /api/tasks/run`, `/api/tasks/:id`, `/api/verify/check`, `/api/coordination`. Auth is a
  GitHub bearer token validated against GitHub. It runs **locally**.
- Deployment status [V]: **Forge is not deployed.** The Vercel team has only two projects, `brain`
  and `amina`. No public HTTPS endpoint for the HTTP API or MCP exists.

## 2. How a shared GPT can actually connect (verified against OpenAI docs, 2026-11-02)

Two supported mechanisms:

1. **Custom GPT Action (OpenAPI).** Paste an OpenAPI schema into a Custom GPT; ChatGPT calls the
   REST endpoints. Supports API-key auth. Brain's existing `/openapi.json` is directly usable.
   Source: developers.openai.com/api/docs/actions/getting-started.
2. **Remote MCP connector.** ChatGPT Developer Mode (Settings → Connectors → Advanced) adds a
   **remote MCP server URL** over HTTPS with **OAuth or no authentication**. A bearer-token-only
   server is not directly supported. Requires a paid ChatGPT plan (Plus/Pro/Business/Enterprise/
   Edu); the Free tier has no custom connectors.
   Sources: help.openai.com "Connecting custom MCP servers in ChatGPT"; community.openai.com
   (bearer-token limitation).

## 3. The gap (what is missing)

| # | Missing piece | Why it blocks the goal |
|---|---|---|
| G1 | Forge has no public HTTPS endpoint | A shared GPT cannot reach a `localhost:3000` API or a stdio MCP process. |
| G2 | Forge's MCP is stdio, not remote | ChatGPT connectors need a remote HTTPS MCP URL. |
| G3 | No single gateway that fronts both | Today Brain and Forge are separate, incompatible surfaces. |
| G4 | Auth model mismatch | Brain uses a custom header; ChatGPT MCP wants OAuth or none; GPT Actions want API-key. |
| G5 | Brain's live build is stale | Fresh `main` deploys fail (PR #271 unmerged), so a fixed gateway cannot ship to prod yet. |

## 4. Proposed design: one gateway, two faces

A single small service ("the tool") that exposes:

- **Face A — OpenAPI for GPT Actions:** `/openapi.json` with three operations —
  `submit_task` (→ Brain `/company-workflows`), `get_status` (→ Brain `/missions/{id}`),
  `run_forge_task` (→ Forge `/api/tasks/run`). API-key auth via a header ChatGPT supports.
- **Face B — remote MCP over HTTPS:** `POST /mcp` exposing `submit_task`, `get_status`,
  `run_forge_task`, and the Forge browser tools, with OAuth (or no auth) as ChatGPT requires.

Routing is a thin table: Brain-bound intents go to Brain; single-repo coding intents go to Forge.
Brain remains the orchestrator; Forge remains the executor. Neither is rewritten.

## 5. Order of work (smallest first)

1. **Deploy Forge** (G1/G2) behind an HTTPS endpoint with the MCP transport switched to
   streamable-HTTP, auth via OAuth or none. This is a Firstborn change, not a Brain change.
2. **Fix Brain's prod deploy** (G5) so a gateway can ship — merge PR #271 (serverless entrypoint).
3. **Add the gateway** (G3/G4) in Brain as a thin router + an MCP endpoint, reusing the existing
   OpenAPI. Then create the Custom GPT Action and the MCP connector.
4. **Verify end to end:** from a ChatGPT conversation, `submit_task` returns a real `mission_id`
   and `get_status` reflects real progress.

## 6. Cost

Everything above can run on free, no-card tiers: Vercel Hobby for hosting (already in use, no card),
and the model paths Brain/Forge already use. The only paid element is the **owner's ChatGPT plan**,
which Developer Mode / Custom GPT connectors require. No new paid service is introduced by this plan.

Cost: $0 in new spend | verified 2026-11-02 | source https://vercel.com/pricing (Hobby, no card)
