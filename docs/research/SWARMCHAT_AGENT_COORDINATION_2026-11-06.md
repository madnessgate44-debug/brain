# SwarmChat — "Open-source Slack for your AI agent swarm" — research, SWOT, install & reverse-engineering

- **Date:** 2026-11-06
- **Trigger:** owner shared `https://github.com/Pranjal2041/swarmchat` with "same protocol"
  (watch/understand → save a transcript + a learning write-up → create the skill accordingly
  → replace the earlier thing we built).
- **Upstream:** `Pranjal2041/swarmchat` — MIT, Python 3.9+, **zero dependencies**, one package
  is both server and client. Launch site `https://swarmchat.io/` (2026-10-29).
- **Evidence rule:** every claim is tagged `[V]` verified here, `[C]` reported by upstream,
  `[I]` inference, `[A]` assumption, `[U]` unknown. Nothing is claimed as run unless it was run.

## 0. Why this matters to us (one paragraph)

We already built a hand-rolled agent-coordination layer: `watcher/bridge/` (a GitHub-issue
"hub" at `madnessgate44-debug/brain#240` + a bespoke ticket envelope + a polling loop) and the
`watcher/skills/watcher-bridge/` skill. SwarmChat is the purpose-built, open-source version of
exactly that idea — a real chat server with channels, DMs, threads, files, notifications, a
blocking `wait`, and a live web viewer — in **~1,560 lines of dependency-free Python** `[V]`.
It is the "b*******" the owner wants replaced: the custom bridge reinvents what SwarmChat
already ships, and SwarmChat's own paper quantifies the coordination wins our bridge never
measured.

## 1. What it is `[V]`

| Fact | Value | Source |
|---|---|---|
| Repo | `Pranjal2041/swarmchat` | GitHub API 2026-11-06 |
| Description | "Open-source Slack for your AI agent swarm" | GitHub API |
| Stars / forks | **104** / 17 | GitHub API |
| License | **MIT** | GitHub API |
| Created / last push | 2026-10-29 / 2026-11-05 | GitHub API |
| Language | Python **3.9+**, **stdlib only, zero deps** | pyproject.toml, README |
| PyPI | `pip install swarmchat` (v0.1.0) | PyPI |
| Releases | **none** (PyPI package only, no git tags) | GitHub API |
| Homepage | `https://swarmchat.io` | GitHub API |
| Authors | Pranjal Aggarwal, Lawrence Keunho Jang, Jing Yu Koh, Daniel Fried, Ruslan Salakhutdinov, Sean Welleck (CMU), Kevin Yang, Nicolai Ouporov (Fleet AI) | launch article |
| Source size | ~1,560 lines of Python across 8 modules | DESIGN.md |

It is **not** a hosted service and needs no key, no card, no account. One process serves HTTP
(JSON) and owns a plain-files data directory; each participant (agent or human) is a `swarmchat`
CLI client identified by a token the participant does not choose.

## 2. Core model `[V]` (from DESIGN.md + live run)

- **User** — short id (`watcher`), display name, free-form fields, status line.
- **Chat** — an id + a member list. Two kinds, like Slack: a **direct chat** (no name; made on
  first message; members never change) and a **channel** (named, public or private, members can
  change). A DM is just a chat with two members.
- **Message** — id, chat, sender, time, text, optional `reply_to`, parsed `@mentions`.
- **Read cursor** — last message each user read per chat; moving it writes a "read" line = read
  receipts.
- **Notification level** — per user per chat: `all` | `mentions` | `none`.
- **Roles** (Slack-like, in `policy.py`): super admin (holds `admin.token`, never posts),
  administrators, channel creators, channel managers, members. Rules can also restrict who may
  DM whom and name channels only listed users may post to (e.g. a verifier-only results channel).

### The agent-critical feature: `wait`

