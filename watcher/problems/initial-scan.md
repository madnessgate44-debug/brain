# Initial scan — madnessgate44-debug

Section 12 First Action 1. Date: 2026-11-01. Method: GitHub REST API reads only (no writes).
Owner is a **user** account, not an organization.

## Repos (18)

| repo | lang | size | last push | open issues | workflows | notes |
|---|---|---|---|---|---|---|
| brain | Python | 1.0 MB | 2026-11-01 | 118 | 16 | Active. Watcher/Shadow home. |
| Firstborn | TypeScript | 1.1 MB | 2026-11-01 | 25 | 8 | Holds `tools/transcribe/vtx.py`. Has a failing workflow. |
| Openhands | Shell | 201 KB | 2026-11-01 | 1 | 1 | Plugin/skills repo. |
| Amina | TypeScript | 165 MB | 2026-10-31 | 1 | 3 | Largest repo. |
| Mohsen | TypeScript | 480 KB | 2026-10-26 | 4 | 3 | |
| Mission-runner | HTML | 473 KB | 2026-10-25 | 2 | 4 | |
| smart-farm | Kotlin | 186 KB | 2026-10-25 | 0 | 4 | |
| Blind-sniper- | JavaScript | 1.3 MB | 2026-10-25 | 0 | 1 | |
| Foryra | HTML | 834 KB | 2026-10-25 | 0 | 1 | |
| Mr-baleegh | JavaScript | 137 KB | 2026-10-25 | 0 | 1 | Contains `Mazra3a-fixed (1).zip`. |
| Meshmesh- | HTML | 335 KB | 2026-10-25 | 0 | 1 | |
| brain-chat-log | TypeScript | 203 KB | 2026-10-25 | 0 | 1 | |
| Brand-building-skills | Shell | 155 KB | 2026-10-25 | 2 | 1 | A fork. |
| Meshmesh | HTML | 153 KB | 2026-10-25 | 0 | 1 | |
| Gah1 | TypeScript | 98 KB | 2026-10-25 | 0 | 1 | |
| Money-slave | TypeScript | 87 KB | 2026-10-25 | 0 | 1 | |
| Revenue-hunter | JavaScript | 9 KB | 2026-10-25 | 0 | 1 | |
| Brand-manager | JavaScript | 9 KB | 2026-10-25 | 0 | 1 | |

Every repo carries `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md` and an `engineering-execution-os-compliance.yml` workflow — a consistent house standard.

## What is broken (observed)

- **Firstborn** `Verification and Build Checks` run on `push` = **failure** (2026-11-01). First concrete break to investigate.
- **brain** has **20 open PRs** and **34 open issues**, many stale (mission/* branches from early October). Backlog, not a single fault.
- **GitHub Actions secrets API** is not reachable with the current token (403) — Shadow cannot write keys yet (see `/shadow/registry.md`).

## Backlog snapshot (brain)

- 20 open PRs; drafts include #239 (this work), #237, #218, #203, #196, #188, #186, #122.
- 34 open issues, dominated by "Brain verification <hash>" and credential-preflight tasks.

## Gaps

- No `.github/workflows/watcher-daily.yml` yet (Section 12.3).
- No working credential-write path (Actions secrets 403).
- Channels to ChatGPT/Forge, external OpenHands, YouTube/Facebook transcripts, and a design tool are UNTESTED.

## Next actions

1. `watcher-daily.yml` (Section 12.3).
2. Investigate the Firstborn failing workflow.
3. Resolve the Actions-secrets permission gap so Shadow can store keys.
