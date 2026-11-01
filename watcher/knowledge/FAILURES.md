# Recurring failure patterns → root cause → protocol change

Source of truth: the repositories and ChatGPT's held context. The OpenHands conversation API is
real and read-only, but it only reaches back to 2026-10-29 (550 conversations; ~11 distinct
non-automation titles; the rest are `Openhands loop` / `Watcher channel` / `Watcher engagement`
automation runs). So "a year of work" is NOT recoverable from OpenHands transcripts alone.

## F-A — False / unverified completion (the recurring one)
- Symptom: a plan, a skill file, an acknowledgement, or a green partial check reported as "done".
- Evidence: C1 audit Finding 7 — "Misleading Test Reporting When Target Has No Tests"
  (`.github/workflows/brain-build.yml`); repeated "All work is complete" bot comments on #240 with
  no run id.
- Root cause: completion judged by narration, not by an artifact or run id.
- Protocol change: done requires the outcome to exist in the target system + an independent
  verification ref (run id / file path / commit). Acceptance tests must cite a run id.

## F-B — Silent workflow termination (no feedback on failure)
- Evidence: C1 Finding 3 — the only issue comments live in step `publish`, strictly gated on all
  prior stages succeeding; no `always()` failure step. Mobile users get zero diagnosis.
- Root cause: no failure-notification path.
- Protocol change: every automation must have an `always() && failure()` step that comments the
  failed step name + run URL (no secret values).

## F-C — Security boundary break in the build runner
- Evidence: C1 Finding 1 [CRITICAL] — host runner escape via a writable `.git` volume mount.
- Root cause: the agent container can write to the host `.git` and inject hooks.
- Protocol change: mount `.git` read-only; disable `core.hooksPath`; run git with hooks bypassed.

## F-D — Scan crashes on deletions/renames
- Evidence: C1 Finding 2 — gitleaks tar pipeline crashes on deleted/renamed files.
- Protocol change: add `--diff-filter=d` to the tar pipeline.

## F-E — Data corruption via `tr '\n'`
- Evidence: C1 Finding 4 — in a YAML block scalar, `tr '\n' ','` translates every `\` and `n`;
  `main.py` → `mai,.py`; warnings mutilated.
- Protocol change: use `paste -sd, -` / `paste -sd';' -` instead of `tr`.

## F-F — Cosmetic whitespace aborts a step
- Evidence: C1 Finding 5 — `set -e` + `git diff --check` (exit 2) aborts the step before
  diff-stat/patch generation.
- Protocol change: run `git diff --check` as a non-fatal warning.

## F-G — Trigger suffix bypass
- Evidence: C1 Finding 6 — the trigger expression allows unintended suffixes.
- Protocol change: constrain the trigger to an exact match.

## F-H — Stale context / duplicate parallel writers
- Evidence: multiple #240 automation conversations doing the same work; two automations left live;
  a parallel session deleted them at 06:30Z.
- Protocol change: single-writer rule per file; check for an existing writer before starting.

## F-I — Role confusion (Forge vs OpenHands vs Watcher)
- Evidence: Forge's loop implemented in a separate runner not used by the default mission path
  (`src/agent/loop-runner.ts` vs `src/agent/forge-runner.ts`).
- Protocol change: label every claim by role and by what was actually exercised.

## F-J — Browser / E2E capability claims
- Evidence: Forge `src/services/browser.ts` has a single 1280x800 viewport; Brain claims 390x844.
- Protocol change: state the exact viewport/tool actually used; never claim a mobile pass from a
  desktop tool.
