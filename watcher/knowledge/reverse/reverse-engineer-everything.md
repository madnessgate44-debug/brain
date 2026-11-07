# Reverse-engineering finding: REE — reverse-engineer-everything

Source: `https://github.com/gryszzz/reverse-engineer-everything` (29★, 7 forks, MIT,
TypeScript, created 2026-10-14, last push 2026-10-28, default branch `main`). Read via the
GitHub API + raw file fetch 2026-11-07; no clone, no execution of the target.

The owner named this repo ("reverse engineer everything"). It is a **local, evidence-first
reverse-engineering workbench** and — directly relevant to us — it *ships two agent skills*
of the same shape we are building, so it is both a target to dissect and a model to learn
from.

## What it is

REE is a **product layer on top of an inherited engine, REA** (`morluto/rea`, MIT). REE does
not rewrite the engine; it adds a beginner on-ramp: an Investigation Studio that binds to
`127.0.0.1`, a set of `node ree.mjs` commands, readiness checks, a macOS app bundle, and an
opt-in public-document collector. The engine does the analysis; REE makes it usable and,
above all, makes its results **evidence-backed**.

The one-line goal, from its own `REE_START_HERE.md`:

```
Question → choose authorized target → observe behavior → inspect structure
         → separate facts from guesses → verify → record what remains unknown
```

## The architecture (exact)

- **Product / engine split.** REE (this repo) = studio + CLI + packaging. REA
  (`morluto/rea`) = the analysis engine and MCP server. The README is explicit that
  `npx rea-agents setup` installs *upstream REA, not this checkout* — a clean separation of
  interface from engine. **CONFIRMED** (`README.md` "REE and REA").
- **Studio is loopback-only.** `127.0.0.1`, no account, no upload; a pasted link shows the
  URL, byte/time limits, and destination *before* anything is fetched, and requires an
  explicit boolean `approved` plus a digest match. `http`, credentials, and non-public
  addresses are refused. **CONFIRMED** (`README.md` "Safety and authorization").
- **Analysis is static and bounded.** The child process is the public engine command for the
  chosen route; one run at a time, a three-minute timeout, then SIGTERM → SIGKILL. The
  ambient environment is *not* saved as evidence. **CONFIRMED** (`README.md` §Safety).
- **Evidence has identity.** Every finding cites an Evidence id (e.g.
  `ev_45d365f3b6f0be5b…`) plus saved `evidence.json` / `view-evidence.json`. Nodes and edges
  are reported as counts (49 nodes, 67 edges) with the id. **CONFIRMED** (`README.md` frames).
- **Two shipped agent skills** (this is the part we most want):
  - `.agents/skills/reverse-engineer-anything/SKILL.md` (22 KB, `version: "41"`) — a routing
    skill: pick the first tool from the *target type* (ASAR/JS → `analyze_javascript_application`;
    ZIP/APK/IPA/MSIX/DMG → `open_binary`; Android → `inspect_android_package`; managed PE →
    `inspect_managed_artifact`; firmware → `inspect_firmware_regions`; browser → `list_browser_targets`;
    packet capture → `inspect_packet_capture`; …). It tells the agent to **skip REA entirely for
    ordinary source-repository analysis** — REA is only for when a claim depends on a shipped
    binary or runtime evidence. **CONFIRMED**.
  - `.agents/skills/ree-investigator/SKILL.md` — the 7-step investigator loop: define question
    and scope → intake (no execution) → check readiness → run only in authorized scope → read
    the Evidence → explain plainly (facts vs. guesses, confidence, unknowns) → reconstruct only
    after evidence. **CONFIRMED**.
- **The governing rule, stated by the repo itself:** *"Static relationships are inferences,
  not proof of execution."* Observations, derivations, confidence, unknowns, and coverage are
  kept **separate by design**. **CONFIRMED** (`REE_START_HERE.md`).

## Where it intersects our work (the gap it fills)

Our Watcher has the *roles* (WATCHER.md §7 "Core job: find public repos, dissect, extract")
but **no written method** for how to dissect, and no rule for separating observed from
inferred. Two concrete gaps in `brain` before this pass:

1. There is no skill that tells Watcher **how to watch, monitor, audit, search GitHub/HF, and
   turn a find into a proposal** — the loop lived in prose in `WATCHER.md`, not in a skill.
2. The existing finding (`watcher/knowledge/reverse/aider-repomap.md`) is good, but there was
   **no reusable method** behind it — each finding re-improvised its shape.

REE's contribution is not code to port (we run no binaries). It is **method and discipline**:
the route-by-target-type idea, the evidence-identity idea, and — most of all — the explicit
*inference vs. observation* separation. Those are directly adopted in the two new skills in
this PR.

## What is worth implementing (ranked)

1. **Adopt the observation/inference/unknown separation into Watcher's findings.** Highest
   value, zero cost. Our evidence tags already lean this way; REE makes it the spine. → done
   in `watcher-reverse-engineering/SKILL.md` §"Separate observed from inferred".
2. **Adopt route-by-target-type for shipped artifacts.** A short routing table so Watcher
   never improvises a half-instrumented attempt on a binary. → done as the "Authorized targets
   for shipped artifacts" section (route it to a dedicated engine; do not fake it here).
3. **Adopt evidence identity.** Every finding should cite the exact revision/path/line it read.
   → done: the "Verification done this session" section, with the read ref named.
4. **The REA engine itself.** *Not* a port. It is a large Node/TypeScript analysis toolchain
   requiring provider binaries (Ghidra/IDA/Hopper) and Node 24. Nothing in brain's path needs
   it today. Route to it only if a real shipped-artifact question appears. **Deferred.**

## What to skip

- Running REE or REA. No binary in our stack to analyze; no GPU; no Node-24 toolchain need.
- Its macOS app bundle, landing page, release jobs — unrelated to our pipeline.
- Its many real-* CI workflows (real-cutter, real-ghidra, real-hopper, …) — they validate
  REE's own engine coverage, not ours.

## Confidence and risk

- Confidence: **HIGH** on what REE is and how it is structured (README 88 KB, START_HERE,
  both skills, and the file tree read in full this session).
- Confidence: **HIGH** that the transferable value is method, not code.
- Risk of adopting: **LOW** — no dependency added, no license entanglement (we adopt ideas
  under our own words; REE is MIT and attributed here).
- Risk of the *engine* claim: **MEDIUM** — we did not run REA, so "it analyzes X" is REE's
  documented claim (**CONFIRMED** as documentation), not a result we reproduced (**UNKNOWN**
  as a live run). Stated honestly.

## Verification done this session

- `GET /repos/gryszzz/reverse-engineer-everything` → MIT, 29★, default branch `main`.
- Git tree (recursive) read; the `.agents/skills/*` entries identified.
- Read in full: `README.md` (88 KB), `REE_START_HERE.md`, `DISCLAIMER.md`,
  `.agents/skills/reverse-engineer-anything/SKILL.md` (22 KB),
  `.agents/skills/ree-investigator/SKILL.md`.
- Safety and authorization section read at `README.md` line ~345.
