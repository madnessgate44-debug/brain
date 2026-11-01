# Forge internals — verified from Firstborn source (2026-11-01)

All facts below were read directly from `madnessgate44-debug/Firstborn@main` this session, not
copied from prose. Cite the file path for each.

## Mission path vs engine
- `docs/CHATGPT-OPERATING-FORGE.md`: the *mission* is a fixed pipeline
  `VALIDATE → INSPECT → PLAN → APPLY → TEST → COMMIT → PR → POLICY`. Forge cannot act outside it.
- The lower *engine* is a bounded look/think/act/observe loop: `src/agent/loop.ts` (8869 B),
  wired by `src/agent/loop-runner.ts` (to `ModelService.chooseNextAction` + tools). **Classification
  (per ChatGPT reconciliation 6554500481): implemented in a separate runner; use by the default
  Forge mission path is NOT yet demonstrated** — the default `.github/workflows/forge.yml` path
  invokes `src/agent/forge-runner.ts` (the fixed-stage mission), not the loop runner.

## Model routing (`src/model-routing.ts`)
- Policy is a pure function of environment + tier (`easy` / `hard`).
- Credential env names: `GEMINI/GOOGLE/GROQ/OPENROUTER/CLOUDFLARE/ZAI/COHERE/CEREBRAS/MISTRAL/`
  `NVIDIA/NIM/KILO_API_KEY` plus the `FREELM_*_KEYS` variants.
- Keyless fallback: freelm anonymous Kilo/OVHcloud endpoints, priority 100 (tried last), ~3 req/min.
- `FIRSTBORN_KEYLESS_ONLY=true` → strict keyless lock; all provider keys are stripped.
- `src/services/model-routing-policy.ts` forces `hard` tier for coding → keyed-first when a key exists.

## Ceilings (`src/agent/limits.ts`) — all env-configurable
| env | default | max |
|---|---|---|
| `FORGE_MAX_FILES` | 5 | 50 |
| `FORGE_MAX_EDITS` | 8 | 200 |
| `FORGE_MAX_PATCH_BYTES` | 100 KB | 5 MB |
| `FORGE_MAX_MODEL_CALLS` | 8 | 50 |
| `FORGE_MAX_REPAIRS` | 2 | 10 |
| `FORGE_MAX_RUNTIME_MS` | 10 min | 60 min |
| `FORGE_MAX_MISSION_ATTEMPTS` | 1 | 5 |

## Sentinel (`src/agent/sentinel.ts`)
Independent verifier, separate workflow run, never Forge approving itself. Three gates:
1. Source branch must start with `forge/`, must not be `main`/`master`, must not equal target.
2. Every required check (`lint,build,test` by default) must have run and passed; a missing check
   is a failure, never a pass.
3. Optional model judge can only add caution: `reject`/`uncertain` → hold.
Decision is a pure, unit-testable function.

## Team (`src/company/team.ts`)
Sequential roster; each role runs the loop with its own mandate/tools and posts a typed artifact
to the shared bus (`src/company/bus.ts`); later roles read earlier artifacts. No concurrent-role
code found.

## Cross-repo (`docs/forge-cross-repository.md`)
Requires `FORGE_CROSS_REPO_TOKEN` (fine-grained: Contents RW, PR RW, Metadata R). Fails closed if
push permission cannot be verified.

## Evidence contract
`.firstborn/evidence/<task-id>.json`, uploaded as artifact `forge-evidence`. Fields:
`status`, `baseCommitSha`, `branchName`, `headCommitSha`, `prUrl`, `modelInvoked`,
`requirements[]`, `testResults[]`, `diagnosis`, `trace[]`, `errorMessage`/`blockerReason`.

## Known failing test (found by a parallel session)
`tests/company.test.ts:270` expects `/Runtime ceiling/` but gets `Step ceiling reached (3)`: a
tool deadline caught at `src/kernel/loop.ts:180` becomes a failed observation, so the loop exits
at the step ceiling (`:186`) before the runtime check (`:121`).

## Tools and commands (`src/agent/tools.ts`, `src/services/test-runner.ts`)
- Capability tiers in `tools.ts`: read-only tools always registered (`list_files, read_file,
  search, find_files, think, fetch_url`); mutating tools (`edit_file, write_file, run_check`)
  registered only when the permission profile allows branch writes.
- `AUTHORIZED_COMMANDS` is an allow-list of exactly **10** entries (verified 2026-11-01):
  `npm install --ignore-scripts`, `npm run lint`, `npm run test`, `npm test`, `npm run build`,
  `npm run model:smoke`, `npx tsc --noEmit`, `git status`, `git diff`, `git diff --check`.
  Arbitrary shell is impossible by design.
- `src/services/browser.ts`: 9 browser tools; single viewport 1280x800 (no mobile viewport).
