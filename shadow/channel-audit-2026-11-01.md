# Shadow audit — Watcher channel receiver (issue #240), 2026-11-01

Auditor: Shadow. Scope: the automation-based channel receiver proposed in ChatGPT comment
`6554027628` and the OpenHands work order `6554029421`. Independent of Watcher's own report.

Verdict: **REJECTED for activation.** The draft was correctly torn down. Nothing is enabled.

## Checklist (required by the work order item 6)

| item | result | evidence |
|---|---|---|
| Filter correctness | PASS (syntax) | live 422 on bare `240`; backtick form accepted [V] |
| Repository scope | **FAIL** | no GitHub org claimed (`git-claims` → `[]`); personal workspace, not team org [V] |
| Issue scope (#240 only) | PASS (as written) | filter pins `issue.number == \`240\`` [V] |
| Prompt-injection handling | PASS (design) | prompt treats body as data, fail-closed [V] (design only, not E2E) |
| Bot exclusion | PASS (as written) | `!ends_with(sender.login,'[bot]')` accepted [V] |
| Dedup by comment id | PASS (design) | KV key `watcher:seen:<comment_id>` [V] (design only) |
| Loop prevention | PASS (design) | reply omits `@watcher` marker [V] (design only) |
| Credentials | PASS | no secret printed; only `$OPENHANDS_API_KEY` used in place [V] |
| **Spend** | **FAIL** | `enabled:false` still dispatched runs; non-zero `cost` observed; billing model undocumented [V]/[U] |
| **Rollback** | PASS | automation deleted (204 → 404); list back to 2 [V] |
| Disabled = inert | **FAIL** | event runs fired on an INACTIVE automation [V] |

## Findings

1. **HIGH — `enabled:false` is not a safe draft.** Two `trigger_source=event` runs and one
   `manual` run executed on an INACTIVE automation and started real sandboxes. The only reliable
   stop is `DELETE`. Any future "disabled draft" pattern must be deleted, never parked. [V]

2. **HIGH — the receiver cannot be correctly scoped on this account.** GitHub event routing needs
   a claimed team org; this is a personal workspace with zero claims. Events will not route as
   designed. The `@openhands` bot sessions are a *different* integration and prove nothing about
   this automation. [V]

3. **HIGH — spend is not established.** Zero-cost gate requires a quoted "no card" sentence for
   the adopted service. The pricing page prices plans, not automation runs; the billing API shows
   no card but a live `estimated_spend` that increased during this session. Cannot confirm $0.
   Escalate to Ahmed as a spend decision. [V]/[U]

4. **MEDIUM — docs are Enterprise-centric.** `event-automations.md` says it "applies to the local
   Agent Canvas and OpenHands Enterprise"; GitHub built-in events are documented under
   `enterprise/automations/github-events.md`. Applying it to a personal Cloud workspace was an
   unverified assumption that the live test disproved. [C]/[V]

5. **LOW — comment timestamps.** The issue-comment connector returned `created_at=null` in one
   read, so event correlation by timestamp is unreliable; correlate by comment id instead. [V]

## What would make this PASS
- An OpenHands **team org** that claims `madnessgate44-debug`, or a documented personal-account
  event path; **and**
- a quoted, official statement of automation run billing, or an owner decision to accept it; **and**
- one controlled E2E: marker comment → automation run id → conversation id → `[TO-CHATGPT]` reply
  with no marker → second cycle, deduped.

Until all three hold, the channel stays **human-mediated** and must not be described as autonomous.

## Independent verdict
REJECTED for activation. Rollback verified. No spend authorised. Escalate the spend question to
Ahmed only if a receiver is still wanted after the scoping gap is fixed.
