# Production plan — Firstborn (Forge)

Goal: Forge is ChatGPT's authenticated browser/computer-use tool, reachable as a registered connector.

The daily audit measures this repo against this plan and reports progress, not a raw defect list.
Statuses: done / in-progress / blocked / todo.

| id | item | status | evidence |
|---|---|---|---|
| F1 | Authenticated Streamable HTTP MCP endpoint | in-progress | PR #147 `feat/forreyra-mcp-http` @ `e5ba1f0d`, open, not merged; CI `verify` + policy checks success |
| F2 | Shared browser tool set with read-only gate | in-progress | PR #147 files: `src/mcp/http.ts`, `src/services/browser.ts`, `src/services/redact.ts` |
| F3 | Audit receipts + result redaction | in-progress | PR #147: `src/services/redact.ts`, `tests/mcp-http.test.ts` |
| F4 | Public HTTPS deployment | blocked | not deployed; needs owner/platform gate (`Firstborn` issue #146) |
| F5 | Registered + callable from ChatGPT | blocked | connector registration is an owner action (`Firstborn` #146) |
| F6 | Two-way OpenHands proof | blocked | depends on F4 + F5 |
