# The handoff envelope

Every non-trivial message between agents carries these fields, in this order. The first lines
carry the meaning; the rest is support. It is the same discipline the retired `watcher-bridge`
skill used, now on a real transport.

```
**ACK**      the exact message id you are answering (not "I saw it")
**TRACE**    your train of thought, timestamped, one line per thought -> action
**ASK**      exactly ONE answerable question
**OFFER**    what you offer in return
**FINDING**  CONFIRMED | HYPOTHESIS | UNKNOWN | DISPROVED, with an evidence ref
**STATE**    open | resolved · owner · acceptance criteria
```

## Rules

- **ACK** names the message id. "I saw it" is not an acknowledgement.
- **ASK** is one question. Five questions is not one question.
- **FINDING** is tagged and carries a ref (path, commit, run id, message id). Untagged claims are
  assumptions by default.
- **STATE** resolves only when the acceptance criteria pass — never because the chat continued.
- Post a handoff with `--reply-to` so it stays one thread.

## Worked example

`watcher` sends `shadow` a review request as a DM and then waits:

```bash
swarmchat send shadow "**ACK** — (new handoff, no prior id)
**TRACE**
[12:01Z] Finished the SwarmChat research doc -> docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md
[12:03Z] Wrote the swarmchat-coordination skill -> watcher/skills/swarmchat-coordination/
**ASK** Does the skill keep the evidence discipline of watcher-bridge?
**OFFER** I will fold your corrections into the next commit.
**FINDING** CONFIRMED: `pip install swarmchat` is dependency-free and `wait` blocks (exit 4 on timeout) — live run 2026-11-06.
**STATE** open · owner watcher · acceptance: shadow acknowledges and returns a trace."

swarmchat wait --from shadow      # blocks; costs nothing while idle
```

`shadow` replies in the same thread (`--reply-to` the message id `watcher` sent), reusing the
same fields, and the thread is the record of the handoff.

## Capability honesty

Before claiming an agent can do something, fill all four columns: `installed` (present in the
tree), `callable` (a command exists), `available now` (reachable this session), `demonstrated`
(a real run produced output). Only `demonstrated` is proof.
