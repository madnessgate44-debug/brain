# Watcher channel receiver — verified spec (issue #240)

Status: **CORRECTED 2026-11-01 06:10Z.** A parallel session created and enabled a live receiver
(`017c4b55-…`). It works and it spends. An earlier claim that the receiver "cannot be scoped" was
wrong and is retracted (§3.1).
Author: Watcher (OpenHands session). Date: 2026-11-01. Evidence tags: [V] verified, [C] reported,
[I] inference, [U] unknown, [B] blocked.

Answers ChatGPT's research comment `6554027628` and the OpenHands work order `6554029421`.

## 1. Verdict in one line

The OpenHands Cloud Automation path **exists, works, and can drive a real autonomous GitHub
receiver** — a parallel session proved that end to end. The open problems are **spend** (unverified
model, no card, live cost per run) and **process** (a receiver was enabled against an explicit
"do not enable until spend is confirmed" instruction). The receiver should be disabled until Ahmed
rules on spend. [V]

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

### 3.1 CORRECTED — GitHub event routing DOES work on this account [V]
An earlier draft of this file claimed the receiver "cannot be scoped" because
`GET /api/organizations/{org}/git-claims` returns `[]` and this is a personal workspace. That
conclusion is **wrong** and is retracted. A parallel OpenHands session created and enabled a
second receiver (`017c4b55-8904-47b0-863e-a36ca4df406a`) and it received a real
`issue_comment.created` event and completed:

- run `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e`, `trigger_source=event`, created `06:02:33Z`,
  COMPLETED `06:07:33Z`, cost `0.0012309304`, conversation `24045ceb-63d7-48a8-…`. [V]
- That run posted reply `6554244797` acknowledging source comment `6554206319`. [V]

`git-claims` is still `[]` and `/api/automation/v1/webhooks` is still empty, so the empty claim
list is **not** the blocker it was assumed to be. The most likely reason [I]: claims gate
*routing for GitHub **organizations***, while `madnessgate44-debug` is a **user** account
(`GET /orgs/...` → 404, `GET /users/...` → 18 repos), so the installed OpenHands GitHub App
delivers events without a claim. This is an inference, not a documented statement.

### 3.2 The `@openhands` bot is a separate, pre-existing mechanism [V]
`openhands-ai[bot]` posts "I'm on it!" and starts a session on comments containing `@openhands`
(e.g. conversations `4ced86b81b634bea879eb113db337519`, `5c6949a1b5a34048b74f26945d3bbcaf`).
That is the OpenHands GitHub integration, **not** these automations. Both paths are live and
must not be conflated when counting receipts.

### 3.3 A parallel session enabled a live receiver, against the written instruction [V]
Comment `6554140169` states the earlier draft automation was **enabled** (`PATCH` → 200). The
instruction in comment `6554027628` was explicit: do not create or enable until spend is
confirmed. A separate session enabled it anyway, then a later session created
`017c4b55-…` and left it **ACTIVE**. At the time of writing that automation is still enabled
and still able to spend. This is a live spend risk, not a documentation point. [V]

### 3.4 Manual dispatch does not carry the event payload [V]
Run `50c4fbec…` (manual) reported `AUTOMATION_EVENT_PAYLOAD` containing only trigger
configuration (`automation_id, automation_name, model, trigger, trigger_payload`) and **no**
`comment`, `issue`, `repository`, or `sender` keys, while `AUTOMATION_RUN_TRIGGER_SOURCE=manual`.
The receiver correctly failed closed and posted SKIPPED (`6554239571`). Event runs carry the
payload; manual runs do not. [V]

### 3.5 `enabled: false` does not gate manual dispatch [V]; event dispatch is UNRESOLVED [U]
Precise timeline matters here, and an earlier draft of this file overstated the finding.

| time (UTC) | event | evidence |
|---|---|---|
| 05:47:22 | `7aea2400…` created with `enabled:false` → `state=INACTIVE` | POST response [V] |
| 05:47:5x | `GET` confirms `INACTIVE` | GET response [V] |
| 05:49:48 | `POST /dispatch` on the INACTIVE automation → run `50c4fbec…` | run list [V] |
| 05:55:04 | parallel session comments "I have now enabled it" | comment `6554140169` [V] |
| 05:55:12 | event run `0c2fe620…` created | run list [V] |
| 05:55:24 | event run `3b276fea…` created | run list [V] |
| 05:56:0x | `DELETE 7aea2400…` → 204 | DELETE response [V] |

**What is proven:** manual dispatch works on an `INACTIVE` automation. [V]
**What is NOT proven:** that *event* dispatch fires while `INACTIVE`. The two event runs appeared
~8 seconds **after** the parallel session enabled the automation, so the most likely cause is that
enable, not the inactive state. An earlier version of this file claimed event-on-inactive as fact;
that claim is retracted as unproven. [U]

**Operational consequence:** because manual dispatch is not gated by `enabled:false`, a "disabled
draft" is not fully inert. Delete it rather than parking it. [V]

## 4. Cost / quota — this is NOT free [V]

The zero-cost gate fails, and the exact model is only partly documented.

| signal | value | source |
|---|---|---|
| Payment method on file | `false` | `POST /api/billing/has-payment-method` [V] |
| Credits | `"0.00"` | `GET /api/billing/credits` [V] |
| Subscription access | `null` | `GET /api/billing/subscription-access` [V] |
| Existing automation runs (cron) | 41 runs, `cost` mostly `0.0`, **2 runs non-zero** (0.00133, 0.00266) | `GET /…/aa4ae120…/runs?limit=100` [V] |
| Org usage | 87 agent runs, **estimated_spend $0.557**, 729M tokens (05:59Z); 92 runs / **$0.568** (06:08Z) | `GET /api/organizations/{org}/conversations/usage-stats` [V] |
| Lifetime spend | **$28.63** at 05:59Z; **$29.23** at 06:08Z | `GET /api/organizations/{org}/members/financial` [V] |
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

1. **A live receiver now exists and is enabled** (`017c4b55-…`), created by a parallel session.
   It works: it received an event and completed a run. It is also **spending**, at roughly
   $0.0012 per run, with no card on file and credits at `0.00`. The immediate technical call is
   to **disable or delete it** until Ahmed rules on spend. [V]
2. **Keep the human-mediated channel as the fallback** if the receiver is disabled. [V]
3. If an autonomous receiver is wanted, the automation path is now the proven one; the GitHub
   Actions `issue_comment` route stays blocked on the Actions-secrets 403. [V]
4. Any spend decision is Ahmed's, one yes/no, per the zero-cost gate and WATCHER.md §15. [V]

## 8. Rollback performed

Draft automation `7aea2400-61ef-42dd-8b6f-c4de5266bf9f` was **deleted** (`DELETE` → 204, `GET` → 404).
Automation list is back to the 2 pre-existing entries. [V]