`swarmchat wait` is a **server-side long poll**. It blocks until a matching message arrives,
prints it, and exits; the idle agent **spends no tokens and does not poll** `[V]`. `--from`,
`--chat`, `--mentions`, `--where`, `--timeout`, `--peek` narrow it. Wait starts from the read
cursor, so nothing that arrives between two waits is lost. Exit codes: `0` done, `1` bad usage,
`2` not found, `3` not allowed, `4` wait timed out.

### The viewer: `swarmchat view` `[V]`

A read-only web page served at `/view` that watches the whole swarm live: **Chat** (channels,
DMs, threads, reactions, read receipts, files), **Board** (Reddit-style), **Map** (every agent
and message drawn as it travels), **Replay** (the run again from any moment, up to 600× speed),
**As an agent** (see exactly what one agent sees, down to where it stopped reading), and search.
It works on **phones and tablets**. It is one HTML file, no build step, and it changes nothing —
its token is accepted for nothing else.

## 3. What the launch article measured `[C]`

The article is a rare quantified study of agent teams (this is the part worth learning from):

- **A swarm is 3–7× faster.** Eight agents hit the same ProgramBench score a solo agent needed
  3–7× longer to reach.
- **Larger swarms scale.** Sixteen agents scored in one hour what one agent took ~11 hours to
  reach. Swarm-scaling exponent **λ ≈ 0.43–0.86** for 4/8/16 agents (1.0 = perfect parallelism);
  eight agents used ~1.3× the tokens to save ~5 hours.
- **Structure barely matters on average.** Four eight-agent structures (flat, lead, features,
  phased) finished within a few points of each other (88.5 / 85.2 / 85.8 / 87.8), but per
  program the structure changed scores by up to 33 points. "No structure" was as good as any.
- **Models coordinate differently.** GPT-6-Luna agents mostly DM each other (81–82% direct);
  Claude Haiku agents broadcast to `#general` (83% channel). Push announcements spread as teams
  grow; rebase/merge-conflict mentions stay ~1.5–2 per agent per hour.
- **Main-character syndrome is real.** In one run five agents each claimed the core of the
  program in the opening seconds.

Takeaway for us `[I]`: the value is a shared, inspectable message bus + a blocking wait, not a
clever orchestration protocol. Our own bridge proved the bus; SwarmChat proves it scales and can
be graded.

## 4. SWOT

### Strengths
- **Zero dependencies, stdlib only, ~1,560 lines** — runs on any agent box, `python3 -m swarmchat`
  starts in <0.1s `[C]`. Trivial to read, audit, fork, and vendor into our repos `[V]`.
- **`wait` is a true long poll** — an agent idles for free, no token burn, no polling loop `[V]`.
- **Plain-file, append-only storage** (`chats/<id>/log/000001.jsonl`) — `cat`/`grep`/`git`-able;
  a whole run is archived by moving one folder `[V]`. Directly compatible with our
  "evidence in files" habits.
- **Live, phone-friendly viewer** with replay and per-agent view — gives us the observability our
  bridge never had `[V]`.
- **Real permissions** (5 roles, per-action `allow`, DM-graph rules, verifier-only channels) —
  enough to model a company of agents with boundaries `[V]`.
- **A published benchmark** behind it, so the design is evidence-driven, not vibes `[C]`.
- **Both CLI and Python API** (`from swarmchat.client import Client`) — drive agents from code or
  shell `[V]`.

### Weaknesses
- **Very new and low-adoption:** 104 stars, created 2026-10-29, **no releases**, v0.1.0 `[V]`.
  API/format can change under us.
- **No encryption, no federation, no voice** by design (v1) `[C]`. Server sees every message;
  the data folder's modes protect against other users, not other processes of the same user `[C]`.
- **Single-process, single-writer per data dir**; Python HTTP caps at ~2,000 req/s `[C]`.
- **Auth is a bearer token in a file** — fine on one box, thin across a network `[V]`.
- **Storage rewrite on delete** (blanks lines in place, padded to equal length, with a
  `redact.journal` for crash recovery) — a subtle area to audit `[C]`.
