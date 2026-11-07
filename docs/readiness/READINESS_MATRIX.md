# READINESS_MATRIX — Phase 1 (2026-11-07)

One row per participant × capability. Every cell is tagged: `[V]` verified by inspection this
session, `[U]` unproven, `[B]` blocked. Evidence is a path, a SHA, a run, or a comment id.
Read-only audit; no secret value is printed anywhere in this file.

Scope: ChatGPT, OpenHands, Forge, Shadow, Watcher, Brain runtime. Claude is removed
(Owner directive `6712932899`). Base commit: `1a9cffb7d3834159aeedea2a202ec4fb13b9f02a`.

## 1. Identity and access

| Participant | GitHub identity | Repo scope | Actions | Branch/PR | Issue/comment | Channel | Tag |
|---|---|---|---|---|---|---|---|
| OpenHands | `openhands <openhands@all-hands.dev>` (14/20 recent commits on `main`) | brain + the 5 products | read | yes (opens PRs, never pushes `main`) | yes | GitHub #292 + SwarmChat `openhands` | `[V]` |
| ChatGPT | owner's account `madnessgate44-debug` (all #292 comments authored by it) | via owner | none of its own | via owner | yes (as owner) | GitHub #292 | `[V]` |
| Forge | `app/github-actions` bot on archive PRs; `forge` in SwarmChat | `Firstborn` + target repos | via `forge.yml` | yes (PRs) | via workflows | GitHub + SwarmChat `forge` | `[V]`/`[U]` |
| Shadow | `madnessgate44-debug` (audit comments) | brain `/shadow/` | via `shadow-*.yml` | audit only | yes (audit comment) | GitHub #292 | `[V]` |
| Watcher | `watcher-bot` (archive PRs `#284/#288`); `watcher` in SwarmChat | brain `docs/sessions`, `watcher/` | via `watcher-*.yml` | yes (PRs) | yes | GitHub + SwarmChat `watcher` | `[V]` |
| Brain runtime | runs as `openhands` executor inside `brain/company/` | brain | via workflows | yes | yes | inherits OpenHands | `[V]` |

`docs/LOOP.md:6` grants Shadow and Watcher the merge right. The Owner directive reassigns Shadow to
adversarial review and makes OpenHands the execution lead — the merge right is a C2 conflict (see
`BLOCKER_REGISTER.md`).

## 2. Model / API routes (names and consumers only — never values)

| Consumer | Provider | Secret name(s) | Where configured | Tag |
|---|---|---|---|---|
| Brain build / chat / R&D | OpenAI-compatible (DeepSeek/OpenRouter) | `BRAIN_AI_API_KEY`, `BRAIN_AI_BASE_URL` | repo Actions secrets | `[V]` name; `[U]` value |
| Brain R&D discovery | GitHub | `BRAIN_RD_GITHUB_TOKEN`, `BRAIN_GITHUB_TOKEN` | repo Actions secrets | `[V]` name; `[U]` value |
| Shadow auditor | Google Gemini pool | `OHGeminiAPI`, `GEMINI_POOL_1..7` | repo Actions secrets | `[B]` — absent, see §4 |
| OpenHands automations | OpenHands Cloud | `OPENHANDS_API_KEY` | repo Actions secrets | `[V]` name; `[U]` value |
| All workflows | GitHub | `GITHUB_TOKEN` (built-in) | Actions | `[V]` |

The secret *names* were read from the workflow YAML (grep). I could **not** list which secrets exist
as repository secrets: `GET /repos/{o}/{r}/actions/secrets` returned **403** for this token
(`Resource not accessible by integration`) `[V]`. Presence is therefore `[U]` for every row except
Shadow's, which the Shadow workflow itself reports BLOCKED (`6709749058`) — so its pool is `[B]`.

## 3. Skills and tools

Skill router (`python3 scripts/skills.py declaration "<task>"`) `[V]`:

| Task | Top matches (score) |
|---|---|
| audit + research + engineering + QA + security + browser | `security (9)`, `security_auditor (4)`, `improve-agent-readiness (4)`, `accessibility-audit (4)`, `security-threat-model (4)` |
| adversarial security audit of a PR | `security (9)`, `code-review-rubric (8)`, `multi-session-pr-coordination (5)`, `security_auditor (4)` |
| product development research + revenue | `multi-session-pr-coordination (5)`, `product_owner (4)`, `research-brief (3)`, `prd (2)` |

Installed skills `[V]`:
- `.agents/skills/writing-for-agents` (1)
- `brain/company/skills/*.md` (9): architect, code_reviewer, customer_advocate, developer,
  product_owner, qa_engineer, release_manager, security_auditor, ux_designer
- `watcher/skills/` (3): swarmchat-coordination, watcher-learning, watcher-reverse-engineering

