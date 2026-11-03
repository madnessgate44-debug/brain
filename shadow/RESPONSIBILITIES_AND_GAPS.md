# Shadow — responsibilities and gaps

What Shadow is *supposed* to be (WATCHER.md) versus what is actually implemented and running,
verified 2026-11-02.

> Shared weaknesses with Watcher are tracked in `watcher/knowledge/WEAKNESSES.md`. Read it
> before auditing: Shadow's own habit (report instead of build; self-diagnose then not close)
> is recorded there as W1 and W5. Closing a gap here means adding a check that fails until it
> is closed — not only writing the paragraph below.

## 1. The contract (WATCHER.md)

| § | Responsibility | Detail |
|---|---|---|
| 1 | Senior auditor and **counter** to Watcher | Cold on evidence, adversarial until proven wrong, mentor who explains each correction. When Watcher fails: (a) complete the task himself and log why Watcher failed, (b) write the fix and hand it back, (c) run a parallel attempt and keep the better result. |
| 3 | Schedule | Wakes on **every Watcher result** to approve/reject; **hourly sweep** from 07:00 as a backstop; reports to Ahmed at **09:00 and 21:00**. |
| 4.8 | Writes the end-of-day decision brief for Ahmed | Part of Watcher's daily cycle. |
| 5 | Audit rules | Quiet after an approval until the next result; a rejection always states the failure, the root cause, and the fix (never reject without a fix); parallel track only when a failure blocks Watcher or touches money/clients/irreversible; keeps the hourly sweep running on the parallel track. |
| 14.2 | Owns the replacement key/connector pool | Writes keys into each target repo's Actions secrets; pool kept in `registry.md` by **label only**; never reads or prints a value. |
| 14.4 | Key sweep every 6 hours | Test every registered key × model with a minimal real request; update status; never write values. |
| 14.5 | Delivery during conversations | Watches PRs, comments, pushes, and CI on every repo; posts the working solution when a key/connector blocker appears; any mid-conversation key failure is a Shadow failure. |
| 14.6 | Card rule | No service that needs a card is recommended or used; verify from the provider's own page. |
| 14.7 | Rotate the exposed Gemini key | Deferred by Ahmed until the build is complete. |
| 15 | Merge authority | Shadow and Watcher merge technical PRs themselves on green CI + a Verified Shadow audit. |

## 2. What is implemented (verified 2026-11-02)

| Component | Role | State |
|---|---|---|
| `shadow/shadow.py` | Single-shot auditor. Gathers live evidence (git state, hub tickets, live model probe, PR checks + full file contents, issue state), sends it to Gemini, returns VERDICT / FINDINGS / WEAKEST POINT / FIX, appends to `audit-log.md`. | **Works** — `generate()` returned a real reply; `live_evidence()` gathered real data. |
| `shadow/keypool.py` | Pool: `OHGeminiAPI` + `GEMINI_POOL_1..7` × 4 models, key-outermost rotation. Values from the environment only. | **Works** — 8/8 labels, 32 routes. |
| `shadow/registry.md` | §14.3 status table, labels only. | **Present**, populated. |
| `.github/workflows/shadow-keys.yml` | §14.4 key sweep, every 6 h, PASS/FAIL only. | **Running** — last success 2026-11-02T14:59Z. |

## 3. Gaps (verified)

| # | Gap | Evidence |
|---|---|---|
| G1 | **No scheduled audit.** Nothing invokes `shadow.py` on a schedule. §3/§5 ("Shadow wakes on each Watcher result") is manual only. | `grep` of `.github/workflows/` for `shadow.py` → none. |
| G2 | **The counter powers (a)/(b)/(c) are absent.** `shadow.py` only audits and logs; it cannot complete a task, write a fix, or run a parallel attempt. | Read of `shadow/shadow.py`. |
| G3 | **No 09:00 / 21:00 report to Ahmed.** | No workflow or code implements it. |
| G4 | **No hourly sweep** backstop; only the 6-hourly key sweep exists. | Workflow inventory. |
| G5 | **§14.2 secret write is DEAD.** `GET /repos/.../actions/secrets` returns 403 "Resource not accessible by integration", so Shadow cannot write keys into Actions secrets. | `shadow/keys-log-2026-11-01.md`; `registry.md` note. |
| G6 | **§14.5 watch/delivery is absent.** No process watches PRs/comments/pushes across repos or posts solutions to chat. | No such workflow or module. |
| G7 | **§14.7 rotation not done.** The exposed key is still in use. | `registry.md` notes. |

## 4. Verdict

Shadow today is a **working single-shot auditor plus a live key pool**. He is **not yet the
counter/operator** WATCHER.md §1 describes: he reviews on demand, but nothing schedules him, he
cannot fix or complete work, he sends no reports, and he cannot write the secrets he is meant to own.

Smallest path to close the gap, in order: (1) a scheduled workflow that runs `shadow.py` against each
Watcher result; (2) the 09:00/21:00 report job; (3) fix the 403 so §14.2 works; (4) only then the
counter powers, which are the largest change.
