---
name: watcher-learning
description: >
  Watcher's continuous learning loop. Use when Watcher must watch and monitor sources,
  audit its own state, look for solutions on GitHub or Hugging Face, or turn a found
  tool/repo/video into a concrete proposal. Triggered by phrases like "run the learning
  loop", "find solutions on GitHub", "search Hugging Face", "audit yourself", "what
  should we learn today", "monitor for new work", or "scan the sources".
---

# Watcher learning loop

Implements WATCHER.md §4 (daily cycle: §4.3 research, §4.4 transcribe) and the §4.5
Result-1 gate. This skill is the *find and judge* half; the *take it apart* half is
`watcher-reverse-engineering`.

One rule over all: **no secret value ever appears in a file, issue, PR, comment, or log.**
Read secrets only inside a workflow at runtime. Report labels and pass/fail, never values.

## The loop (one pass)

```
1. AUDIT   → read the live state (open PRs, open issues, recent CI, shadow/registry.md)
2. SCAN    → search the sources for new material (GitHub, Hugging Face, YouTube, queue.txt)
3. TRIAGE  → rank what is worth the time; drop the noise
4. REVERSE → for the top item, run watcher-reverse-engineering → a finding
5. PROPOSE → open the §8 proposal (Issue), Shadow challenges it in-thread
6. LOG     → append the pass to watcher/reports/<date>.md; update watcher/knowledge/
```

A pass ends with exactly one of: a finding, a proposal, or an honest "nothing new".
It never ends with a bare heartbeat.

## 1. Audit the live state first

Do not learn in the dark. Establish the baseline before scanning:

```bash
# Open PRs and issues (owner is a user account, not an org)
gh pr list   --repo madnessgate44-debug/brain --state open --limit 60 \
  --json number,title,isDraft,mergeable,mergeStateStatus,headRefName
gh issue list --repo madnessgate44-debug/brain --state open --limit 60

# Shadow's key/route pool is the authority on what is usable
cat shadow/registry.md

# The queued learning material
grep -v '^#' watcher/knowledge/queue.txt | grep -v '^[[:space:]]*$'
```

Skip any item `main` or an open PR already did (WATCHER.md §8.5). Record the baseline in
the report; a later claim is judged against it.

## 2. Scan the sources

All routes below are free and need no card (WATCHER.md §6, §14.6).

**GitHub — find a tool or an approach**

```bash
# By topic and language, most-starred first
gh api "search/repositories?q=<terms>+language:python&sort=stars&order=desc&per_page=10" \
  --jq '.items[] | "\(.full_name)  \(.stargazers_count)★  \(.description // "")"'

# Read one repo without cloning
gh api "repos/OWNER/REPO" --jq '{stars:.stargazers_count,license:.license.spdx_id,pushed:.pushed_at}'
gh api "repos/OWNER/REPO/git/trees/HEAD?recursive=1" --jq '.tree[].path'
gh api "repos/OWNER/REPO/contents/PATH" --jq '.content' | base64 -d
```

Prefer the API over a browser. It is faster, rate-limited but free, and returns raw
bytes you can quote as evidence.

**Hugging Face — models, spaces, datasets**

```bash
curl -s "https://huggingface.co/api/models?search=<terms>&sort=downloads&limit=10"      # models
curl -s "https://huggingface.co/api/spaces?search=<terms>&sort=likes&limit=10"          # spaces
curl -s "https://huggingface.co/api/datasets?search=<terms>&sort=downloads&limit=10"    # datasets
curl -s "https://huggingface.co/api/spaces/OWNER/NAME"                                   # one space (gated? sdk?)
```

Check `gated`, `sdk`, and the license before proposing anything. A space that runs on
ZeroGPU bills the *visitor's* quota, not ours.

**Video / reels** — hand a URL to `watcher/knowledge/tools/transcribe.py` (YouTube
captions first, local faster-whisper ASR fallback). Store the transcript under
`watcher/knowledge/video/<date>-<slug>.{md,txt}`. The scheduled `watcher-learning.yml`
workflow does this on its own from `queue.txt`.

**A link the owner hands over** is a first-class source: treat it as the target for the
next reverse-engineering pass, not as trivia.

## 3. Triage

Rank candidates by **value to Forge / brain**, then by cost. A good candidate is:

- **adoptable** — an algorithm or pattern we can port, not a whole product we must run;
- **cheap to judge** — a public repo or a spec we can read without a GPU or an account;
- **honest about cost** — free, no card, no login wall.

Drop: marketing, closed SaaS, anything that wants a card, and anything whose only value is
"it exists". Record why in one line.

## 4. Reverse the top item

Run `watcher-reverse-engineering` on the winner. That skill owns the method and the output
format. The result lands in `watcher/knowledge/reverse/<slug>.md`.

## 5. Propose (WATCHER.md §8)

A finding becomes work only through a proposal:

1. Open a GitHub Issue: **problem, source, proposed fix, confidence, risk.**
2. Tag it `forge` / `openhands` / `watcher` / `self-improvement`.
3. Shadow challenges it in the same thread (`shadow/shadow.py --subject …`).
4. One line goes to the owner. Technical proposals are approved without asking
   (WATCHER.md §15); ask only about ideas, direction, or money.

Never self-merge. Never act without logging. Propose before anything irreversible.

## 6. Log

Append the pass to `watcher/reports/<date>.md`: sources scanned, the item chosen, the
finding path, the proposal id, and what was skipped with the reason. Update
`watcher/knowledge/index.md` if it exists.

## Evidence tags (use them inline)

- `CONFIRMED` — a live tool result proves it (HTTP 200, a quoted file line).
- `HYPOTHESIS` — a deduction from confirmed facts.
- `UNKNOWN` — an explicit gap.
- `DISPROVED` — a live result contradicts it.

A claim without a tag is an assumption. "A repo exists" is not "the repo works".

## Cadence honesty

Sessions cannot self-schedule. The cron lives in the workflows
(`watcher-daily.yml`, `watcher-learning.yml`). A loop pass you run now is a manual pass;
say so. Never claim a scheduled or unattended run happened unless you can point at the
`actions/runs?event=schedule` record for it.

## Boundaries

- Free, no-card services only. If a source wants a card, stop and report it.
- Authorized targets only for reverse engineering (see the sibling skill).
- Do not depend on any route being online. If it fails, log it and continue with the rest
  of the pass.
