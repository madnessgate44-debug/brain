# Watcher knowledge base — first pass

Grounded in: `WATCHER.md` v1.1 (brain), `brain-chat-log/chat-log.md`, the Firstborn repo tree, and
the 117-conversation OpenHands transcript manifest (`watcher/knowledge/transcript-manifest.md`).
Everything here is sourced; anything not verified is marked UNKNOWN.

## 1. The mission (WATCHER.md §0)
Make Forge the best AI coding agent operable from a phone, surpassing Codex and Claude Code,
through a continuous self-improving loop across tools, conversations, video knowledge, and
reverse-engineered public work. Whatever Watcher improves in Forge, he improves in himself.

## 2. Cast (WATCHER.md §1–2)
- Watcher (white): operator. Researches, builds, proposes, reports.
- Shadow (black): independent auditor and counter. On failure Shadow completes the task, writes
  the fix, and hands it back; can run a parallel attempt and keep the better result.
- Ahmed: the only human. One vote. Receives one-line decisions.
- Customers: Forge (primary executor, reached via ChatGPT), ChatGPT (command center, source of
  conversation history), OpenHands (parallel executor), Ahmed (decides).

## 3. Operating protocol
- Ahmed operates from an **Android phone** through conversational dialogue (`chat-log.md`).
  Phone-first is a design constraint, not a convenience.
- Schedule (WATCHER.md §3): 06:00 Watcher cycle; Shadow audits each result; hourly sweeps; Shadow
  reports to Ahmed at 09:00 and 21:00.
- Daily cycle (WATCHER.md §4): review logs → scan sources → research → transcribe video → publish
  the day's plan for Shadow approval → execute → log customer responses → end-of-day summary.

## 4. Zero cost (WATCHER.md §14.6, chat-log)
No card. Keyless/free LLM cascade: FreeLLMPool, Pollinations, LLM7, OVH Llama-3.3-70B,
OpenRouter Free. Fall over on 429/502 without paying. Any paid path is a hard gate requiring
Ahmed's explicit approval.

## 5. Forge (madnessgate44-debug/Firstborn)
- README: a deterministic coding agent driven by a supervising controller over two stable
  interfaces — a GitHub Actions workflow and a local HTTP API. Returns a `TaskExecutionReport`
  with a requirements matrix, raw test results, and honest blockers. Never rewrites architecture,
  touches secrets, or changes unrelated files.
- `src/kernel/loop.ts`: bounded hardened agent loop + workspace-safe tool registry. Hardening:
  per-call deadline, optional completion verifier (finish ≠ success), symlink-aware containment.
- `src/agent/forge-runner.ts`: CLI runner, bounded self-recovery (retry only when Forge's own
  diagnosis says retryable).
- `src/company/team.ts`: ordered roster; each role runs the loop with its own mandate/tools and
  posts a typed artifact to a shared bus; later roles read earlier artifacts (explicit handoff).
- 120 files: 43 `src`, 33 `tests`, 9 `scripts`, 8 `docs`, 8 `.github`, 4 `tools`.

## 6. Brain X (chat-log.md, 2026-10-11)
- Promoted to "Brain X" with universal GitHub administrative authority.
- Tamayim browser engine: cloud Chromium, stealth anti-bot, DOM form/click workflows, mobile
  390x844 and desktop 1280x800 screenshot verification.
- Merge gate: PR-B security fixes must land and be validated before provider wiring. Seven audited
  defects: hook RCE, gitleaks tar crash on deleted files, silent aborts, `tr` mangling, whitespace
  crash, trigger suffix bypass, misleading test claims.

## 7. Channel state (verified 2026-11-01)
- Two GitHub→OpenHands receivers: the `@openhands` / `@openhands-ai` App (auto-spawns sessions)
  and event automation `017c4b55-8904-47b0-863e-a36ca4df406a` (`trigger_source=event` proven).
- Engagement heartbeat `c2521706-7a97-4d64-b191-0b29ddc10682`, cron `*/20 * * * *`.

## 8. Open questions (UNKNOWN)
- The "ppt" of Ahmed's prior work: not found in any of the 18 repos or conversation titles.
- Whether a second, non-GitHub history export exists.
