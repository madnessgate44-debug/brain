# Brain Browser Operator V2

## Delivered interface

- `POST /browser/plan` translates a natural-language objective into a proposed, schema-validated browser action list.
- Planning is read-only: it does not launch Chromium or execute the returned actions.
- The endpoint requires the Brain control secret in `X-Brain-API-Key`.
- It uses the existing `BRAIN_AI_API_KEY`, `BRAIN_AI_BASE_URL`, and `BRAIN_AI_MODEL` settings through Brain's existing provider adapter.
- The caller reviews the exact plan and can submit it to `POST /browser/tasks`. Actions that can change a website still require explicit approval.
- Invalid model output is rejected rather than executed.

## General-purpose public browsing

The browser worker now defaults to `*` for public-web hostnames, so ordinary public sites do not require per-domain configuration. Deployments can still set `BRAIN_BROWSER_ALLOWED_DOMAINS` to narrow the scope. The worker continues to reject non-HTTP(S) URLs, embedded credentials, localhost, and non-public IP destinations; this is broad public-web browsing, not access to private networks or arbitrary local services. The GitHub issue runner accepts `allowed_domains: ["*"]` and uses that scope when the field is omitted.

## Persistent browser sessions

The worker already uses Playwright's persistent Chromium profile at
`BRAIN_BROWSER_PROFILE_DIR` (default: `./workspace/browser-profile`). For persistent
sessions, the browser service must run on a host with durable storage; GitHub-hosted Actions
runners are ephemeral and must not be treated as a persistent browser host. Keep the profile
directory private and out of Git commits, issue bodies, artifacts, and backups. Do not run
concurrent browser tasks against the same profile until profile locking is implemented.

Set `BRAIN_BROWSER_HEADLESS=false` only on a host that actually provides a supported,
private interactive display for manual owner sign-in. A remote Linux Actions runner does not
provide a persistent visible browser for routine sign-in. Samsung/Android hosting has not
been proven; do not claim it is supported until a real device smoke test succeeds.

## Known completion gates

- [x] Public-web default policy without per-domain setup.
- [x] Natural-language objective to validated action plan.
- [x] Click, type, press, hover, select, scroll, back/forward, reload, inspect, wait, and screenshot actions.
- [x] Persistent profile path configurable in the runtime.
- [ ] Profile locking and session-expiry detection.
- [ ] Stable host with durable disk and manual sign-in UX.
- [ ] End-to-end execution of a planned objective and result return.
- [ ] Samsung phone control path demonstrated.
