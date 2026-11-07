# Watcher knowledge base — index and sourced facts (issue #240)

Date: 2026-11-01. Author: Watcher (OpenHands session). Every fact below carries a source and an
evidence tag: [V] verified this session, [C] reported by another party, [I] inference, [U] unknown.

## Sources (indexed)

| # | source | location | what it is |
|---|---|---|---|
| S1 | `WATCHER.md` v1.1 | brain @ main | constitution; §0 mission, §14 credentials, §15 standing approval |
| S2 | `brain-chat-log/chat-log.md` | repo `brain-chat-log` @ main | Ahmed's operating history (28 lines, 3 entries) [V] |
| S3 | `Firstborn` repo tree | `madnessgate44-debug/Firstborn` @ `36a9916e` | 120 files; the Forge agent [V] |
| S4 | issue #240 comment thread | brain issue #240 | 32 comments as of 06:11Z; the ChatGPT↔Watcher handshake [V] |
| S5 | OpenHands conversation list | `GET /api/v1/app-conversations/search` | 100+ sessions; tagged with `automationid`/`automationrunid` [V] |
| S6 | `watcher/channel/status-2026-11-01.md` | this repo | authoritative channel state |
| S7 | `watcher/reports/forge-parity-reinspection-2026-11-01.md` | this repo | Forge vs Claude Code, row by row |

`watcher/knowledge/README.md` already states the folder's purpose ("video transcripts and insights");
this index is the entry point that ties the sources together. A parallel session's PR #243 carries a
longer `transcript-manifest.md` and `BASE.md`; those are complementary, not superseded.

## The mission (S1 §0) [V]

Make Forge the best AI coding agent operable from a phone, surpassing Codex and Claude Code, through
a continuous self-improving loop across tools, conversations, video knowledge, and reverse-engineered
public work. Whatever Watcher improves in Forge, he improves in himself.

## Cast (S1 §1–2) [V]

- **Watcher** (white): operator — researches, builds, proposes, reports.
- **Shadow** (black): independent auditor and counter; on failure, completes the task, writes the fix,
  and can run a parallel attempt keeping the better result.
- **Ahmed**: the only human; one vote; receives one-line decisions.
- **Customers**: Forge (primary executor, reached via ChatGPT), ChatGPT (command center, source of
  conversation history), OpenHands (parallel executor), Ahmed (decides).

## Operating protocol (S2, S1 §3–4) [V]

- Ahmed operates from an **Android phone** through conversational dialogue. Phone-first is a design
  constraint, not a convenience. [V]
- Daily cycle (S1 §4): review logs → scan sources → research → transcribe video → publish the day's
  plan for Shadow approval → execute → log customer responses → end-of-day summary. [V]
- Shadow reports to Ahmed at 09:00 and 21:00 whether or not anything happened. [V]

## Zero cost (S1 §14.6, S2) [V]

No card. Keyless/free LLM cascade: FreeLLMPool, Pollinations, LLM7, OVH Llama-3.3-70B, OpenRouter
Free. Fall over on 429/502 without paying. Any paid path is a hard gate requiring Ahmed's explicit
approval. **This is why the channel automations are disabled** — their spend model is unverified
(see S6 §2 and `shadow/audit-2026-11-01-channel-remediation.md`). [V]/[U]

## Forge identity and architecture (S3, S7) [V]

- **Forge = `madnessgate44-debug/Firstborn`, branch `main`.** README §1: "Forge is the deterministic
  coding agent for the Firstborn project." HEAD verified `36a9916e900f9019ef1c46d95d08985c38fbac9d`. [V]
- Two interfaces: a GitHub Actions workflow (`forge.yml`) and a local HTTP API (`server.ts`,
  `POST /api/tasks/run`). Returns a `TaskExecutionReport`. [V]
- Engine: `src/kernel/loop.ts` — bounded loop (maxSteps 12, maxRuntime 10 min, maxCall 2 min),
  symlink-aware workspace containment, optional completion verifier. [V]
- Tools (`src/agent/tools.ts`): list/read/search/find/think/fetch_url + edit/write/run_check +
  9 browser tools (browser tools only when `allowBrowser`). [V]
- Company: role roster run **sequentially** (`src/company/team.ts:68`), budget `maxRoleRuns=40`. [V]
- Command execution is a **fixed registry of 11 commands** (`src/services/test-runner.ts:15`); no
  arbitrary shell. This is the largest measurable Claude-Code parity gap. [V]

## Brain X (S2, 2026-10-11) [V]

- Promoted to "Brain X" with universal GitHub administrative authority. [C]
- **Tamayim** browser engine: cloud Chromium, stealth anti-bot, DOM form/click workflows, mobile
  390x844 and desktop 1280x800 screenshot verification. [C]
- **Merge gate**: PR-B security fixes must land and be validated before provider wiring. Seven
  audited defects: hook RCE, gitleaks tar crash on deleted files, silent aborts, `tr` mangling,
  whitespace crash, trigger suffix bypass, misleading test claims. [C]

## Open questions [U]

- **The "ppt" of Ahmed's prior work**: not found. Searched all 18 repos for `*.pptx` (0 results),
  all conversation titles (0), and the local tree (0). [V]/[U] — need repo + path or the outline.
- Whether a second, non-GitHub history export exists. [U]

— Watcher (via OpenHands). This index was created by an AI agent on behalf of the repository owner.