- **The launch video is silent b-roll**; the substance is the article + DESIGN.md `[V]`.

### Opportunities
- **Replace our bespoke bridge.** `watcher/bridge/` + the `watcher-bridge` skill become a thin
  adapter over SwarmChat: same evidence discipline, a real transport `[I]`.
- **One server for the whole swarm.** Watcher, Shadow, Forge, OpenHands sessions, and the owner
  can share `#general` + DMs, with the viewer as the control room on a phone `[I]`.
- **Gradable coordination.** Because every message is a JSON line, we can replay and score our own
  runs (who unblocked whom, time-to-answer) exactly as the paper did `[I]`.
- **Vendor a pinned copy** into the repo (MIT allows it) so CI and sessions are reproducible even
  if upstream moves `[I]`.
- **`--where EXPR`** lets an agent subscribe to a precise slice (e.g. only messages mentioning it
  in a named channel) `[V]`.

### Threats
- **Young project, single maintainer group; no release tags.** Pin a commit if we depend on it `[I]`.
- **Security surface:** a chat server on a host is an attack surface; a token leak is full
  impersonation. The data dir must be `0700` and agents should run as separate users `[C]`.
- **`--where` runs a Python expression client-side** — the server never runs it, and attributes
  are whitelisted, but we must not pass untrusted expressions `[C]`.
- **Adoption trap:** adopting a moving v0.1 into our core could churn; keep it behind an adapter
  and a pinned version `[I]`.
- **Zero-cost rule:** SwarmChat itself is free (no card). Self-hosting on a phone/laptop is fine;
  any *hosted* SwarmChat would need review against the owner's no-card rule `[I]`.

## 5. How to get it and run it (phone / laptop / OpenHands)

SwarmChat is free, keyless, and needs no card `[V]`. Python 3.9+ is the only requirement.

**Install (anywhere Python runs):**
```bash
pip install swarmchat
python3 -m swarmchat --help      # the CLI; `swarmchat` also works once scripts are on PATH
```

**Start a server and add one user per agent:**
```bash
swarmchat serve                              # http://127.0.0.1:8484
swarmchat admin add watcher --name "Watcher" # prints the token
swarmchat admin add shadow  --name "Shadow"  # prints the token
```

**Give each agent its address + token (env, or `swarmchat login`):**
```bash
export SWARMCHAT_SERVER=http://127.0.0.1:8484
export SWARMCHAT_TOKEN=<that agent's token>
```

**The loop an agent actually runs:**
```bash
swarmchat chats                                   # unread counts
swarmchat read                                    # new messages, then marked read
swarmchat send shadow "Can you review my change?" # a DM (chat made on first send)
swarmchat send "#general" "Merged." --reply-to ID # a threaded reply
swarmchat wait --from shadow                      # block until Shadow writes (free while idle)
```

**Watch everything (best on a phone):**
```bash
swarmchat view        # opens http://HOST:PORT/view#token=...  (read-only, live, replay)
```

**From Python:**
```python
from swarmchat.client import Client
me = Client("http://127.0.0.1:8484", token)
me.send(chat="shadow", text="Can you review my change?")
reply = me.wait(timeout=600)
```

**On a phone** `[I]`: install Python (Termux on Android, or a Python app on iOS), `pip install
swarmchat`, run `serve`, and point the phone browser at `/view`. The server and the phone may be
the same device. Remote agents reach it with `--host 0.0.0.0` + `--tls-cert/--tls-key`, adding
users via `swarmchat admin --admin-token … --server URL`.

## 6. Reverse-engineering notes (how it is built)

Read from DESIGN.md + the live CLI `[V]`; no private code was needed.

- **One package, two roles.** `swarmchat serve` is the server; every other subcommand is a
  client. Both ship in one dependency-free package.
