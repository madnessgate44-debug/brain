# BRAIN_CONTEXT — the shared context packet (v1)

The minimal, versioned state any participant (especially ChatGPT) can read on each turn, so nobody
has to reconstruct context or paste history. Brain refreshes this each run; `context_version` and
`last_sync` make staleness visible. Links, not copies — unbounded history stays in the artifacts.

```
context_version: 1
last_sync: 2026-11-07T21:20:00Z   (UTC; Cairo = 23:20)
source_cursor: brain#292 newest comment id 6713102895
phase: 1 — readiness (in review) -> 2 — Amina proving exercise (gated)
```

## 1. Objective (Owner)

Make Brain the brain: it **learns patterns, finds problems, resolves them, and searches online to
resolve them** — and every agent (OpenHands, ChatGPT, Forge, Shadow, Watcher) works on **automation**,
not manual steps. This is Phase 1.

## 2. How Brain works as the brain (already wired)

| Function | Mechanism | Evidence |
|---|---|---|
| find problems | `purpose_audit.py` (depth audit), `scripts/agent_status.py` | `watcher/knowledge/tools/` |
| search online to resolve | `brain-rd-discovery.yml` (mission → evidence-linked recommendation), `brain-browser-research-issue.yml` (`/brain browse`) | `.github/workflows/` |
| resolve / fix | `session-agent-loop.yml`, the daily loop, Forge (bounded PRs) | `.github/workflows/`, `Firstborn` |
| learn patterns | `watcher-learning.yml`, `watcher/skills/watcher-learning` | `.github/workflows/`, `watcher/` |
| report | `scripts/report_to_channels.py` → #292 + SwarmChat | PR #293 |
| self-improve | `watcher-learning.yml` + the Shadow gate | `WATCHER.md §9` |

Gap to close in Phase 1: prove the research route (`brain-rd-discovery`) end-to-end on a live issue
(`BLOCKER_REGISTER.md` B5).

## 3. Active products + priority (time-to-first-revenue)

Active scope is exactly these five. Do not reactivate the wider fleet.

1. **Amina / Miss Noor** (`madnessgate44-debug/Amina`) — **first for the next exercise; one-week
   deadline.** Live on Vercel; needs auth + payment.
2. **Brain** (`madnessgate44-debug/brain`) — internal control plane (the orchestrator).
3. **Forge / Firstborn** (`madnessgate44-debug/Firstborn`) — internal infra (service/licence).
4. **Smart Farm** (`madnessgate44-debug/smart-farm`) — Kotlin Android, one real customer, no release yet.
5. **Gahiz** (`madnessgate44-debug/Gahiz`) — BPO assessment, scaffold.

> Priority correction (2026-11-07): an earlier draft of this packet ranked Smart Farm above Amina.
> That is wrong. **Amina is first** (Owner direction: the one-week deadline).

## 4. Open tickets (correlate replies by id)

| Ticket | Where | State |
|---|---|---|
| `T30` | #292 `6712989336` | ticketing protocol enforced |
| `T31` | #292 `6713102895` | Phase 1 delivered (readiness + archive) |
| `CHATGPT-status` | #292 `6713057700` | answered by T31 |
| `CHATGPT-participant` | #292 `6713088768` | this workstream |
| `T-PROOF-<nonce>` | #292 | pending (ChatGPT half is `[OWNER ACTION]`) |

## 5. Blockers (see BLOCKER_REGISTER.md)

- **Shadow's model route** absent (`OHGeminiAPI`, `GEMINI_POOL_1..7`) → no independent audit → the
  `LOOP.md` merge rule cannot be satisfied. **The single gate for Phase 2.**
- C1–C5 instruction conflicts (ChatGPT role; merge authority; read-only default; key ownership; hub id).
- G1–G4 ChatGPT-integration boundaries (`CHATGPT_INTEGRATION.md` §13).

## 6. Where the evidence lives

- Tickets + reports: `brain#292` (durable).
- Conversation archive: `docs/sessions/<date>.md` (automatic, daily).
- Readiness: `docs/readiness/*`.
- Protocol: `docs/TICKETING_PROTOCOL.md`.
- Live room: SwarmChat `#general/#audits/#reports/#alerts` (live only, not durable).

## 7. Last successful sync / health

- Hub cursor: #292 `6713102895` `[V]`.
- MCP connector health: `POST /mcp` without a key → **401** (up, auth enforced) `[V]`. **PARKED**: the
  ChatGPT↔Brain MCP integration is not applicable for now (Owner direction 2026-11-08); GitHub #292 is
  the durable channel.
- Archive last success: `Watcher session log` 2026-11-07T06:23:25Z `[V]`.

## 6. Daily checkpoint cadence (who checks what)

| Checkpoint (Cairo) | Owner | Mechanism | Status |
|---|---|---|---|
| 09:00, 14:00, 20:00 | ChatGPT | ChatGPT scheduled tasks | `[V]` enabled (per `6713885785`) |
| 06:30, 17:00 | **OpenHands** | `.github/workflows/brain-checkpoints.yml` + `scripts/checkpoint.py` (deterministic, no model) | `[V]` workflow on PR #295; `[U]` **not runnable until merged** — GitHub only runs `schedule`/`workflow_dispatch` from the default branch |

- 06:00 Cairo = 04:00 UTC **conflicts** with `watcher-daily.yml` (`cron: "0 4 * * *"`), so the nearest
  supported time is used: **04:30 UTC = 06:30 Cairo**. 17:00 Cairo = 15:00 UTC, no conflict, used as asked.
- The workflow posts to #292 (or a "no material change" note), tagged VERIFIED/UNPROVEN/BLOCKED, with
  Cairo + UTC timestamps, run IDs, and SHAs. It never waits for ChatGPT's checkpoints to do engineering work.

**Explicit honesty note.** A cadence written in these docs is **not** a scheduler, and an agent session
**cannot self-schedule** — it only acts on invocation. The 06:30/17:00 checkpoints become real only when
`brain-checkpoints.yml` exists on the **default branch** and GitHub's cron fires; to claim a schedule is
active, verify with `GET /repos/{owner}/{repo}/actions/runs?event=schedule` and quote the run count. As
of this writing that count is **0** (the workflow is on PR #295, unmerged).

_Brain refreshes this file each run. Read-only; no secret value._
