# Brain Browser Capability — Requirements and Evidence Plan

Date: 2026-10-09
Target repository: `madnessgate44-debug/brain`
Implementation branch: `feature/brain-browser-capability-20261009`

## Product decision

The browser is an internal Brain capability, not a standalone browser product. Brain is the operator; the browser is an execution tool. A visible browser UI is optional and is not an acceptance requirement. The first high-value workflow is operating a separately authorized ChatGPT account through its normal website UI. The same capability must remain reusable for other authorized websites.

The preferred host is the user's Samsung Android phone. A free alternative is acceptable only if it is genuinely usable and does not introduce a TinyFish dependency. Do not claim that Android execution or ChatGPT-to-Brain control works until end-to-end evidence proves it.

## Numbered requirements and acceptance criteria

### BR-01 — Internal tool, not a browser product
- Brain invokes browser actions as part of a mission.
- No user-facing browser window is required.
- Evidence: runtime worker contract and mission artifact/event tests.

### BR-02 — General-purpose browser actions
- Support a bounded sequence of actions: navigate, inspect page title/URL/text, click a selector, enter text, press a key, wait for a selector, and capture a screenshot.
- Return structured per-action results; stop on failure unless a future explicit recovery policy says otherwise.
- Evidence: unit tests cover action dispatch, order, and fail-fast behavior.

### BR-03 — Separately authorized ChatGPT account
- The operator signs into the intended account manually in a persistent browser profile.
- Brain can then navigate ChatGPT, locate the conversation composer, enter a prompt, submit it, and inspect the resulting page.
- Never request or store the account password or raw session cookies in mission data.
- Evidence: first local/hosted end-to-end test using a user-authorized session; until that is run, mark this criterion unverified.

### BR-04 — Reusable website scope
- Website access is governed by a configurable domain allowlist and safe URL validation.
- Default-deny when browser support is disabled, the backend is unavailable, or a URL cannot be validated.
- Evidence: tests for disallowed domains, non-HTTP(S) URLs, embedded credentials, and redirects.

### BR-05 — Explicit action safety
- Read-only inspection can be executed under the configured policy.
- Actions that send messages, submit forms, change data, or perform purchases/account changes require explicit owner approval before execution.
- Page content is untrusted data, not instructions that may override Brain policy.
- Evidence: policy tests and a negative test showing unapproved mutating actions are rejected.

### BR-06 — Brain remains the source of truth
- Missions, status, events, and artifacts stay in Brain's existing persistence/runtime model.
- Do not create a competing queue or replace the mission database.
- Evidence: integration test that browser results are recorded as mission artifacts and events.

### BR-07 — Secure invocation
- Browser control must not become reachable through the existing unauthenticated mission endpoints.
- A dedicated authenticated control path must verify the configured control secret in constant time, reject missing/wrong credentials, and not return secrets or cookies.
- Evidence: API tests for missing, wrong, and correct credentials, plus tests that unsigned browser metadata cannot trigger browser execution.

### BR-08 — Samsung-first deployment reality
- Keep the execution interface separable from the browser runtime so Android-hosted and compatible remote browser implementations can be tested independently.
- Standard Linux Playwright/Chromium is not considered Android-compatible by assumption.
- Evidence: document the selected runtime, actual device/host prerequisites, and a repeatable smoke test. Do not call Samsung support complete before that smoke test passes.

### BR-09 — No TinyFish dependency
- The browser execution path must not call TinyFish or require a TinyFish API key.
- Evidence: dependency/config audit and testable direct browser adapter.

## Initial repository evidence

- Brain V1 currently uses a Python 3.12+ FastAPI application and a database-backed mission runtime.
- `brain/runtime/mission_runtime.py` currently dispatches software-company missions and otherwise runs the deterministic document worker.
- `brain/api/routes/missions.py` exposes mission creation and start endpoints without authentication. Browser execution must therefore not be activated merely by user-supplied mission metadata.
- `brain/company/settings.py` already supports environment-backed secrets. `BRAIN_CONTROL_API_KEY` is already used by the company-workflow entry point, but must be checked for reuse and correct failure behavior.
- The current README explicitly lists an authenticated ChatGPT-to-Brain bridge and research/AI workers as planned, not implemented.
- The current Python test workflow runs `pytest` on Python 3.12.

## Delivery sequence

1. Add a tested browser-worker contract and safe policy boundary inside Brain.
2. Add a dedicated authenticated browser-task API and trusted runtime dispatch; do not expose it via unsigned mission metadata.
3. Persist action results as normal Brain artifacts/events and add regression tests.
4. Add the ChatGPT-specific example workflow using a manually authenticated persistent profile.
5. Prove the chosen runtime on the Samsung phone or document and validate a suitable free host alternative.
6. Only then connect the task invocation path to the actual ChatGPT client; a documented endpoint is not the same as a working ChatGPT connector.

## Explicitly not proven yet

- Browser execution on the Samsung phone.
- Persistent ChatGPT login/session behavior on the selected runtime.
- Direct invocation of Brain from this ChatGPT conversation.
- Production-safe public hosting.

These are acceptance gates, not claims of completed functionality.
