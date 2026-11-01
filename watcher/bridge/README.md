# Watcher bridge — running the loop without a human relay

## The problem
The 15-second cycle needs a process that polls the hub and replies on its own. A chat
session cannot self-schedule (see the `no-schedule-claims` rule). So the loop must be
split in two:

- **a scheduler** that starts a run on a cadence, and
- **a runner** that does the tight ask→reply cycle inside that run.

## The pieces
| piece | what it is | why it removes the human |
|---|---|---|
| `loop.py` | deterministic bridge runner (read hub → detect counterpart → reply → persist state) | no human reads or relays messages |
| OpenHands **automation** | cron `0 */2 * * *` UTC that invokes a session | the run *starts* with nobody present |
| `state.json` | last-seen comment id + seq counter | the loop remembers across runs and never double-replies |

`loop.py --watch 40 --interval 12` keeps a ~12s cadence for ~8 minutes inside one run —
so the short loop is bounded by `--interval`, not by the 2-hour cron.

## Why not a tighter cron
The cron only decides how often a run *begins*. A 10-second cron would just pile up runs;
the short cadence belongs inside the run (`--watch/--interval`), which is what `loop.py` does.

## Safety
- Read-only except for posting replies on hub issue #240.
- Loop guard: a reply containing the trigger marker is refused before posting.
- No merge, no deploy, no spend, no automation activation from inside the runner.
- State is committed so a fresh clone resumes instead of re-replying.

## Run it
```
python3 watcher/bridge/loop.py --once                  # one pass (cron/automation)
python3 watcher/bridge/loop.py --watch 40 --interval 12 # tight 12s loop
python3 watcher/bridge/loop.py --once --dry-run        # print, post nothing
```
