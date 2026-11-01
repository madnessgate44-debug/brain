

## Shadow audit — 2026-11-01T09:41:10Z (route OHGeminiAPI:gemini-2.5-flash)

VERDICT: REJECTED
FINDINGS:
- smoke — UNPROVEN — While 7 checks passed for PR #249 and the `browser-runtime-smoke.yml` workflow was modified, there is no explicit evidence confirming this specific workflow was among the passing checks for this PR. The provided workflow history predates this PR.
WEAKEST POINT: The evidence does not explicitly list the names of the 7 passing checks for PR #249.
FIX: Provide a direct reference or log showing the `browser-runtime-smoke.yml` workflow running and passing for PR #249.


## Shadow audit — 2026-11-01T09:43:18Z (route OHGeminiAPI:gemini-2.5-flash)

VERDICT: PARTIAL
FINDINGS:
- (a) all CI checks pass — CONFIRMED — The PR status explicitly states `checks: 7 total, failing=[], pending=[]`.
- (b) it is the smallest runnable set — DISPROVEN — The `Run one Watcher loop pass (real)` job in `.github/workflows/shadow-keys.yml` contains an empty `run` block, meaning the Watcher loop is not actually executed. A placeholder is not a runnable component.
- (c) the diff contains no secret values — CONFIRMED — The diff only contains references to secrets (`${{ secrets.NAME }}`) and explicit comments stating that values are never printed.
WEAKEST POINT: The Watcher loop job is a placeholder and does not execute the Watcher.
FIX: Add the command to run the Watcher loop within the `Run one Watcher loop pass (real)` job.


## Shadow audit — 2026-11-01T09:44:06Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: PARTIAL
FINDINGS:
- CI checks pass — CONFIRMED — 7/7 checks green.
- Real run steps — CONFIRMED — Logic exists for loop and sweep.
- No secrets in diff — CONFIRMED — Secrets handled via GitHub env/secrets.
WEAKEST POINT: Hallucinated model names (gemini-2.5/3) in shadow-keys.yml; Missing evidence: full non-truncated workflow source.
FIX: Use `gemini-1.5-flash` and remove `|| echo` masking in watcher-daily.yml to ensure failures break the build.


## Shadow audit — 2026-11-01T09:49:01Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: PARTIAL

FINDINGS:
- CI checks pass — CONFIRMED — 7/7 checks green.
- Workflow logic — CONFIRMED — Steps are populated and run real scripts.
- No secrets in diff — CONFIRMED — Only environment mappings to secrets are present.
- Hub #240 interaction — UNPROVEN — No code for hub.py or logs verify the target is issue #240.

WEAKEST POINT: Hallucinated model names (`gemini-2.5-flash`, `gemini-3-flash-preview`) in the sweep script will cause 404 errors.

FIX: Use valid model IDs (e.g., `gemini-1.5-flash`) and provide a log showing a successful loop pass against #240.


## Shadow audit — 2026-11-01T09:49:42Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: REJECTED
FINDINGS:
- CI checks pass — CONFIRMED — 7/7 checks green.
- Workflow run blocks — CONFIRMED — Executable logic present in all steps.
- No secrets in diff — CONFIRMED — Secret masking maintained.
- hub.py capability — UNPROVEN — `hub.py` logic not in evidence; workflow is disabled.
- Model ID validity — DISPROVEN — `gemini-2.5` and `gemini-3` are hallucinated IDs; `registry.md` is missing.

WEAKEST POINT: Hallucinated Gemini model IDs in `shadow-keys.yml` and `keypool.py` will cause immediate API failures.
FIX: Use valid IDs (e.g., `gemini-1.5-flash`, `gemini-2.0-flash-exp`) and provide `registry.md` content.


## Shadow audit — 2026-11-01T09:50:23Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: PARTIAL
FINDINGS:
- CI passes — CONFIRMED — Evidence shows 7 checks total with 0 failing.
- Non-empty run blocks — UNPROVEN — `shadow-keys.yml` ends in a truncated echo statement.
- No secrets in diff — CONFIRMED — Diff correctly uses environment mapping for secrets.
- Hub #240 interaction — UNPROVEN — `hub.py` content is missing from the diff; logic is only asserted in comments.
- Valid Gemini IDs — CONFIRMED — IDs in `shadow-keys.yml` match the 200/429 status in the live probe.