Gaps `[U]`: no dedicated `browser-qa` skill in brain (Forreyra exists in `Firstborn`); no
`accessibility-audit` skill file despite the router naming it (router keyword match, not installed).
Do not describe a skill as installed when only the router matched it.

## 4. Prompts and operating instructions

| Participant | Prompt / instruction file | Tag |
|---|---|---|
| all | `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md` (controlling), `WATCHER.md`, `docs/WORKFLOW.md`, `docs/LOOP.md`, `docs/TICKETING_PROTOCOL.md` | `[V]` |
| Brain runtime | `brain/company/roles.py` (ROLE_CATALOG), `brain/company/skills/*.md`, `docs/SESSION_LOOP_TASK.md` | `[V]` |
| Shadow | `shadow/RESPONSIBILITIES_AND_GAPS.md`, `WATCHER.md §5 §14` | `[V]` |
| Watcher | `WATCHER.md` §0–§16 | `[V]` |

Contradictions: see `BLOCKER_REGISTER.md` C1–C5.

## 5. Research capability

| Agent | Can browse / search / fetch? | Evidence | Tag |
|---|---|---|---|
| Brain runtime | **no** by default — the deterministic document worker does not do web research | Owner directive states it; re-verify against the worker code in Phase 2 | `[U]` |
| Brain (workflows) | **yes** via `brain-browser-research-issue.yml` and `brain-rd-discovery.yml` (free-first web research) | workflow present, runs active | `[V]` |
| OpenHands (this session) | **yes** — Tavily search/extract/crawl + headless browser | used this session | `[V]` |
| Forge | **yes** — Forreyra drives a real Chromium (`Firstborn/FORREYRA.md`) | file present | `[V]` |
| ChatGPT | yes (its own tooling) | not observable from here | `[U]` |

## 6. Coordination and persistence

| Channel | Durable? | Evidence | Tag |
|---|---|---|---|
| GitHub #292 | **durable** | survives sessions; the report channel | `[V]` |
| SwarmChat `#general/#audits/#reports/#alerts` | **not durable** — sandbox-local; dies on reset | `.swarmchat/`, server at `127.0.0.1:12000` | `[V]` |
| Claude inbox | removed from the workflow | Owner directive `6712932899` | `[V]` |

Agent-to-agent **wake/trigger**: none wired `[U]`. SwarmChat `wait` long-poll could wake a
participant but nothing uses it. GitHub `issue_comment` workflows only fire on exact owner phrases
(`/brain test`, `/brain retry`) — verified by the `skipped` runs on every comment this session `[V]`.

## 7. Watcher service coverage

Watcher's daily workflow is **enabled and running** — `watcher-daily.yml:9` cron `0 4 * * *`, last
five runs `success` (latest 2026-11-07T10:54:52Z) `[V]`. The file header says "DISABLED on creation"
but that comment is stale; the workflow state is `active`. What Watcher does **not** yet do: the
Phase-1 readiness checks above (its daily cycle is the audit/report cycle). Per `WATCHER.md §6`,
Shadow owns credential pool operations; Watcher coordinates service.

| Missing requirement | Owner | Remediation | Status |
|---|---|---|---|
| Shadow pool secrets absent | Shadow / Owner | add `OHGeminiAPI` + `GEMINI_POOL_1..7` to Actions secrets | `[B]` — needs approval |
| Repo-secret inventory | Owner (token scope) | token needs `secrets:read`, or a human lists them | `[B]` — 403 |
| Brain web-research proof | OpenHands | test the R&D/browser workflow on a live issue | `[U]` |
| Agent wake/trigger | Owner decision | adopt SwarmChat `wait` or a GitHub dispatch bus | `[U]` |

## 8. Can the internal system do the job? (the gate)

| Capability the directive requires | Who | Ready? |
|---|---|---|
| Inspect (read repo state, runs, files) | OpenHands, Watcher | **yes** `[V]` |
| Research (browse, cite) | OpenHands, Forge, brain workflows | **yes** `[V]` |
| Plan (specs, acceptance) | ChatGPT + OpenHands | **yes** `[V]` |
| Execute bounded repairs | OpenHands, Forge | **yes** `[V]` |
| Independent review | Shadow | **partly** — audit runs but BLOCKED without its model `[B]` |
| Verify + report | OpenHands, Watcher | **yes** `[V]` |

**Gate result:** 5 of 6 capabilities ready. The single blocker is Shadow's model route (§2). The
Amina proving exercise can start once the Owner either supplies Shadow's pool or explicitly accepts
Shadow-blocked and names OpenHands as the verifier for that exercise.

_Phase 1 deliverable 1 of 4. Read-only; no secret value, merge, deploy, or spend._
