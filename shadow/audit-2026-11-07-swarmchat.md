# Shadow audit — SwarmChat bus (PR #289)

Auditor: OpenHands agent (Shadow role), on behalf of the owner.
Scope: PR #289, `research/swarmchat-coordination` → `main`.
Rule applied: `docs/LOOP.md` owner grant — merge when CI is green and this audit returns Verified.

## What the PR changes

| File | Change |
|---|---|
| `docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md` | Research + SWOT + install + reverse-engineering for SwarmChat. Docs only. |
| `watcher/knowledge/video/2026-11-06-swarmchat-launch.{txt,md,fr.md,article.txt}` | Transcript, notes, French summary, extracted article. Docs only. |
| `watcher/skills/swarmchat-coordination/**` | New skill (SKILL.md, README, 3 reference docs, `scripts/swarm_setup.py`). |
| `watcher/bridge/SUPERSEDED.md` | Marks the homemade bridge superseded. Docs only. |
| `tests/test_swarmchat_skill.py` | Regression test; real server, `pytest.importorskip("swarmchat")`. |
| `.openhands/memory/MEMORY.md` | Mission 22 entry. |

## Checks

- **Technical only:** yes — research, docs, a skill, a test, and a memory note. No spend, no goal
  change, no secrets. `swarm_setup.py` writes agent tokens to a local file mode `0600` and never
  prints them; the test creates its own server in a temp dir.
- **CI on head `df2e06b`:** `Check execution policy files` ×2, `python-tests`, `tests (3.12)`,
  `tests (3.13)`, `chromium-smoke`, `Vercel Preview Comments` — all **success**.
- **Mergeability:** `mergeable: true`, `mergeable_state: clean`, 0 commits behind `main`.
- **Live behaviour confirmed:** `python3 -m swarmchat serve` boots; `admin add` issues one token
  per agent; `swarmchat wait` is a server-side long poll that blocks then returns (exit `0`), and
  `wait --timeout 2` returns exit `4`; `--json` emits one JSON object per line.
- **Test run:** `python3 -m pytest tests/test_swarmchat_skill.py -q` → 2 passed.

## Verdict

**Verified.** Merge as a merge commit (the repo's established style).

## Deferred in the same review

- **#283 (ARTEMIS)** — already merged to `main` as `9dbdd23`; content identical. Nothing to do.
- **#272, #243, #242, #196, #183, #145, #122, #121, #4** — see `audit-2026-11-07.md`. Left deferred
  on purpose (superseded, or colliding with merged work, or 130–250 commits behind). Resurrecting
  stale branches is an owner decision, not a mechanical rebase.
