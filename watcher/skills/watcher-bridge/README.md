# watcher-bridge — install and use

A portable protocol so ChatGPT and OpenHands/Watcher exchange knowledge and interrogate Forge
together, with evidence over claims. Co-designed 2026-11-01.

## Install in a ChatGPT project

1. Open the ChatGPT project.
2. Add a project instruction / knowledge file and paste the contents of `SKILL.md`.
3. Optionally paste `reference/KNOWLEDGE_PACKET.md` and `reference/FORGE_INTERROGATION.md` as
   additional project knowledge.
4. No secret is required. The bridge works entirely through the shared GitHub issue thread.

## Install on the OpenHands side

The skill lives in this repository. The runner is ready to use:

```
python3 watcher/skills/watcher-bridge/scripts/checkin.py            # print a WATCHER-BRIDGE v1 message
python3 watcher/skills/watcher-bridge/scripts/checkin.py --post     # post it to the coordination issue
```

It reads the coordination issue and open PRs, then emits a schema message from live state. It is
read-only unless `--post` is given.

## Daily use

- **Check-in:** send a `WATCHER-BRIDGE v1` message. Reply with the same schema.
- **Reconcile:** when the two pictures disagree, post both, mark the superseded line, keep one packet.
- **Catch-up:** summarise only what changed since a timestamp, labelling each trigger
  `manual|event|scheduled|unavailable` with its run id.
- **Forge interrogation:** walk one row of `reference/FORGE_INTERROGATION.md` per session; record a
  status and an evidence ref.

## Where the living documents live

- `watcher/knowledge/PACKET.md` — the reconciled knowledge packet.
- `watcher/knowledge/DECISIONS.md` — the append-only decision log.

## Limits (stated honestly)

- No continuous heartbeat. Each OpenHands session is bounded.
- Scheduled check-ins need an automation run and Ahmed's approval; the rejected GitHub-event
  receiver is not re-enabled.
- Read-only by default. No merges, deployments, secrets, or paid actions.
