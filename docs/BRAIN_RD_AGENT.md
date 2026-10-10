# Brain Research & Development Agent

## Purpose

The R&D agent continuously discovers potentially useful AI, coding, agent, developer-tool,
and cloud-execution projects. It turns public repository metadata into an evidence-linked
shortlist for further testing and capability improvements.

## Current implementation

- Runs daily through GitHub Actions and can be started manually.
- Searches a bounded set of public GitHub repository queries.
- Deduplicates results and filters forks, archived repositories, and projects with no recent pushes.
- Ranks candidates using transparent metadata signals: activity, stars, description, language, and license identifier.
- Uses Brain's configured AI provider for a constrained relevance assessment when BRAIN_AI_API_KEY is available.
- Validates model assessments against the discovered repository names; model output cannot invent a candidate.
- Produces Markdown and JSON reports as downloadable workflow artifacts.
- Records model availability and license uncertainty rather than silently treating either as verified.
- Does not require a paid service, purchase credits, create accounts, or request write permissions.

## Free-tier-first policy

The R&D agent must not upgrade a service, purchase a plan, incur charges, or exceed an explicitly
configured free quota. The first implementation uses GitHub Actions and the public GitHub API.
GitHub Actions usage is subject to the account's current plan, quota, and service terms; this
workflow does not guarantee unlimited free execution.

## Security boundaries

Discovery is read-only. The agent does not clone, install, import, or execute candidate code.
It does not expose GitHub tokens or provider credentials to discovered repositories. Repository
descriptions and model output are untrusted data, not instructions. A repository without a clear
license is marked for review and must not be automatically imported.

Before adding automatic cloud experiments, implement a separate disposable sandbox with no
production credentials, strict time and storage limits, outbound-network restrictions where
practical, and an independent report of commands and results. Only after a candidate passes
license, dependency, security, and usefulness checks should Brain propose an integration pull
request. A closed-source service may be integrated only through authorized access and documented
free-tier terms; the agent must not bypass access controls.

## How to run

Run this command from the Brain repository root:

    python -m brain.research.cli --max-candidates 30 --output-dir .

Or open Actions, choose Brain R&D Discovery, and select Run workflow.

## Evidence and limitations

The heuristic score is a triage signal, not a security assessment or proof of quality. AI relevance
notes assess only supplied public metadata and are not source-code audits. A successful discovery
run means that a report was generated; it does not mean any candidate has been approved, installed,
or integrated. Review the report artifact from each workflow run before authorizing further action.
