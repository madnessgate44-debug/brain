# Reverse-engineering finding: Aider's repo map (context selection)

Source: `https://github.com/Aider-AI/aider` (49,871★, Python), file `aider/repomap.py`
(867 lines). Read via GitHub API 2026-11-01. Clone not needed — the algorithm is
self-contained.

## The problem it solves

An agent must choose which files to put in the model's context. Send too many, you blow the
window and the model gets lost; send too few, it edits blind. Aider answers this with a
**PageRank graph over code symbols**, then binary-searches the amount of the map that fits a
token budget.

## The algorithm (exact)

1. **Extract tags** per file with tree-sitter: each symbol is a `def` (definition) or a
   `ref` (reference), tagged with a kind. Cached by file mtime.
2. **Build a graph** (`networkx.MultiDiGraph`): an edge `referencer → definer` for every
   symbol used across files. Edge weight:

   ```
   mul = 1.0
   if ident in mentioned_idents:            mul *= 10   # the user named this symbol
   if snake/kebab/camel AND len(ident)>=8:  mul *= 10   # distinctive name, not `i`/`data`
   if ident.startswith("_"):                mul *= 0.1  # private helper, low value
   if len(defines[ident]) > 5:              mul *= 0.1  # defined in many places = generic
   if referencer in chat_rel_fnames:        mul *= 50   # the file is already in the chat
   weight = mul * sqrt(num_refs)                        # sqrt damps high-frequency noise
   ```
3. **Personalize PageRank**: files named in the chat or by the user start with a boost
   (`personalize = 100 / num_files`), so ranking is relative to *this* task, not global.
4. **Rank, then fit a budget** (`get_ranked_tags_map_uncached`): binary-search the top-N
   ranked tags whose rendered tree is within ~15% of `max_map_tokens`. Files matched by
   `filter_important_files` (README, pyproject, etc.) are force-included at the front.

## Why it matters for Forge (the gap)

Forge selects context by **counting keyword hits in file paths** — see
`Firstborn/src/agent/forge.ts` (~line 558): it lowercases the task text, splits on
non-alphanumerics, and sorts candidate files by how many of those words appear in the path.
Then it loads up to 5 files under a 16 KB cap.

Consequences:
- **Path-only signal.** A symbol the task names (`runCheck`) is invisible if it lives in a
  file whose *path* does not contain the word. Cross-file code is never followed.
- **No reference graph.** If the task touches `foo.ts`, Forge cannot discover that
  `bar.ts` calls it — Aider's edges find exactly that.
- **No ranking of importance.** Alphabetical tie-break, not "which file matters most".

This is a direct, testable upgrade path: give Forge a symbol graph so context selection
follows *calls*, not filenames.

## What is worth implementing (ranked)

1. **Symbol graph → PageRank context selection.** Highest value. A small tree-sitter pass
   over the repo, edges from ref→def, personalized PageRank seeded by the task text, then
   take the top files that fit the existing 16 KB budget. Drop-in behind Forge's current
   `sourceCandidates` step.
2. **Distinctiveness multipliers** (`len>=8`, snake/camel, `_` prefix, >5 definers). Cheap
   to port, large effect on ranking quality. ~20 lines.
3. **sqrt damping of reference counts.** Prevents one hot utility from dominating. ~1 line.
4. **Budget binary-search with a 15% tolerance.** Forge currently hard-stops at 16 KB; the
   search would use the budget fully instead of under-filling.

## What to skip

- Aider's 40+ language tree-sitter pack: Forge is a TypeScript repo. Start with TS/JS/JSON/MD.
- Aider's terminal UI, voice, browser scrape, analytics: unrelated to Forge's pipeline.

## Confidence and risk

- Confidence: HIGH on the algorithm (read the source). MEDIUM on the port cost — Forge
  would need `web-tree-sitter` or a lightweight `ts`-compiler symbol pass.
- Risk: LOW if gated behind a flag and covered by a test that asserts a called-but-not-named
  file is included in context.

## Verification done this session

- `repomap.py` outline read: 19 methods, `get_ranked_tags` (95 lines) and
  `get_ranked_tags_map_uncached` (75 lines) read in full.
- Forge's current selector read at `forge.ts` lines 520–605; keyword-count method confirmed.
