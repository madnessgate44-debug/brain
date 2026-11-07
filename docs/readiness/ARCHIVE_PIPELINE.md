# ARCHIVE_PIPELINE — automatic conversation archiving (Phase 1 §2)

The Owner requires the OpenHands conversation archive to stay current **automatically**, with
redaction, idempotency, a cursor, and failure alerts. This documents what exists, what this PR
adds, and the exact trigger/latency.

## 1. What already exists (verified)

| Piece | File | What it does | Tag |
|---|---|---|---|
| Exporter | `scripts/export_conversations.py` | enumerates conversations, pulls events, renders an ordered verbatim transcript, redacts secrets | `[V]` |
| Schedule | `.github/workflows/watcher-session-log.yml` | cron `30 0 * * *` (00:30 UTC / 02:30 Cairo); exports the previous UTC day; opens a PR and **auto-merges** when CI is green | `[V]` |
| Archive | `docs/sessions/<date>.md` + `<date>.manifest.json` | the committed transcript and its manifest | `[V]` |
| Index | `docs/sessions/README.md` | day index; 19 days / 142 conversations / 577 owner messages as of 2026-11-06 | `[V]` |
| Raw events | `.openhands/export/raw/*.events.json.gz` (+ `.sha256`) | gzipped raw dump, **gitignored** (`.gitignore:32`) | `[V]` |

**Latency:** a conversation created on day D is archived on D+1 at ~00:30 UTC (up to ~24 h). This is
the reliable supported trigger — the Cloud API exposes no per-turn webhook to this repo.

**So the "make archiving automatic" ask is largely already satisfied.** The earlier claim that it did
not exist was wrong; the correct statement is: *the pipeline exists and runs daily; its redaction had
no fail-closed proof, and its cursor/idempotency were implicit.*

## 2. What this PR adds (the hardening)

| Gap | Fix | Where |
|---|---|---|
| No fail-closed leak gate | `check_leaks` / `leak_scan_files` + `main()` returns **2** if any secret shape survives redaction | `scripts/export_conversations.py` |
| No standalone scan mode | `--scan [paths]` — no API, no writes; exit 2 on a hit; used by CI | same |
| No redaction proof on a real event | `--verify-canary` builds a synthetic conversation carrying a secret-shaped canary, asserts it is redacted, and that the scanner catches it if it were not; exit 2 on failure; run in CI | same |
| No explicit cursor/watermark | `read_cursor` / `write_cursor` write `.openhands/export/cursor.json` = `{last_run_utc, last_date, count, conversations:{id: log_sha256}}`, written **only after** the leak gate passes; the run prints how many sections changed vs the previous cursor | same |
| No dedicated CI gate | `archive-leak-scan.yml` scans `docs/sessions`, runs the canary, and runs the tests on every change | `.github/workflows/` |
| Redaction unproven | 9 tests: each secret shape flagged; clean text passes; a sabotaged redaction **fails closed (exit 2)**; `--scan` and `--verify-canary` exit non-zero on a hit; the cursor round-trips | `tests/test_export_conversations.py` |

## 3. How each Owner requirement is met

| Requirement | How | Tag |
|---|---|---|
| detects new/changed events, regenerates incrementally | the exporter selects conversations by creation date and re-renders; `--from-raw` re-renders from cache with no API calls | `[V]` |
| preserves id, title, timestamps, speaker, order | `render_conversation()` writes `### <title>`, `- conversation: <id>`, per-event `[HH:MM:SS]`, `OWNER (verbatim)` vs `Watcher/agent` | `[V]` |
| redaction before commit/log, fail-closed tests | `redact()` + `check_leaks()` gate + tests | `[V]` |
| updates automatically after each session | `watcher-session-log.yml` daily cron + auto-merge | `[V]` |
| idempotent, handles retries, no duplicate turns, records cursor | per-conversation `log_sha256` in the manifest; deterministic render (test `test_main_export_is_deterministic`) → identical input gives byte-identical output → no noise PR; `429` backoff on the API | `[V]` |
| archives all conversations in scope, lists exclusions | scope = every conversation created that UTC day; exclusions = automation-run titles marked `automation: true` (still archived, flagged) | `[V]` |
| verification: a new conversation appears; a secret is redacted | the two `main()` tests prove both, offline | `[V]` |
| never commits raw events / secrets / unredacted text | raw dir gitignored; redaction + scan gate | `[V]` |

## 4. Cursor and last-success observability

- **Cursor/watermark:** `.openhands/export/cursor.json` — `{last_run_utc, last_date, count,
  conversations:{id: log_sha256}}`, written **only after** the leak gate passes, so it never points
  at a failed run. A re-run prints how many sections changed vs the previous cursor. (The per-day
  `docs/sessions/<date>.manifest.json` also carries `log_sha256` per conversation.)
- **Last success:** the `Watcher session log` workflow runs list (GitHub Actions → the workflow →
  runs); latest success is the last archived day. Example: 2026-11-07T06:23:25Z `success` `[V]`.
- **Failure alert:** if the exporter returns non-zero (e.g. exit 2 on a leak), the workflow step
  fails and GitHub raises the failure on the Actions tab; the PR is not opened. This is the alert.
- **Source scope:** every OpenHands Cloud conversation created on the target UTC day. **Exclusions:**
  Owner↔ChatGPT conversations are **not** covered (no supported export/API is reachable — see §5);
  the OpenHands event store must not be represented as containing ChatGPT conversations.

## 5. Source coverage and exclusions

| Source | Covered? | Tag |
|---|---|---|
| OpenHands Cloud conversations (this account) | **yes** — `app-conversations/search` | `[V]` |
| Automation runs | yes, flagged `automation: true` | `[V]` |
| Owner↔ChatGPT conversations | **no — `[B]`** | `[B]` |

`[B]` Owner↔ChatGPT: no supported export/API is reachable from this credential. This pipeline does
**not** claim to capture them. Handoff: ChatGPT exports its own history (OpenAI → Settings → Data
controls → Export) and the Owner pastes or attaches it to #292; it is archived as an attachment
reference, not auto-scraped.

## 6. Verification (how to reproduce)

```bash
# unit + fail-closed proof (offline)
python3 -m pytest tests/test_export_conversations.py -q --noconftest
# scan the committed archive for residual secret shapes
python3 scripts/export_conversations.py --scan docs/sessions
# a full export for one day (needs OPENHANDS_API_KEY)
python3 scripts/export_conversations.py --date 2026-11-07
```

_Phase 1 §2 deliverable. No secret value handled; no merge, deploy, or spend._