- **Module map** (each readable alone): `store.py` (files + in-memory index), `api.py` (what a
  request does), `server.py` (HTTP, tokens, the long-held `wait`), `policy.py` (who may do what),
  `client.py` (one method per request + `--where`), `cli.py` (commands/flags/output). Budget:
  ~1,500 lines; v0.1 is 1,560 `[C]`.
- **Wire protocol:** HTTP + JSON; each CLI command is one request; `wait` is a long poll the
  server holds open `[C]`.
- **Storage:** `chats/<chat>/log/NNNNNN.jsonl`, append-only, one JSON object per line; new file
  every 10,000 messages; edits/deletes/reactions appended as events pointing at the original;
  deletes blank the original line in place padded to equal length, with a `redact.journal` for
  crash recovery; state files replaced atomically `[C]`.
- **Index rebuild:** on start the server rebuilds in memory from the files (last seq, last
  message, members per chat; read cursors + settings per user); recent messages served from
  memory or the newest log file `[C]`.
- **Limits that matter for safety:** token checked before the body is read; request
  line/headers/body deadlines; `max_connections` 4,096 (evicts the longest-idle connection);
  `max_requests` 32 per user; `min_free` 1 GB; optional per-user byte `quota` `[C]`.
- **Security posture:** private channels answer outsiders as if they do not exist; members see a
  random attachment id, never the content hash; the viewer's token can only look; text is escaped
  and the page's CSP allows only its own hashed script `[C]`.
- **`--where EXPR`:** a Python expression over plain message/chat data run **client-side** with a
  checked attribute whitelist (`m.text`, `m.sender`, `m.at`, `c.members`, `re`), so it cannot
  import, open files, or run commands `[C]`.

## 7. Verification done this session `[V]`

Live run of `pip install swarmchat` (v0.1.0) on 2026-11-06:

| Check | Command | Result |
|---|---|---|
| Install + version | `pip install swarmchat` → `swarmchat 0.1.0` | PASS |
| Server boots | `python3 -m swarmchat serve --data /tmp/swdata --port 8484` | PASS — "0 users, 0 chats … serving http://127.0.0.1:8484" |
| Add two agents | `admin add watcher` / `admin add shadow` | PASS — two tokens printed |
| Create public channel | `channel create general --public` | PASS |
| Send to channel | `send "#general" "…"` | PASS — `Sent 2a71abd9e9dc07f1:2` |
| **Blocking wait** | background `wait --from watcher`, then `send shadow "…"` | PASS — wait idled, then printed the message and exited 0 |
| Wait timeout | `wait --timeout 2` | PASS — exit code **4** |
| JSON mode | `chats --json` / `read --json` | PASS — one JSON object per line |
| Directory / info | `people`, `info "#general"`, `whoami` | PASS |

Artifacts: `watcher/knowledge/video/2026-11-06-swarmchat-launch.{txt,md,article.txt}`.

## 8. Recommendation `[I]`

1. **Adopt SwarmChat as the swarm bus**, pinned to a commit, behind a thin adapter in
   `watcher/bridge/` (keep our evidence/ticket discipline, drop the bespoke transport).
2. **Supersede** the `watcher/skills/watcher-bridge/` skill with `swarmchat-coordination`
   (this change), which keeps the hard rules and points the transport at SwarmChat.
3. **Run Watcher + Shadow + a session on one local server** with `#general` and DMs; use
   `swarmchat view` on the phone as the control room; use `wait` so idle agents cost nothing.
4. **Grade our own runs** from the JSONL logs (time-to-answer, who unblocked whom) the way the
   paper did.

### Open questions `[U]`
- Does upstream want to be depended on (no releases yet)? Pin, or vendor an MIT copy?
- Where does the shared server live so CI jobs and local sessions can both reach it, under the
  free/no-card rule?
- Migration: does the existing hub `brain#240` stay as the durable audit trail while SwarmChat
  carries the live chat?
