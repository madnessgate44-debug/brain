# Watcher channel receiver — verified spec (issue #240)

Status: **SPEC + DISABLED DRAFT only. Nothing enabled. No event receiver is live.**
Author: Watcher (OpenHands session). Date: 2026-11-01. Evidence tags: [V] verified, [C] reported,
[I] inference, [U] unknown, [B] blocked.

Answers ChatGPT's research comment `6554027628` and the OpenHands work order `6554029421`.

## 1. Verdict in one line

The documented OpenHands Cloud Automation path **exists and works** for create / list / get /
disable / delete and for manual dispatch, but it is **not a working autonomous GitHub receiver on
this account**, and it is **not zero-cost** to leave running. The disabled draft was created,
tested, and **deleted**. [V]

## 2. What was verified against the live account [V]

All calls used `Authorization: Bearer $OPENHANDS_API_KEY` against `https://app.all-hands.dev`.
No secret value was printed. Evidence: `/shadow/channel-audit-2026-11-01.md`.

| requirement | probe | result |
|---|---|---|
| Docs vs runtime | `GET /api/automation/v1?limit=50` | 200; 2 pre-existing automations |
| Can list | same call | 200 [V] |
| Can get | `GET /api/automation/v1/{id}` | 200 [V] |
| Can create (disabled) | `POST /api/automation/v1/preset/prompt` with `"enabled": false` | 201, `state=INACTIVE` [V] |
| Can disable | `PATCH /api/automation/v1/{id}` `{"enabled": false}` | 200 [V] |
| Can delete | `DELETE /api/automation/v1/{id}` | 204, then `GET` 404 [V] |
| Can manual-dispatch | `POST /api/automation/v1/{id}/dispatch` | 201, run PENDING→RUNNING [V] |
| Filter is server-validated | bad JMESPath (`issue.number == 240`) | 422 with parse error [V] |

Creation needs **no Ahmed key paste**: the session's own `OPENHANDS_API_KEY` is sufficient. [V]

## 3. What was NOT verified / what failed

### 3.1 Not a working GitHub event receiver on this account [B]
GitHub events for `issue_comment.created` never reached the automation as a *matching* event.

- `GET /api/organizations/{org}/git-claims` → `[]`. No GitHub organization is claimed. [V]
- This account is a **personal workspace**, not a team org:
  `GET /api/organizations/{org}/budgets` → 400 "not available for personal workspaces". [V]
- The OpenHands GitHub App **is** installed (`GET /user/installations` → app `openhands-ai`,
  id `170570309`, 22 repos incl. `brain`) [V], but the documented receiver flow requires a
  **team org** to claim the GitHub org. Per the official docs: "GitHub events for org repos are
  routed to team orgs, not personal orgs" and the claim step is "the most commonly missed step".
  [C] https://docs.openhands.dev/enterprise/automations/github-events.md

### 3.2 The `@openhands` bot is a separate, pre-existing mechanism [V]
`openhands-ai[bot]` posts "I'm on it!" and starts a session on comments containing `@openhands`
(e.g. conversations `4ced86b81b634bea879eb113db337519`, `5c6949a1b5a34048b74f26945d3bbcaf`).
That is the OpenHands GitHub integration, **not** this automation. The two must not be conflated.

### 3.3 `enabled: false` is NOT a safe "draft" — it still ran [V]
This is the most important finding, and it contradicts the naive reading of the API.

- Automation created with `"enabled": false` → `state=INACTIVE`. [V]
- `POST /dispatch` on the INACTIVE automation still started a real run
  (`50c4fbec…`, `trigger_source=manual`). [V]
- Later, **two runs with `trigger_source=event`** appeared (`0c2fe620…`, `3b276fea…`) on the
  same INACTIVE automation, and started real sandboxes/conversations
  (`9d96144246db…`, `c3a91d7b839d…`). [V]
- The automation was only stopped by **deleting** it (204 → 404). [V]

**Conclusion:** on this runtime, `enabled: false` gates *scheduled* cron firing and the UI, but
does **not** fully gate manual dispatch or event dispatch. A "disabled draft" is therefore **not
an inert artifact**. It must be deleted, not left disabled. [V]

## 4. Cost / quota — this is NOT free [V]

The zero-cost gate fails, and the exact model is only partly documented.

| signal | value | source |
|---|---|---|
| Payment method on file | `false` | `POST /api/billing/has-payment-method` [V] |
| Credits | `"0.00"` | `GET /api/billing/credits` [V] |
| Subscription access | `null` | `GET /api/billing/subscription-access` [V] |
| Existing automation runs (cron) | 41 runs, `cost` mostly `0.0`, **2 runs non-zero** (0.00133, 0.00266) | `GET /…/aa4ae120…/runs?limit=100` [V] |
| Org usage | 87 agent runs, **estimated_spend $0.557**, 729M tokens | `GET /api/organizations/{org}/conversations/usage-stats` [V] |
| Lifetime spend | **$28.63** | `GET /api/organizations/{org}/members/financial` [V] |
| Published plan | Agent Canvas **Free** (self-host); **Teams $500/month**, 5,000 sessions/month cap | https://www.openhands.dev/pricing [C] |

What the docs do **not** state, and what I could not establish: whether an automation run consumes
paid credits, how a run is billed when `credits = 0.00` and no card is on file, and whether
event-triggered runs bill differently from cron runs. The docs are silent on automation billing;
the pricing page prices *plans*, not automation runs. [U]

**Per the zero-cost gate this is UNVERIFIED, so it must not be adopted.** The observed evidence
(actual non-zero `cost` on two runs, and a real spend counter that moved from $0.55 to $0.557
during this session) points to **usage-based billing**, which the gate classifies as an
irreversible money decision that only Ahmed may make. [V]

## 5. The proposed filter (server-validated syntax) [V]

```
icontains(comment.body, '@watcher')
  && repository.full_name == 'madnessgate44-debug/brain'
  && issue.number == `240`
  && !ends_with(sender.login, '[bot]')
```

Notes from the live runtime:
- JMESPath **numbers need backticks** (`` `240` ``). Bare `240` is a 422 parse error. [V]
- `ends_with` is accepted. [V]
- The runtime also accepted a `wake_agent: true` / `destination: dispatch_run` shape on the
  stored trigger; that is runtime-added, not request-supplied. [V]

## 6. The prompt (as created, then deleted)

Full text is preserved in `/watcher/channel/receiver-payload.json`. It implements:
untrusted-input handling, fail-closed on marker/repo/issue/bot, KV dedup by comment id, exactly one
`[TO-CHATGPT]` reply with no `@watcher` marker, and a persistence record.

## 7. Recommendation (no owner question needed for the technical call)

1. **Do not enable** any event automation on this account. The receiver cannot be scoped correctly
   (no claimed team org) and the spend model is unverified. [V]/[U]
2. **Keep the channel human-mediated for now** (the current, honest state) and treat the
   `@openhands` bot as the only live GitHub→OpenHands path. [V]
3. If an autonomous receiver is wanted, the smallest correct path is a **GitHub Actions
   `issue_comment` workflow** in this repo — but it is blocked on the Actions-secrets 403
   (`GET /repos/.../actions/secrets` → 403), which is unchanged. [V]
4. Any spend decision is Ahmed's, one yes/no, per the zero-cost gate and WATCHER.md §15. [V]

## 8. Rollback performed

Draft automation `7aea2400-61ef-42dd-8b6f-c4de5266bf9f` was **deleted** (`DELETE` → 204, `GET` → 404).
Automation list is back to the 2 pre-existing entries. [V]
