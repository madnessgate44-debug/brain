---
name: watcher-reverse-engineering
description: >
  Watcher's "reverse engineer everything" method. Use to dissect a public repo, tool,
  shipped artifact, or documented system and extract what is worth implementing for Forge
  or brain. Triggered by phrases like "reverse engineer this", "take this apart", "what can
  we steal from it", "dissect this repo", or when the learning loop picks a target.
  Output: a finding under watcher/knowledge/reverse/.
---

# Watcher reverse-engineering

Implements WATCHER.md §7. The core job: find a public, high-quality target, dissect its
architecture, and extract what is worth implementing for Forge and OpenHands. The output
is always a finding file, never a bare summary.

This skill is an *evidence discipline*, adapted from the REE/REA approach (see
`watcher/knowledge/reverse/reverse-engineer-everything.md`). It borrows their core idea:
**separate what is observed from what is inferred, and never claim more than the evidence
shows.** The tooling here is read-only: the GitHub API, Hugging Face API, and raw file
reads. No clone, no execution of the target, no GPU.

## Scope and authorization first

Before touching anything, write down:

- **target** — owner/repo or URL, and the exact revision (commit/branch/date) you read;
- **permission** — a public repo is readable, not necessarily modifiable; you are reading,
  never changing the target;
- **the question** — the one thing this pass must answer (e.g. "how does it select
  context?"), not "explain everything";
- **allowed actions** — reads only, unless the owner authorizes more.

Never silently broaden the target. Public availability is not permission to execute,
redistribute, or claim authorship. Do not reverse-engineer anything the owner is not
authorized to inspect.

## Method

```
1. IDENTIFY  → repo facts: stars, license, language, last push, default branch
2. MAP       → file tree; find the modules that answer the question
3. READ      → the real source, quoted, at a named revision
4. SEPARATE  → observed facts vs. inferences; keep unknowns listed
5. GAP       → where our stack (Forge / brain) is weak here, with our own file+line
6. RANK      → what is worth implementing, cheapest-highest first
7. SKIP      → what is not worth it, and why
8. CONFIDENCE→ confidence + risk, honestly
9. RECORD    → the finding file + the verification actually done
```

### 1. Identify (GitHub API)

```bash
gh api "repos/OWNER/REPO" \
  --jq '{stars:.stargazers_count, forks:.forks_count, license:.license.spdx_id,
         lang:.language, pushed:.pushed_at, branch:.default_branch}'
```

### 2. Map the tree

```bash
gh api "repos/OWNER/REPO/git/trees/HEAD?recursive=1" --jq '.tree[] | select(.type=="blob") | .path'
```

Find the modules that answer your one question. Ignore the rest.

### 3. Read the real source (quoted)

```bash
gh api "repos/OWNER/REPO/contents/PATH?ref=<sha-or-branch>" --jq '.content' | base64 -d
# or, for a file you will read whole:
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://raw.githubusercontent.com/OWNER/REPO/<ref>/PATH"
```

Quote the lines that prove your claim. An unquoted claim is an assumption.

### 4. Separate observed from inferred

This is the rule the whole skill exists for. REA's own framing: *static relationships are
inferences, not proof of execution.* Apply it to us:

- **Observed** — what a raw file or a live response literally says.
- **Inferred** — what you conclude from it. Label it.
- **Unknown** — what you could not establish. Keep it listed; do not paper over it.

A repo existing is observed. That its algorithm is good is inferred. That it would drop
into Forge is a hypothesis until a test shows it.

### 5. Find our gap

The finding is only useful if it points at a real weakness in *our* stack, named with
our own file and line (e.g. `Firstborn/src/agent/forge.ts` ~line 558). Read our code, not
just theirs.

### 6–7. Rank what to take; list what to skip

Rank by value to Forge/brain and by cost. Skip: whole products we would have to run,
40-language support when we use one language, anything unrelated to our pipeline.

### 8. Confidence and risk

State confidence HIGH/MEDIUM/LOW and where it comes from (read the source? only the
README?). State the risk of adopting, and the cheapest test that would confirm it.

## Output format

Write `watcher/knowledge/reverse/<slug>.md` in the house shape (see
`aider-repomap.md` for the exemplar):

```
# Reverse-engineering finding: <target> (<what it is>)

Source: <url> (<stars>★, <license>), file <path> (<lines>). Read via <method> <date>.

## The problem it solves
## The algorithm / architecture (exact)   ← quote the source
## Where it intersects our work           ← our file+line gap
## What is worth implementing (ranked)
## What to skip
## Confidence and risk
## Verification done this session          ← the exact commands you ran
```

## Evidence discipline

- Every non-trivial claim carries a tag: **CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED**.
- The "Verification done" section lists the real commands and what they returned. No entry,
  no claim.
- If you could not read a file, say so — do not reconstruct it silently.

## Authorized targets for shipped artifacts

Reading a public repo is in scope. Taking apart a **shipped binary, package, firmware, or
runtime** is a different, higher bar and is *not* done from this sandbox by default. That
work belongs to a dedicated, evidence-first engine (REA, the engine behind
`reverse-engineer-everything`) and needs, per its own rules:

- explicit authorization for the exact target and action;
- static, read-only work first; runtime/attach/network capture as a separate review;
- Evidence saved with ids, coverage, and unknowns — never a hand-drawn result.

If a task genuinely needs that engine, say so and route it there rather than improvising
a half-instrumented attempt. Never run, attach to, or fetch on behalf of an unknown target
just because its file type looks supported.

## Boundaries

- Read-only against the target. Never modify, redistribute, or claim authorship of it.
- Never print a secret. Public APIs only, no credentials in a finding.
- Do not claim a port "works" until a test in our repo shows it.
