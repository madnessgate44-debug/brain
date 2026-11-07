# ARTEMIS — "let an AI coding agent control your phone" — research + SWOT

- **Date:** 2026-11-06
- **Trigger:** Facebook reel `https://www.facebook.com/share/r/19mVcPn8wa/`
  (video id `1421050626342423`, uploader "The Prince Osa", 25.9s, Egyptian Arabic).
- **Question from the owner:** what is this tool, run a SWOT, and how do I get it
  on my phone / with an OpenHands-style agent.
- **Evidence rule:** every claim is tagged Verified / Observed-not-verified /
  Hypothesis / Blocked. Nothing is claimed as run unless it was run.

## 1. The video, in French (as asked)

Transcript source: local faster-whisper ASR of the reel audio (no captions exist
for this reel), produced by the repo tool `watcher/knowledge/tools/transcribe.py`.
The audio is Egyptian Arabic. The French below is a translation of the ASR.

> **Google a sorti un outil gratuit.** Il permet à Claude Code de piloter un vrai
> téléphone Android. Tu le regardes travailler : il ouvre les applis, fait défiler
> les écrans, change les réglages, et te renvoie le résultat. Il s'appelle
> **ARTEMIS**. Il a **15 000 étoiles sur GitHub** et Google dit que son taux de
> réussite dépasse **99 %**. Tu le branches sur ton téléphone et tu lui confies les
> tâches pénibles du quotidien. Il embarque un **serveur MCP**, donc il s'intègre
> directement dans Claude Code et Codex. Et tout est **open source**.

Note: "15 000 étoiles" is slightly stale — the repo is at ~16.7k stars today.

## 2. What it actually is (Verified)

| Fact | Value | Source |
|---|---|---|
| Repo | `google/artemis` | GitHub API |
| Description | "ARTEMIS turns natural-language instructions into reliable Android automation… integrates seamlessly with AI coding assistants such as Antigravity, Codex, and Claude Code. It also achieves 99%+ success rate on AndroidWorld Benchmark." | GitHub API |
| Stars / forks | **16,711** / 1,845 | GitHub API 2026-11-06 |
| Created | 2026-08-13 | GitHub API |
| Last push | 2026-10-01 | GitHub API |
| Language | Python (requires **3.12+**) | pyproject.toml |
| License | **Apache-2.0** | GitHub API |
| Releases | none published (source install only) | GitHub API |
| On-device | installs a small **"Artemis Accessibility Helper"** service; removable | README |

It is a **mobile test-automation agent**, not a consumer phone app. It drives a
real Android device (USB debugging on, or an emulator) with ADB + scrcpy, and it
exposes itself two ways:

1. **MCP server** — so Claude Code / Codex / Antigravity / Cursor / Windsurf can
   call tools such as `mobile_run_task`, `mobile_get_device_state`,
   `mobile_diagnose`, and pull Logcat + screenshots.
2. **CLI / Web console / Python SDK** — `uv run artemis run "…"` or
   `http://localhost:8000` for live screen mirroring and replays.

Two execution profiles: **Flash** (~3–5 s/step, fast reactive loop) and
**Pro** (~15–40 s/step, planner + operator + checker with a safety net).

## 3. The "SWAT" analysis (SWOT)

The owner asked for a "SWAT" analysis; interpreted as **SWOT** (Strengths,
Weaknesses, Opportunities, Threats).

### Strengths
- **Google-backed, Apache-2.0, genuinely open** — `google/artemis`, free, no card.
- **Real state-of-the-art claim:** 99%+ on Google Research's **AndroidWorld**
  benchmark (100+ multi-step tasks, 20+ apps) — and the video's "99%" matches it.
- **Native MCP** — drops into Claude Code / Codex / Antigravity / Cursor /
  Windsurf with one `artemis mcp --install all`. This is the same integration
  surface OpenHands agents already speak.
- **Handles custom UIs** — accessibility tree + OCR + visual models for Canvas /
  Compose / Flutter; "dynamic-first, coordinate-fallback" locating.
- **Traceability** — screenshots, Logcat, execution replays, structured reports.

### Weaknesses
- **Setup is developer-grade, not app-store-grade.** Needs Python 3.12+, `uv`,
  ADB, scrcpy, FFmpeg, USB debugging. There is **no APK to install** — the tool
  runs on a **host machine** and drives the phone over ADB. (Verified: no GitHub
  releases exist.)
- **Needs a paid LLM API key** (Gemini / OpenAI / Anthropic / OpenRouter / xAI)
  — the model calls are the cost. Free-tier Gemini keys work for light use.
- **Young project** — created 2026-08-13, last push 2026-10-01, no releases yet.
- **Android only** (iOS is on the roadmap, not shipped).
- **Privacy/trust surface:** it installs an Accessibility Service on the phone
  (README: it "listens only on the phone itself and sends nothing elsewhere", but
  screen contents do go to the configured LLM provider).
- **Guardrails matter:** on a *personal* phone you should set
  `ARTEMIS_HELPER_AUTO_INSTALL=false` and `ARTEMIS_KEEP_DEVICE_AWAKE=false`.

### Opportunities
- **QA automation without a device farm** — regression testing on a real phone
  from CI (the Python SDK fits pytest/CI).
- **Accessibility smoke-tests** — drive TalkBack / large-font flows on a real device.
- **Reproduce bug reports** — "do these 8 taps, capture Logcat + screenshot".
- **Reusable for the Amina / Miss Noor app** — an agent could exercise the
  Arabic/French learner flows on a real Android phone, not just a headless browser.
