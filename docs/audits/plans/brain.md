# Production plan — brain

Goal: be the control plane — learn patterns, find problems, resolve them, and report daily to every channel.

The daily audit measures this repo against this plan and reports progress, not a raw defect list.
Statuses: done / in-progress / blocked / todo.

| id | item | status | evidence |
|---|---|---|---|
| B1 | Multi-channel daily report producer + fan-out | done | `scripts/daily_report.py` composes; `scripts/report_to_channels.py` posts (PR #293 merged 2026-11-07T22:41:05Z) |
| B2 | Repo queue + rotation cursor committed | done | `docs/audits/repo-queue.json`, `docs/audits/cursor.json` |
| B3 | Production plan per active product | done | `docs/audits/plans/*.md` (brain, Amina, Firstborn, smart-farm, Gahiz) |
| B4 | Daily report wired to a scheduled workflow | done | `.github/workflows/brain-daily-report.yml`; verified `GET actions/runs?event=schedule` — ran 2026-11-14T12:59Z and 2026-11-15T13:28Z, both success |
| B5 | Hub routing reconciled to canonical #292 (was #240) | in-progress | PR #298 `openhands/hub-reconciliation-292` open, not merged |
| B6 | Shadow independent audit unblocked (model route) | blocked | `docs/readiness/BLOCKER_REGISTER.md` B1; pool secrets absent |
| B7 | The daily report's own W1 number must be true | in-progress | shallow checkout made `report-only share` read 0% (real 31%, 18/58); fixed in `scripts/agent_status.py` + 4 workflows; PR open |
