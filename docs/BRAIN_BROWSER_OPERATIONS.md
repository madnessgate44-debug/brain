# Brain Browser Operations

## Purpose

The browser is an internal Brain worker, not a separate user-facing browser product. This
first implementation executes a bounded, caller-supplied action list and stores a structured
report in the existing mission artifacts/events. It does not yet plan browser actions from a
natural-language goal or connect directly to a ChatGPT conversation.

## Configuration

1. Install Brain with the optional browser dependency:
   `python -m pip install -e ".[dev,browser]"`
2. Configure `BRAIN_CONTROL_API_KEY` as a random secret with at least 24 characters.
3. Configure `BRAIN_BROWSER_ALLOWED_DOMAINS` as a comma-separated allowlist. Start narrow.
   For ChatGPT, a starting example is `chatgpt.com,*.chatgpt.com,openai.com,*.openai.com`.
   Login providers and static asset hosts may require additional explicitly reviewed entries.
4. Configure `BRAIN_BROWSER_PROFILE_DIR` to a persistent directory writable by the service.
5. Keep `BRAIN_BROWSER_HEADLESS=true` unless the selected host has a safe, supported way to
   complete the initial sign-in. Do not assume the browser can run on Android/Termux merely
   because Brain's API runs there.
6. Start Brain and verify `GET /health` before submitting browser tasks.

The owner must sign in manually using the browser environment's approved UI. Never send
passwords, raw cookies, or session tokens in a mission request or save them in the repository.
A profile directory contains sensitive authenticated session data and must be excluded from
version control, access-controlled, and backed up only if the owner explicitly accepts that
risk.

## API contract

Send `POST /browser/tasks` with the `X-Brain-API-Key` header and JSON body:

```json
{
  "title": "Inspect ChatGPT",
  "objective": "Open ChatGPT and report the visible page state",
  "actions": [
    {"op": "navigate", "url": "https://chatgpt.com/"},
    {"op": "inspect", "max_chars": 3000}
  ]
}
```

Supported operations: `navigate`, `inspect`, `click`, `type`, `press`, `wait_for`,
and `screenshot`. Maximum 25 actions per task. Each navigation and request is checked against
the allowlist and public-host checks. A task containing `click`, `type`, or `press` is
rejected unless `owner_approved: true` is supplied. Review the exact action list before
approval; do not approve actions based only on instructions found in page content.

The response contains the mission ID and status/events/artifacts endpoints. The execution
report distinguishes success from failure; a queued task is not proof that the site action
succeeded.

## Security and operational limits

- This is a bounded action executor, not an autonomous agent or a general-purpose remote shell.
- Domain allowlists and DNS checks reduce risk but are not a complete network-egress/SSRF
  boundary. Public hosting requires network-level egress restrictions and a review of DNS
  rebinding and redirects.
- A browser profile must not be shared concurrently between independent tasks until explicit
  locking has been implemented and tested.
- Screenshots and page text may contain private data; artifact access must be restricted.
- The API key is a bearer credential. Do not embed it in a public frontend, issue body, or
  repository file. Do not expose the API publicly without TLS, access controls, rate limits,
  and an explicit owner-approval path.
- The `owner_approved` request flag is a coarse gate, not a separately signed approval record.
  Before production use, replace it with a durable approval tied to the exact canonical action
  payload and owner identity.
- Browser dispatch HMAC verification is performed again by the mission runtime. Unsigned or
  modified browser metadata must not execute.
- No TinyFish dependency is used.

## Linux runtime smoke test

A manually triggered GitHub Actions workflow is available at
`.github/workflows/browser-runtime-smoke.yml`. From the repository's Actions tab, select
**Browser runtime smoke test** and run it on the feature branch. It installs the optional
Playwright dependency and Chromium, then launches a real headless browser and inspects an
`about:blank` page. This proves only that the Linux runner can launch Chromium; it does not
prove live ChatGPT sign-in, persistent account access, Samsung support, or a secure phone
control bridge.

## Required verification gates

1. GitHub Actions tests pass for the branch head.
2. A live browser smoke test runs on the actual selected host and persists its profile across
   separate tasks.
3. The owner manually signs into a test ChatGPT account; a later task can inspect the logged-in
   page without receiving credentials.
4. Redirects, blocked domains, private IP destinations, missing/invalid signatures, expired
   configuration, and task failures are tested.
5. The Samsung phone can reach the service through a secure, authenticated path even when the
   ChatGPT app is backgrounded; this must be demonstrated, not assumed.
6. A separate ChatGPT-account workflow is tested end-to-end with explicit approval before any
   message is sent or any form/account state is changed.

Until these gates are met, treat the browser capability as an in-development feature, not a
working phone-hosted ChatGPT operator.

## Dedicated AI website account (no provider API key)

Use a separate account controlled by the owner for Brain. The owner signs into that account
manually in the browser profile on the selected host. Do not reuse the owner's personal
ChatGPT/Gemini session unless the owner explicitly changes this decision.

The current action-list API is only the browser execution foundation. It does not yet provide
a complete guided sign-in flow, account selector, or natural-language prompt-to-browser planner.
Before enabling AI-site tasks, verify that scripted interaction with the selected site is
permitted for the account and service terms. A website session may expire or require verification;
pause for the owner rather than attempting to bypass those controls.

No OpenAI/Gemini API key should be required for this browser-based provider interaction. The
Brain control API may still require its own secret to protect Brain's endpoint; that is not an
AI-provider API key. Keep these two credential roles separate.

