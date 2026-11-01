# Vercel-as-board proposal — verification (2026-11-01)

ChatGPT proposed: Vercel = ChatGPT↔Watcher communication board; GitHub = engineering evidence.
Verdict: **architecture sound, foundation partly exists, the board itself does NOT exist yet.**
The loop is **not** operational on Vercel — do not claim it is.

## What exists (verified)

| item | evidence | state |
|---|---|---|
| Vercel project `brain` | `prj_iAUlBjtc9a0xryvIRtbpr1MIv9Cl`, team `team_AI8XmzPHH369q3vdHLtlTJZf` | CONFIRMED |
| Live alias | `brain-one-pi.vercel.app` → `dpl_25HjDoBb1C555Tm95zypRmD3KNj4` (branch `feat/connector-mcp`) | CONFIRMED |
| MCP connector live | `GET /connector` → 200 `{"key_configured":true,"mcp_path":"/mcp","transport":"streamable-http"}` | CONFIRMED |
| `/mcp` up | `POST /mcp` without key → 401 | CONFIRMED |
| Connector tools | `brain_chat`, `brain_create_mission`, `brain_start_mission`, `brain_get_mission`, `brain_list_missions`, `brain_list_artifacts` (PR #242 `brain/connector/client.py`) | CONFIRMED |
| REST surface | `/openapi.json` paths: health, missions, approvals, company-workflows, browser, chat, connector | CONFIRMED |

## What is missing (the gap)

- **No message board.** No `/board`, `/messages`, `/inbox` endpoint (all 404 on the live app).
- **No board tool.** The connector exposes chat + missions, not "post a message / read messages".
- `POST /chat` is **stateless** (takes a `messages` array, returns a reply) — it is not a persistent board.
- Therefore ChatGPT's "post to Vercel, Watcher reads and replies" is **not implementable today** without new code.

## Second gap: the live key rejects the local key

`POST /mcp` with the local `BRAIN_CONTROL_API_KEY` → `401 {"detail":"Invalid Brain control key."}`.
The deployed value is encrypted on Vercel and differs from the local one. Until they match, I cannot
drive the live connector at all. Needs owner action (share/rotate), not a code change.

## Third finding: my branch deploys ERROR

Every push of `watcher/channel-handshake-240` produced a Vercel deployment in state **ERROR**
(`brain-90i24ojde…`, `brain-e71wvu11g…`, `brain-53yjwfzlr…`, …). Cause: `vercel.json`,
`requirements.txt`, `Dockerfile` exist only on PR #242's branch `feat/connector-mcp`, **not on main**.
So main (and my branch) cannot build on Vercel. The live app is served from `feat/connector-mcp`.

## Smallest concrete change

Add a durable board to the connector: two tools (`post_message`, `read_messages`) backed by the
existing mission/event/artifact store (do not add a second queue). That single change turns the live
connector into the board ChatGPT described, with no new infrastructure and no new spend.
