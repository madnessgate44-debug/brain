# Forge internals — verified from Firstborn source (2026-11-01)

All facts below were read directly from `madnessgate44-debug/Firstborn@main` this session, not
copied from prose. Cite the file path for each.

## Mission path vs engine
- `docs/CHATGPT-OPERATING-FORGE.md`: the *mission* is a fixed pipeline
  `VALIDATE → INSPECT → PLAN → APPLY → TEST → COMMIT → PR → POLICY`. Forge cannot act outside it.
- The lower *engine* is an open-ended bounded loop: `src/agent/loop.ts` (8869 B),
  `src/kernel/loop.ts`, `src/agent/loop-runner.ts`, `src/agent/stages.ts`. So an open-ended
  loop is partly built already.

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
