# CHATGPT_INTEGRATION — making ChatGPT a first-class participant (Phase 1)

> **PARKED (Owner direction, 2026-11-08).** The Brain↔ChatGPT **MCP connector** workstream is parked.
> It is **not applicable for now** and must not be treated as a blocker or a standing Owner action.
> GitHub issue #292 remains the durable coordination channel. Do not re-raise "mount the connector"
> as a task. Resume only if the Owner explicitly un-parks it. The rest of this document is kept as the
> prior analysis; read it as history, not as an active workstream.

Owner requirement (this session): "all agents should be working on automation … brain has to be the
brain, he has to learn patterns, find problems, and resolve it, search online to resolve it — that's
phase one." ChatGPT ticket `6713088768` makes "ChatGPT as a first-class participant" an explicit
Phase 1 workstream; ticket `6713057700` asks for a status/feasibility answer. This file is the
evidence-backed feasibility matrix + design + proof plan.

Read-only; no permission change, secret provisioning, cost, or new external service. Tags: `[V]`
verified, `[U]` unproven, `[B]` blocked, `[OWNER ACTION]` needs the Owner.

## 0. Verdict in one line

**A supported path already exists** — Brain ships a live MCP connector that any ChatGPT connector
slot can mount (`brain_chat`, mission tools). ChatGPT can also read/write this repo through GitHub.
The missing piece is not capability; it is **(a)** a versioned context packet Brain keeps current,
**(b)** an event/trigger contract so a ticket reaches ChatGPT without the Owner relaying it, and
**(c)** the Owner adding the connector + key in ChatGPT. Autonomous, owner-absent invocation of
ChatGPT is **not** possible on current platform boundaries and is marked `[B]`.

## 1. What Brain already has (evidence)

| Capability | Evidence | Tag |
|---|---|---|
| Brain MCP connector, live | `docs/CONNECTOR.md:6-10`; `POST https://brain-one-pi.vercel.app/mcp` → **HTTP 401** (`{"detail":"Invalid Brain control key."}`) — route deployed, auth enforced | `[V]` |
| Connector tools | `docs/CONNECTOR.md:37-48`: `brain_chat`, `brain_create_mission`, `brain_start_mission`, `brain_get_mission`, `brain_list_missions`, `brain_list_artifacts` | `[V]` |
| Connector auth model | one Bearer key `BRAIN_CONTROL_API_KEY` (≥24 chars); missing key → `503`, wrong key → `401` (`docs/CONNECTOR.md:20-31`) | `[V]` |
| Durable hub | GitHub issue #292 (survives sessions) | `[V]` |
| Free-first research automation | `.github/workflows/brain-rd-discovery.yml` (workflow_dispatch, mission input), `brain-browser-research-issue.yml` (issue-opened `/brain browse`) | `[V]` |
| Live local room | SwarmChat on `127.0.0.1:12000`, channels `#general/#audits/#reports/#alerts`, identities owner/watcher/shadow/forge/openhands/cloud | `[V]` |
| SwarmChat durability | sandbox-local; dies on reset; a Cloud automation cannot reach it | `[V]` |

## 2. Feasibility matrix