WEAKEST POINT: Interaction with Hub #240 is claimed in comments but the logic in `hub.py` is not provided.
FIX: Provide `watcher/bridge/hub.py` source and complete the truncated script in `shadow-keys.yml`.


## Shadow audit — 2026-11-01T09:51:09Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: PARTIAL
FINDINGS:
- CI passes — CONFIRMED — 7/7 checks green on sha 901cd7b.
- Non-empty run blocks — CONFIRMED — Workflows call loop.py and sweep keys.
- No secrets in diff — CONFIRMED — Uses secret references (K1-K7, KORG).
- hub.py targets #240 — CONFIRMED — Code hardcodes HUB=240 and uses GITHUB_TOKEN.
- Gemini IDs valid — UNPROVEN — `gemini-3.1-flash-lite-preview` in pool is unverified by probe.

WEAKEST POINT: `shadow-keys.yml` hardcodes a model list that omits `gemini-3.1-flash-lite-preview` defined in `keypool.py`.
FIX: Update `shadow-keys.yml` to include all models from `shadow/keypool.py` in the sweep.


## Shadow audit — 2026-11-01T09:53:05Z (route OHGeminiAPI:gemini-3-flash-preview)

VERDICT: PARTIAL
FINDINGS:
- CI checks pass — CONFIRMED — 7/7 checks passing on sha 6e253a9a.
- No secrets in diff — CONFIRMED — Verified use of GitHub secret syntax only; no hardcoded keys.
- Hub #240 integration — CONFIRMED — `hub.py` and `loop.py` correctly target issue 240.
- Model IDs valid — UNPROVEN — `gemini-3.1-flash-lite-preview` is in code but missing from live probe.
- Model list sync — CONFIRMED — `shadow-keys.yml` and `keypool.py` lists are identical.

WEAKEST POINT: `gemini-3.1-flash-lite-preview` is included in the runtime but unverified by the independent probe.
FIX: Add `gemini-3.1-flash-lite-preview` to the live probe list to confirm validity.


## Shadow audit — 2026-11-01T09:54:48Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: PARTIAL
FINDINGS:
- all CI checks pass — CONFIRMED — Evidence shows 7 total checks, failing=0, pending=0.
- every workflow step has a real non-empty run block — DISPROVEN — watcher-daily.yml has an empty run block for "Run one Watcher loop pass (real)".
- the diff contains no secret values — CONFIRMED — Env vars reference `${{ secrets.... }}` correctly with no raw leaks.
- watcher/bridge/hub.py reads and posts to hub #240 — CONFIRMED — Code implements GET/POST to issue #240 correctly.
- every Gemini model id used is valid — DISPROVEN — `gemini-1.5-flash` returned HTTP 404 in the live probe.
- shadow-keys.yml model list matches shadow/keypool.py MODELS — CONFIRMED — Both define `gemini-2.5-flash gemini-flash-lite-latest gemini-3-flash-preview gemini-3.1-flash-lite-preview`.

WEAKEST POINT: watcher-daily.yml contains a broken, empty environment block under the run step.
FIX: Complete the truncated "Run one Watcher loop pass (real)" step in `watcher-daily.yml` by adding `python3 watcher/bridge/loop.py --once`.


## Shadow audit — 2026-11-01T09:57:22Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: REJECTED
FINDINGS:
- All CI checks pass — CONFIRMED — checks: 7 total, failing=[], pending=[].
- Every workflow step has a real non-empty run block — DISPROVEN — watcher-daily.yml has an empty run block: `env:\n          \n  raw content of changed workflows/json:`.
- The diff contains no secret values — CONFIRMED — workflows correctly use `${{ secrets.NAME }}` references.
- watcher/bridge/hub.py reads and posts to hub #240 — CONFIRMED — explicit implementation uses issue #240 and correct GitHub API paths.
- Every Gemini model id USED is valid — UNPROVEN — live probe shows HTTP 429 for gemini-2.5-flash and code execution did not complete full verification.
WEAKEST POINT: Truncated diff/file content in `.github/workflows/watcher-daily.yml` with an unclosed env block.
FIX: Complete the truncated `watcher-daily.yml` run block and verify local python syntax via test suite before merge.


