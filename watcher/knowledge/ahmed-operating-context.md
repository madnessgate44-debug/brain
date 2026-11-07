# Knowledge base — Ahmed's operating context

Ranked-plan task **#5**: "Build `/watcher/knowledge/` from Ahmed's history + ppt". Author:
Watcher (OpenHands session), 2026-11-01. Tags: [V] verified, [C] reported, [U] unknown,
[B] blocked.

## The "ppt"

**Not found.** [V] I searched the 18 repos in `madnessgate44-debug` (tree listings), the
`brain-chat-log` history, and OpenHands conversation titles. No presentation deck, `.pptx`,
slide outline, or document titled "ppt" exists in any of them. This is the same result ChatGPT
reported. The ppt remains **BLOCKED** pending a repo + path or a pasted outline from Ahmed or
ChatGPT. Nothing is invented in its place. [B]

## What Ahmed's history does establish (evidence-backed)

Source: `madnessgate44-debug/brain-chat-log`, `chat-log.md` and `README.md` (read via the GitHub
API this session). [V]

| fact | detail | evidence |
|---|---|---|
| System name | **Brain X** — "Universal Multi-Agent Autonomous Software Company" | `brain-chat-log/README.md` |
| Primary operator surface | **Android phone**, conversational dialogue with ChatGPT | `chat-log.md` Log Entry 002 |
| Browser engine | **Tamayim** — cloud Chromium, stealth, DOM click/fill, dual-viewport screenshots (mobile 390x844, desktop 1280x800) | `chat-log.md` Log Entry 003; `README.md` |
| LLM cost model | **100% zero-cost** keyless cascade: FreeLLMPool, Pollinations AI, LLM7, OVH Llama-3.3-70B, OpenRouter Free | `README.md`; `chat-log.md` Log Entry 003 |
| Merge gate | PR-B security fixes land **before** provider wiring | `chat-log.md` Log Entry 002 |
| Audited defects (PR-B) | 7: hook RCE, gitleaks tar crash on deleted files, silent aborts, `tr` mangling, whitespace crash, trigger suffix bypass, misleading test claims | `chat-log.md` Log Entry 001 |
| Forge identity | deterministic coding agent, GH Actions + local HTTP API, `TaskExecutionReport` | `Firstborn/README.md`; `src/types/agent.ts:72` |

## Reconciliation with WATCHER.md

- The **zero-cost mandate** in `README.md` and `chat-log.md` Log Entry 003 matches WATCHER.md
  §14 (free/keyless routes, no card). It is a hard constraint, not a preference. [V]
- The **phone-first** operating protocol is the design centre. It matches WATCHER.md §0
  ("best AI coding agent operable from a phone"). [V]
- The **Tamayim** engine maps to the browser worker already present in Brain
  (`brain/runtime/`, `docs/BRAIN_BROWSER_OPERATIONS.md`). [I]

## Gaps

- The ppt location: BLOCKED. [B]
- ChatGPT private chat history: no export path from this sandbox; not claimed. [U]
- OpenHands conversation history: enumerable via `app-conversations/search` (200) and readable
  per id via `conversation/{id}/events/search` (200); a full export is a separate, larger task. [V]
