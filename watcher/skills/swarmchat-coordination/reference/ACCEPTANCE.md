# Acceptance — how to know this skill works

Run these against a throwaway server. Every step has an expected result; if any fails, the skill
is not in force.

1. **Install is free and keyless.** `pip install swarmchat` succeeds with no key and no card.
2. **The server boots.** `swarmchat serve --data DIR --port PORT` prints "0 users, 0 chats …" and
   answers HTTP on that port.
3. **Two identities exist.** `admin add watcher` and `admin add shadow` each print a distinct token.
4. **A channel carries a message.** `send "#general" "…"` prints a message id; `read "#general"`
   shows it.
5. **The wait blocks and wakes.** Background `wait --from watcher` as `shadow`; send as `watcher`;
   the wait prints the message and exits `0`.
6. **The wait times out honestly.** `wait --timeout 2` exits `4` when nothing arrives.
7. **JSON is scriptable.** `chats --json` prints one JSON object per line.
8. **A handoff is one thread.** A reply with `--reply-to MSG` appears in the same thread
   (`read --thread MSG`).
9. **The viewer only looks.** `swarmchat view` serves a page; its token cannot send or move a read
   position.

## Verified here (2026-11-06)

Steps 1–7 and 9 were run live against `swarmchat` 0.1.0; see §7 of
`docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md` for the exact commands and results.
Step 8 is exercised by `scripts/swarm_setup.py --demo`.
