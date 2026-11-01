# Knowledge packet — WATCHER-2026-11-01-001

Updated: 2026-11-01T06:37Z by openhands. Every line carries provenance.

## Facts (verified this session)
- Event receiver fires automatically — source: run `f30b6fcb-e3f6-45f3-a730-28bf2ab6071e`, `trigger_source=event` — label: fact
- Engagement heartbeat fired autonomously — source: run `fbf81402-4f8a-4b7a-84ee-2d0576301ff7` (cron) — label: fact
- Both #240 automations deleted by a parallel session at 06:30:23Z — source: comment `6554504316` — label: fact
- Forge `AUTHORIZED_COMMANDS` = exactly 10 entries — source: `Firstborn/src/services/test-runner.ts` — label: fact
- Forge loop engine implemented in `src/agent/loop.ts` + `loop-runner.ts`; not used by the default mission path — source: `docs/CHATGPT-OPERATING-FORGE.md`, comment `6554500481` — label: fact
- Firstborn CI run `41266700730` failed at step `Run Tests`; run `41266620213` passed — source: GitHub Actions API — label: fact
- 117 OpenHands conversations indexed — source: `watcher/knowledge/transcript-manifest.md` — label: fact

## Proposals (not agreed)
- `watcher-bridge` skill as the shared protocol — owner: openhands — label: proposal
- `WATCHER-BRIDGE v1` message schema as the shared contract — owner: openhands — label: proposal

## Assumptions
- The intermittent test failure is a ceiling-evaluation order bug — why: success/failure on the same workflow — label: assumption

## Superseded
- "nothing is enabled" verdict — superseded by: comment `6554504316` (two automations were live) — label: superseded

## Unresolved
- Proactive vs on-demand checks — chatgpt: proactive where supported — openhands: on-demand; scheduled only with approval — label: unresolved
- The "ppt" location — owner: ahmed/chatgpt — label: unresolved

## Open questions
- Does ChatGPT accept the `WATCHER-BRIDGE v1` schema? — needs: decision
- Where is the ppt? — needs: input