| # | Capability | Verified current support | Evidence | Limitation | Recommended design | Owner | Acceptance test |
|---|---|---|---|---|---|---|---|
| 1 | ChatGPT **reads** Brain state | **yes** | ChatGPT comments on #292 (it inspects GitHub) | reads only what is in GitHub; no live room | Brain maintains a versioned context packet in-repo + a pinned "latest" comment on #292 | OpenHands | ChatGPT answers "what is the current phase?" from the packet alone |
| 2 | ChatGPT **writes** a ticket/spec | **yes** | #292 tickets `6713057700`, `6713088768` | manual, owner-relayed today | a fixed ticket template + a `CHATGPT-` id prefix; Brain parses on new comment | OpenHands | a ChatGPT ticket with `ASK` is picked up and answered in-thread |
| 3 | Brain **invokes** ChatGPT | **no (platform boundary)** `[B]` | no ChatGPT inbound webhook exists to this repo | ChatGPT has no public inbound API for a repo to call | inversion: Brain posts an `[OWNER ACTION]`/`CHATGPT` ticket; the Owner (or a ChatGPT scheduled task) opens a turn | Owner | a Brain ticket results in a ChatGPT reply within one Owner turn |
| 4 | ChatGPT **calls Brain** tools | **yes, when mounted** | `docs/CONNECTOR.md:37-48`; live endpoint 401 | needs the Owner to add the connector + key in ChatGPT | mount the MCP connector; ChatGPT calls `brain_chat`/`brain_list_missions` | Owner | ChatGPT calls `brain_chat` and returns the reply |
| 5 | **Durable** bidirectional room | **partial** | #292 durable; SwarmChat not | SwarmChat dies on reset | canonical room = **#292**; SwarmChat = live bonus only | OpenHands | both sides correlate a message to a ticket id |
| 6 | **Autonomous** ChatGPT turn (owner absent) | **no** `[B]` | no supported invocation path | ChatGPT cannot run in the background on its own | fallback: Brain queues `[OWNER ACTION]`; a ChatGPT **scheduled task** may poll #292 if the Owner enables it | Owner | a queued ticket is answered without the Owner pasting content |
| 7 | Shared context on each turn | **no, to build** | no context packet exists | ChatGPT must reconstruct state each time | ship `docs/readiness/BRAIN_CONTEXT.md` (this PR), Brain refreshes it daily | OpenHands | packet has phase, products, open tickets, blockers, cursor, last-sync |
| 8 | Redaction on the path | **yes** | exporter `redact()` + `check_leaks()` gate (PR #295) | — | every outbound artifact passes the leak gate | OpenHands | a secret-shaped test value is redacted before post |

## 3. Communication topology

- **Canonical durable room: GitHub issue #292.** It survives sessions and is where every participant
  already reads/writes. SwarmChat stays a *live* channel, never the record.
- **Inbound to Brain (ChatGPT → Brain):** a comment on #292 (works today). Brain reads it in its loop
  or on `issue_comment`.
- **Outbound from Brain (Brain → ChatGPT):** a ticket comment on #292 with a `CHATGPT` label and an
  `ASK`. Brain cannot push to ChatGPT; it posts and waits.
- **Direct tool path (ChatGPT → Brain runtime):** the MCP connector (mounted in ChatGPT).
- **Identity:** GitHub = the account that comments; MCP = `BRAIN_CONTROL_API_KEY`. Correlate every
  message with a ticket id (`T<n>` or `CHATGPT-<n>`) so a reply maps to its request.

## 4. Invocation and automation — the exact boundary

| Path | Autonomous today? | How |
|---|---|---|
| Brain audits/researches/fixes on schedule | **yes** | cron workflows (`brain-rd-discovery`, `session-agent-loop`, `watcher-*`) |
| Brain posts a ticket for ChatGPT | **yes** | comment on #292 |
| ChatGPT produces the answer | **no** — needs a turn | Owner opens ChatGPT, or a ChatGPT **scheduled task** polls #292 |
| ChatGPT calls Brain tools | **yes**, once mounted | MCP connector |
| ChatGPT executes in the background with no turn | **no** `[B]` | not supported |

So the honest model: **Brain is autonomous; ChatGPT is pull-based.** Brain never blocks on ChatGPT —
it queues the question, keeps working, and folds in the answer when it arrives (the ticket's `STATE`
stays open until then).

## 5. Shared context packet

`docs/readiness/BRAIN_CONTEXT.md` (shipped in this PR) is the minimal versioned packet: current
phase, active products + priority, open tickets, blockers, the source cursor, last successful sync,
and links to transcripts/artifacts rather than copying history. Brain refreshes it each run; the
packet carries a `context_version` and a `last_sync` UTC timestamp so staleness is visible.

## 6. Two-way handoff

1. Brain opens a ticket on #292 with `ASK` + acceptance criteria (or ChatGPT opens one).
2. ChatGPT replies in-thread, naming the ticket id back and stating `STATE`.
3. Brain/OpenHands acknowledges, does the work, and replies with evidence.
4. If no reply arrives in a bounded window, Brain escalates with one `[OWNER ACTION]` line — it never
   stalls silently.

## 7. Event and state model

| Concern | Rule |
|---|---|
| IDs | ticket `T<n>` (Brain) / `CHATGPT-<n>` (ChatGPT); correlation required in every message |
| Timestamps | GitHub clock (`github_now()` in `watcher/bridge/hub.py`), UTC in the record, Cairo for the Owner |
| Ordering | by comment id (monotonic) |
| Idempotency | a ticket id is processed once; a re-post with the same id is a no-op |
| Retries | API 429 → backoff (exporter already does this); a failed post retries, never duplicates |
| Cursor | the last processed comment id, stored in `watcher/bridge/state.json` (already present) |
| Audit trail | every ticket + reply stays on #292 |

## 8. Safety and permissions

- Least privilege: the MCP key is one scoped `BRAIN_CONTROL_API_KEY`; the repo token is the Actions
  `GITHUB_TOKEN`. No new secret is created by this work.
- No secret value in any message, log, or artifact; the leak gate (PR #295) fails closed.
- Hard distinction: **recommendation** (a comment) ≠ **task request** (a ticket) ≠ **authorization**
  (an Owner approval). Only the Owner authorizes consequential actions.
- Owner approval gates: adding the connector/key in ChatGPT; any secret provisioning; any merge.

## 9. Availability and observability

- While the Owner is away: Brain keeps running its cron loops; ChatGPT tickets queue.
- Health check: the MCP endpoint answers `401` without a key (proves it is up); a keyed `brain_chat`
  call proves the tool path. #292's newest comment id + the context packet's `last_sync` prove the
  loop is current.
- Failures: a ticket with no reply past its window is flagged `[OWNER ACTION]`; a failed workflow run
  raises on the Actions tab.

## 10. Practical alternatives compared

| Route | Works today | Verdict |
|---|---|---|
| GitHub #292 comments | yes | **primary durable path** |
| Brain MCP connector in ChatGPT | yes (mount) | **primary tool path** |
| SwarmChat live room | yes, sandbox-local | live bonus; not durable |
| ChatGPT direct inbound API to Brain | no | not offered by the platform |
| Brain polling ChatGPT internals | no | unsupported; rejected |

## 11. Minimal end-to-end proof (the test protocol)

Brain cannot drive a ChatGPT turn, so the proof is split; the ChatGPT half is `[OWNER ACTION]`.

1. **Brain side (do now, automated):** post a uniquely identified test ticket to #292 —
   `T-PROOF-<nonce>` with a correlation token and a secret-shaped value; assert it appears and that
   the secret is redacted.
2. **ChatGPT side `[OWNER ACTION]`:** in ChatGPT, (a) add the MCP connector
   `https://brain-one-pi.vercel.app/mcp` + `BRAIN_CONTROL_API_KEY`, and (b) reply to `T-PROOF-<nonce>`
   naming the id back and calling `brain_chat` once.
3. **Correlation + close:** Brain sees the reply, matches `T-PROOF-<nonce>`, and closes the ticket.
   Success = correlation proven, redaction proven, one retry survived, observable on #292.

## 12. Dependency-ordered implementation plan

| Step | Action | Depends on | Owner |
|---|---|---|---|
| 1 | Ship `BRAIN_CONTEXT.md` + this matrix | — | OpenHands (this PR) |
| 2 | Add a `CHATGPT` ticket template + parser in the loop | step 1 | OpenHands |
| 3 | Brain refreshes `BRAIN_CONTEXT.md` each run | step 1 | OpenHands |
| 4 | Run the `T-PROOF` test (Brain half) | step 1 | OpenHands |
| 5 | Mount the MCP connector in ChatGPT | Owner adds key | `[OWNER ACTION]` |
| 6 | Complete the `T-PROOF` test (ChatGPT half) | step 5 | Owner/ChatGPT |
| 7 | Optional: a ChatGPT scheduled task that polls #292 | step 5 | `[OWNER ACTION]` |

## 13. Blockers

| ID | Blocker | Type | Smallest safe alternative |
|---|---|---|---|
| G1 | ChatGPT has no autonomous inbound invocation | `[B]` platform | Brain queues a ticket; Owner or a ChatGPT scheduled task opens the turn |
| G2 | Owner must add the MCP connector + key in ChatGPT | `[OWNER ACTION]` | ChatGPT uses GitHub comments meanwhile |
| G3 | SwarmChat is not durable | `[B]` | canonical room is #292 |
| G4 | A ChatGPT scheduled task may need a paid tier | `[OWNER ACTION]` | keep the Owner-in-the-loop relay |

_Phase 1 workstream. Read-only; no permission change, secret provisioning, cost, or new service._
