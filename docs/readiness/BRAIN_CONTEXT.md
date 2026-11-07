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

1. **Smart Farm** (`madnessgate44-debug/smart-farm`) — Kotlin Android, one real customer, no release yet.
2. **Amina / Miss Noor** (`madnessgate44-debug/Amina`) — live on Vercel, needs auth + payment.
3. **Gahiz** (`madnessgate44-debug/Gahiz`) — BPO assessment, scaffold.
4. **Forge / Firstborn** (`madnessgate44-debug/Firstborn`) — internal infra (service/licence).
5. **Brain** (`madnessgate44-debug/brain`) — internal control plane.

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
- MCP connector health: `POST /mcp` without a key → **401** (up, auth enforced) `[V]`.
- Archive last success: `Watcher session log` 2026-11-07T06:23:25Z `[V]`.

_Brain refreshes this file each run. Read-only; no secret value._