- **Foundation for an on-phone agent** — once an OpenHands agent has an MCP client,
  ARTEMIS *is* the "hands" for a phone.

### Threats
- **Cost drift** — Pro profile at ~15–40 s/step on a 100-step task burns tokens fast.
- **Supply-chain / trust** — it runs with ADB privileges and installs an
  accessibility service; only run it from the official `google/artemis` repo.
- **Personal-data exposure** — screen contents and Logcat go to a third-party LLM.
- **API churn** — young repo; commands/config may change between commits.
- **Policy** — automating a bank / messaging app may violate that app's ToS.
- **Impersonation risk** — the reel is an unaffiliated creator; the real repo is
  the only authoritative source.

## 4. How to get it "on your phone" (step by step)

Key correction to the video: **ARTEMIS does not install on the phone as an app.**
It runs on a computer (or a server), and the *phone* is the target. The phone only
receives a small accessibility helper APK.

### A. Prerequisites
- An **Android phone** (or emulator) with **Developer options → USB debugging** ON.
- A **computer** with Python **3.12+** and `uv` (or run it on a server).
- **One LLM API key** — the free `GEMINI_API_KEY` tier is enough to start.
- **ADB** must see the device: `adb devices` should list it.

### B. Install and run (from the README, Verified)
```bash
git clone https://github.com/google/artemis.git && cd artemis
./start.sh          # macOS/Linux — auto-installs ADB, scrcpy, FFmpeg, uv deps
# Windows PowerShell:  .\start.bat
```
Then open `http://localhost:8000` for the visual console, or run headless:
```bash
uv run artemis run "Open Settings, find Battery and tell me the current level" --profile flash
```
Put your key in `.env` (copy `.env.example`): `GEMINI_API_KEY=…`.

### C. Wire it into an AI agent (MCP)
```bash
uv run artemis mcp --install all      # Claude Code / Codex / Antigravity / Cursor / Windsurf
```
Manual (Codex, `~/.codex/config.toml`):
```toml
[mcp_servers.artemis]
command = "/path/to/artemis/.venv/bin/python"
args = ["-m", "mcp_server"]
cwd = "/path/to/artemis"
[mcp_servers.artemis.env]
PYTHONUNBUFFERED = "1"
PYTHONPATH = "/path/to/artemis"
```
Also mount `mcp_server/rules.md` as the agent's rules (the README calls this
"highly recommended") so the agent behaves like a careful mobile test engineer.

### D. Remove it
`uv run artemis helper uninstall` — and turn off USB debugging when done.

## 5. "With me on OpenHands" — how the agent fits

- **Closest match today:** ARTEMIS ships MCP, and OpenHands agents speak MCP. Add
  ARTEMIS as an **MCP server** in an OpenHands Cloud conversation (Settings →
  MCP servers) pointing at a host that has the phone attached. The agent then
  gets `mobile_run_task`, `mobile_get_device_state`, `mobile_diagnose`, etc.
- **Caveat (Hypothesis):** the MCP server is a local `stdio` process that must be
  able to reach ADB and the phone. It has to run on a machine with the device
  physically attached — a cloud sandbox cannot reach your phone unless the phone
  is on the same network via ADB-over-TCP or the MCP host is your own laptop.
- **This sandbox cannot demo it:** there is no Android device and no ADB here, so
  the phone-driving path is **Blocked** in this environment. What *was* run here:
  reel metadata + ASR transcript + the GitHub/README verification.

## 6. About "reverse engineering it"

You do not need to reverse-engineer anything — it is Apache-2.0 open source, so
the source *is* the spec. If the intent is "understand how it works so I can
rebuild it", the honest answer is:

- It is **not** a hidden binary. `google/artemis` is ~Python: a `langgraph` agent
  graph (planner/operator/checker), an ADB + scrcpy device layer, a multimodal
  locator (accessibility tree + OCR + vision), and an MCP server wrapper.
- The only closed part is the **LLM** it calls (Gemini/Claude/GPT) — that is a paid
  API, not something to reverse.
- Reading `mcp_server/server.py`, `artemis/`, and `config/artemis.jsonc` in the
  cloned repo is the legitimate path.

I did **not** attempt to bypass any authentication, DRM, or access control — the
project is public and needs none.

## 7. Bottom line

- The video is **substantially accurate**: Google really did open-source a free
  Android-automation agent, ~16.7k stars, 99%+ AndroidWorld, native MCP, works
  with Claude Code and Codex. (Observed-not-verified: the reel's own claims beyond
  what the repo states.)
- The one thing the video glosses over: **it does not go on your phone.** It runs
  on a computer and drives the phone over USB/ADB. "On my phone" = the phone is
  the target, the accessibility helper is the only thing installed on it.
- Fastest path for the owner: clone → `./start.sh` → set `GEMINI_API_KEY` →
  `artemis mcp --install all` → prompt your agent. Cost = LLM tokens only.

## Sources
- Repo: https://github.com/google/artemis (Apache-2.0)
- AndroidWorld benchmark: https://github.com/google-research/android_world
- Reel: https://www.facebook.com/share/r/19mVcPn8wa/ (id `1421050626342423`)
- Transcript: `watcher/knowledge/video/2026-11-06-google-artemis-phone-control.md`
