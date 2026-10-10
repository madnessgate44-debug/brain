# Brain free-first architecture and browser plan

**Decision:** Brain must have no mandatory paid hosting, browser, or AI dependency. Paid services are optional escape hatches, not the default runtime.

## Requirements and acceptance criteria

1. **$0 mandatory infrastructure:** no paid Render service, persistent disk, browser subscription, or metered automation is required for the baseline workflow.
2. **Phone-controlled intake:** the owner can create a GitHub issue from the Samsung phone and start a bounded task with a marker.
3. **Real browser execution:** Playwright/Chromium runs on a GitHub-hosted Linux runner and produces an explicit plan, step results, screenshots when requested, and a report.
4. **Evidence before claims:** only completed browser actions count as evidence. A model plan, queued workflow, or successful install is not proof the research objective was achieved.
5. **Approval gate:** a plan containing clicks, typing, pressing keys, or selecting form values is not executed by the natural-language research path. It returns the exact plan for review.
6. **Safe scope:** public, non-sensitive pages only. No private accounts, credentials, session-cookie reuse, CAPTCHA bypass, purchases, account changes, or attempts to evade site restrictions.
7. **No merge or deploy:** this branch is a reviewable implementation. It must not merge itself or provision infrastructure.
8. **Recoverable records:** the issue comment and workflow artifact provide a result trail. Artifacts have limited retention and are not the permanent mission database.

## Free execution architecture

- **Control plane:** GitHub Issues. The marker /brain browse starts a public read-only research task. Explicit browser tasks that may mutate a website use the authenticated FastAPI /browser/tasks endpoint; that API currently has no public persistent deployment URL.
- **Runner:** GitHub Actions standard Linux runner plus open-source Playwright/Chromium. GitHub's current documentation says standard runners are free and unlimited for public repositories; private repositories use plan allowances. Confirm limits at https://docs.github.com/en/billing/concepts/product-billing/github-actions.
- **Browser:** Playwright opens public websites, inspects rendered page text, follows a bounded plan, and can capture screenshots. It runs only for the duration of a workflow; it is not an always-on remote desktop.
- **Planning:** the existing OpenAI-compatible adapter calls the configured Gemini endpoint using a secret stored in GitHub Actions. Gemini's free quota can be exhausted or changed. If no key or quota is available, Brain must fail explicitly; it must not claim the AI planner ran.
- **Durable evidence:** GitHub issue comments provide the result summary; the workflow artifact contains the full plan/report and is retained for 7 days. For durable records, preserve useful findings in a committed report or pull request after review. Do not treat runner filesystem or SQLite as persistent.
- **Optional public-web retrieval:** the TinyFish account currently reports Search at $0/query and Fetch at $0/URL. Those are useful for research during the current pricing window, but Brain must not depend on them. Its baseline browser runner uses Playwright. The current wallet reports $9.888, with auto-reload unconfigured; do not spend on routine research.

## TinyFish budget policy

Use the currently available no-cost Search/Fetch methods for source discovery where useful. Do not call the metered TinyFish Browser or Agent just to repeat a task the free runner can perform. Reserve the existing wallet only for a specifically identified, high-value dynamic-browser test that cannot be completed with Playwright or free retrieval. Before any such test, define the question it must answer, use a short step/time bound, record the returned cost, and stop if the cost is unclear. Do not top up or enable auto-reload.

The wallet rates are account-specific and may change. Check the live wallet before any metered run. A balance is not permission to spend it indiscriminately.

## Natural-language public research

Create an issue in this repository with /brain browse and one JSON block. Example:

    {
      "title": "Inspect official browser documentation",
      "objective": "Summarize the official guidance on retries and cite the page sections",
      "start_url": "https://playwright.dev/docs/test-retries",
      "allowed_domains": ["playwright.dev"]
    }

The allowed_domains list may be omitted; when omitted, the start URL's host is the default. Keep the list narrow. The owner-only workflow asks the existing model adapter to create a bounded plan, pins its first navigation to the supplied URL, preflights allowed destinations, then executes only read-only actions. It records the exact plan, action results, and optional screenshots.

If the plan contains a mutating action, execution stops and the report returns the proposed action list. The owner must inspect that exact list and separately submit an explicitly approved task to the authenticated /browser/tasks API before a mutation can run. This issue workflow does not execute write actions. Both the issue author and the actor who opens/edits the issue must be the repository owner. Editing an issue triggers a new run, so an issue should not be edited casually while a workflow is active.

## Capability boundary: what is and is not solved

| Capability | Current status |
|---|---|
| Owner starts tasks from a phone | Supported through GitHub Issues |
| Rendered public pages in Chromium | Implemented; CI includes a real Chromium smoke test |
| Natural-language plan generation | Implemented using configured Gemini-compatible API; free quota not guaranteed |
| Read-only public browsing | Implemented in the new issue workflow; end-to-end run still required |
| Screenshot and structured action report | Implemented; live issue-workflow evidence still required |
| Browser tabs | New/list/switch/close tab actions implemented with public-URL checks; end-to-end workflow still to verify |\n| Public-link extraction | Implemented with deduplication and URL policy; live research accuracy still to benchmark |\n| Multi-site research | Possible when each destination is in allowed_domains; not yet benchmarked |
| Logged-in sites or personal ChatGPT/Gemini sessions | Not supported by this free workflow |
| Always-on FastAPI API with persistent SQLite | Not provided by GitHub Actions; would need a different free persistent architecture or paid hosting |
| Guaranteed unlimited model calls or compute | Impossible to promise on free tiers |
| Proven performance better than TinyFish overall | Not yet established; requires a repeatable benchmark |

## Benchmark to justify “better than TinyFish”

For representative public research tasks, record:
- objective completion rate, with source URLs and quoted evidence;
- number of actions, retries, timeouts, and blocked destinations;
- whether screenshots and page text support each conclusion;
- elapsed time and marginal cost;
- whether any action exceeded its approved scope.

Do not claim Brain is better until the same task set has been run through both systems and the results compared. The intended advantage is not one clever browser call; it is the combination of task planning, explicit permissions, evidence trails, bounded recovery, repository workflows, and a $0 mandatory baseline.

## Current change boundary

This branch removes the paid Render blueprint and its paid-deployment guide. It does not create a Render service, deploy anything, merge itself, or change any existing secret. The FastAPI backend still has no public persistent URL. The new workflow is a free remote execution path, not a substitute for a durable always-on API.