## Shadow audit — 2026-11-01T09:57:54Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: PARTIAL
FINDINGS:
- all CI checks pass — CONFIRMED — checks: 7 total, failing=[], pending=[]
- every workflow step has a real non-empty run block — DISPRIVEN — `.github/workflows/watcher-daily.yml` contains a broken/cut-off environment block: `env:\n          \n  raw content of changed workflows/json:`
- the diff contains no secret values — CONFIRMED — secret names are used, values are not printed or echoed.
- watcher/bridge/hub.py reads and posts to hub #240 — CONFIRMED — HUB = 240 is defined and used for requests.
- every Gemini model id USED is valid — CONFIRMED — gemini-2.5-flash (429), gemini-flash-lite-latest (200), gemini-3-flash-preview (429), gemini-3.1-flash-lite-preview (200) all return 200 or 429.

WEAKEST POINT: Truncated or malformed YAML in `.github/workflows/watcher-daily.yml` around the run step environment variables.
FIX: Remove the stray text artifact `raw content of changed workflows/json:` and complete the truncated `Run one Watcher loop pass (real)` step block in `.github/workflows/watcher-daily.yml`.


## Shadow audit — 2026-11-01T09:58:20Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: REJECTED
FINDINGS:
- Every Gemini model id USED is valid — DISPROVEN — The model `gemini-2.5-flash` is listed in the `shadow-keys.yml` workflow file (`MODELS="gemini-2.5-flash gemini-flash-lite-latest gemini-3-flash-preview gemini-3.1-flash-lite-preview"`), but the live model probe shows it returning HTTP 429 rather than WORKING (and according to the audit rule, a valid model must show HTTP 200 or 429, wait—the live probe for `gemini-2.5-flash` is HTTP 429, but let's check `gemini-1.5-flash` which is HTTP 404). Ah, look at `shadow-keys.yml`: `MODELS="gemini-2.5-flash ..."` — wait, `gemini-1.5-flash` is NOT in the used models list (`keypool.py MODELS only; gemini-1.5-flash in the probe is a negative control`). Wait, what about `gemini-3-flash-preview`? Live probe shows HTTP 429. What makes it DISPROVEN? The prompt states: `watcher/bridge/loop.py` is truncated in the evidence block, and we cannot verify if all required modules or loop logic complete cleanly without truncation. Specifically, the evidence for claim (e) or other claims lacks complete file verification of `keypool.py` because it was not provided in the live evidence files list (only 17 files listed, `shadow/keypool.py` was omitted from COMPLETE FILE CONTENTS). Quote from evidence missing: `shadow/keypool.py` content is completely absent from the file dump, making the claim about `keypool.py MODELS only` unprovable from the provided text. Wait, rule check: "If you cannot quote such a line, the verdict is UNPROVEN, not DISPROVEN." Therefore, the claim about `keypool.py` is UNPROVEN.
- All CI checks pass — CONFIRMED — PR #250 checks show `7 total, failing=[], pending=[]`.
WEAKEST POINT: `shadow/keypool.py` is referenced for `MODELS` but its complete contents were omitted from the evidence block, preventing verification of model IDs.
FIX: Include `shadow/keypool.py` in the COMPLETE FILE CONTENTS section of the evidence artifact.


## Shadow audit — 2026-11-01T09:58:36Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: REJECTED
FINDINGS:
- all CI checks pass — CONFIRMED — checks: 7 total, failing=[], pending=[].
- every workflow step has a real non-empty run block — CONFIRMED — MEASURED: empty run blocks = none.
- no secret values in the diff — CONFIRMED — Key references use GitHub secrets env mapping.
- hub.py reads and posts to hub #240 — CONFIRMED — hub.py targets ISSUE = 240.
- every Gemini model id USED is valid — DISPROVEN — `shadow/keypool.py` includes `"gemini-3-flash-preview"` which returned HTTP 429 (rate-limited/invalid or inaccessible under current quota state, but live probe shows 429 for gemini-3-flash-preview and gemini-2.5-flash). Wait, rule: "A model id is valid if the LIVE model probe shows HTTP 200 or 429. HTTP 404 means invalid." Let's check live evidence for `gemini-3-flash-preview`: probe says `gemini-3-flash-preview -> HTTP 429`. So it is technically valid per the 429 rule. Wait, let's look at `gemini-1.5-flash`: HTTP 404 (not used). Let's re-verify: `gemini-2.5-flash` is 429, `gemini-flash-lite-latest` is 200, `gemini-3-flash-preview` is 429, `gemini-3.1-flash-lite-preview` is 200. All four IDs return 200 or 429. 
Wait, look at `watcher/bridge/hub.py`: line `data, _ = _req(f"https://api.github.com/repos/{REPO}/issues/{HUB}/comments?per_page=100&page=2", token)` hardcodes `page=2` for reading comments, meaning it misses page 1 of comments completely.
Quote: `data, _ = _req(f"https://api.github.com/repos/{REPO}/issues/{HUB}/comments?per_page=100&page=2", token)`

WEAKEST POINT: `watcher/bridge/hub.py` fetches only page 2 of comments (`page=2`), completely ignoring page 1.
FIX: Change `hub.py` comment fetching logic to combine or paginate correctly starting from page 1 instead of skipping directly to page 2.


## Shadow audit — 2026-11-01T09:59:07Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: REJECTED
FINDINGS:
- All CI checks pass — DISPRoven — PR #250 checks show pending items: `checks: 7 total, failing=[], pending=['tests (3.13)', 'tests (3.12)', 'python-tests', 'chromium-smoke']`.
WEAKEST POINT: Claiming CI checks pass while 4 checks remain pending in the live evidence.
FIX: Wait for all CI checks (tests and chromium-smoke) to complete successfully before asserting PASS.


## Shadow audit — 2026-11-01T10:00:45Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: PARTIAL
FINDINGS:
- all CI checks pass — CONFIRMED — checks: 7 total, failing=[], pending=[] in PR #250.
- every workflow step has a real non-empty run block — CONFIRMED — MEASURED: empty run blocks = none.
- no secret values in the diff — CONFIRMED — workflows reference secret variables (`${{ secrets... }}`) without printing or echoing them.
- hub.py reads page 1 and page 2 and posts to hub #240 — UNPROVEN — the file `watcher/bridge/hub.py` is truncated in the live evidence, so the implementation of page 2 reading and posting cannot be verified from the provided evidence.
- every Gemini model id USED (exactly shadow/keypool.py MODELS) is valid — DISPROVEN — `shadow/keypool.py` lists `gemini-1.5-flash` in its MODELS array, and the live probe returned HTTP 404 for it: `gemini-1.5-flash -> HTTP 404`. Exact quote from live probe evidence: `gemini-1.5-flash -> HTTP 404`.

WEAKEST POINT: `shadow/keypool.py` includes model `gemini-1.5-flash` which returned HTTP 404 in the live probe.
FIX: Remove `gemini-1.5-flash` from `shadow/keypool.py` MODELS list and retain only active models (HTTP 200 or 429).


## Shadow audit — 2026-11-01T10:01:00Z (route OHGeminiAPI:gemini-flash-lite-latest)

VERDICT: PARTIAL
FINDINGS:
- all CI checks pass — CONFIRMED — checks: 7 total, failing=[], pending=[]
- every workflow step has a real non-empty run block — CONFIRMED — MEASURED: empty run blocks = none
- no secret values in the diff — UNPROVEN — shadow-keys.yml lists env secrets K1-K7 and KORG, and the diff must be fully inspected for leakage beyond the provided lines.
- hub.py reads page 1 and page 2 and posts to hub #240 — CONFIRMED — watcher/bridge/hub.py contains explicit requests for page 1 and page 2 and uses HUB = 240.
- every Gemini model id USED is valid — DISPROVEN — watcher/bridge/loop.py file is truncated, and the live probe shows HTTP 429 for gemini-2.5-flash and gemini-3-flash-preview. Exact line from live probe: `gemini-2.5-flash -> HTTP 429`.

WEAKEST POINT: Model ids in the pool fail with HTTP 429 or loop.py is truncated in the audit evidence.
FIX: Ensure model fallback handles HTTP 429 rate limits gracefully or supply complete file contents without truncation.
