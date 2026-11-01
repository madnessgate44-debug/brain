# Forge interrogation matrix (read-only)

Walk each row. Record exactly one status and the evidence ref. Do not mark a row `tested` unless a
real run or file read in this session backs it.

Status vocabulary: `implemented` (code exists), `tested` (observed working this session),
`partially tested`, `untested`, `not found`.

| # | area | what to inspect | evidence ref |
|---|---|---|---|
| 1 | Architecture | `src/kernel/loop.ts`, `src/agent/loop.ts`, `src/agent/stages.ts` — mission pipeline vs engine loop | |
| 2 | Capabilities | `src/agent/tools.ts` — read-only vs mutating tool tiers | |
| 3 | Tool permissions | `src/agent/policy.ts` — permission profile gates | |
| 4 | Browser | `src/services/browser.ts` — tools, viewport, stealth | |
| 5 | Agent orchestration | `src/company/team.ts`, `src/company/bus.ts` — sequential roles, artifact handoff | |
| 6 | Company workflows | `src/company/company.ts`, `.github/workflows/company-*.yml` | |
| 7 | Persistence / resumption | checkpoint/resume code; `maxMissionAttempts` in `src/agent/limits.ts` | |
| 8 | Verification | `src/agent/sentinel.ts` — merge gates; `src/agent/runtime-verify.ts` | |
| 9 | Failure recovery | `src/agent/diagnosis.ts`, `maxRepairAttempts` | |
| 10 | Security boundaries | `resolveInWorkspace` symlink containment; `AUTHORIZED_COMMANDS` allow-list | |
| 11 | Cost | `src/model-routing.ts` keyless policy; per-run cost from the automation API | |
| 12 | Evidence contract | `.firstborn/evidence/<id>.json`; artifact `forge-evidence` | |
| 13 | Trigger paths | owner issue + label `forge-task`; dispatch `mode=coding|audit` | |
| 14 | CI health | failing workflow runs and their root cause | |

## Method
- Read the file or run the read-only check; never infer from a README.
- For a runtime row, cite a run id and timestamp.
- Note the root cause, not just the symptom.
- Distinguish "implemented in code" from "demonstrated working".
