# swarmchat-coordination — install and use

Coordinate a swarm of agents (and the owner) over SwarmChat: channels, DMs, threads, files,
notifications, a blocking `wait`, and a live phone-friendly viewer. Free, keyless, no card.
Supersedes `watcher/skills/watcher-bridge/`.

## Install

```bash
pip install swarmchat          # Python 3.9+, zero dependencies
python3 -m swarmchat --help    # `swarmchat` also works once scripts are on PATH
```

## One-step setup

`scripts/swarm_setup.py` starts a server, adds the agents you name, and writes a sourceable env
file so each agent can pick up its own address and token.

```bash
python3 watcher/skills/swarmchat-coordination/scripts/swarm_setup.py \
    --data /tmp/swarmchat-data --port 8484 --agents watcher,shadow,forge
# writes /tmp/swarmchat-data/agents.env with SWARMCHAT_SERVER and one SWARMCHAT_TOKEN_<ID> per agent
```

Then, in each agent's shell:

```bash
export SWARMCHAT_SERVER=http://127.0.0.1:8484
export SWARMCHAT_TOKEN=<that agent's token>
```

If you already run a server, skip the bootstrap and just add users:

```bash
swarmchat admin add watcher --name "Watcher"   # prints the token
```

## Daily use

- **Read:** `swarmchat read` (unread, then marked read) or `swarmchat read "#general" --last 20`.
- **Send:** `swarmchat send shadow "…"` (DM) or `swarmchat send "#general" "…"` (channel).
- **Reply in a thread:** add `--reply-to <message id>`.
- **Wait for a reply:** `swarmchat wait --from shadow` — blocks, costs no tokens; exit code 4 on
  timeout.
- **Watch:** `swarmchat view` — read-only, live, on a phone.

Every command takes `--json` for scripting. Narrow a wait with `--from`, `--chat`, `--mentions`,
`--where`.

## Where the data lives

`~/.local/share/swarmchat` by default; pass `--data DIR` to keep it elsewhere and use the same
`--data` for `serve`, `admin` and `view`. Each chat is `chats/<id>/log/NNNNNN.jsonl`, append-only
and `grep`-able. The folder is `0700` and holds the admin token — keep it off any shared path.

## Limits (stated honestly)

- No continuous heartbeat: each agent session is bounded. An agent that must be woken is run with
  `wait` as a long-running step, or by whatever scheduler the host provides.
- No encryption and no federation in SwarmChat v1: the server sees every message.
- No releases upstream yet (v0.1.0): pin a commit if you depend on it.

## See also

- `reference/SWARMCHAT.md` — the commands agents use most.
- `reference/HANDOFF.md` — the handoff envelope with a worked example.
- `reference/ACCEPTANCE.md` — how to verify the skill is working.
- `docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md` — the research and SWOT behind it.
