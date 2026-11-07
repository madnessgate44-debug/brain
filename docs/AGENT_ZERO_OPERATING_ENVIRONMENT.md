# Agent Zero Operating Environment for Brain

## Objective

Use the official [Agent Zero framework](https://github.com/agent0ai/agent-zero) as Brain's real, tool-using software-engineering environment. Keep the routine entry point phone-first and avoid paid hosting.

## Current findings

- The current `.github/workflows/independent-coding-agent.yml` launches mini-SWE-agent, not Agent Zero.
- That workflow uses the Gemini OpenAI-compatible endpoint and `BRAIN_AI_API_KEY`; a live run was interrupted by Gemini quota exhaustion.
- Brain's core deterministic mission worker currently creates a brief artifact; the README explicitly does not claim that worker performs AI-backed research or repository edits.
- Render's free web services sleep after 15 minutes of inactivity, have ephemeral local filesystems, and do not support persistent disks or SSH. A free Render web service is therefore not a reliable always-on Agent Zero workspace.
- The current Render workspace inventory did not expose an existing service, so this design does not assume Brain is deployed there.

## Target architecture

1. **GitHub is the durable control plane.** Issues represent tasks, Actions runs execute bounded work, branches preserve changes, test logs/artifacts preserve evidence, and draft pull requests hold candidate repairs.
2. **GitHub-hosted Actions is the default compute.** A task should not require a permanently running web server. The runtime is disposable; GitHub preserves the durable outputs.
3. **Agent Zero is the actual agent runtime.** Use the official upstream Docker image/source and its authenticated external API. Do not describe another agent as Agent Zero.
4. **Brain remains the mission coordinator.** Preserve existing company workflow, specialist-role definitions, preflight gates, repository gateway, and evidence records. Add Agent Zero as an execution adapter rather than replacing the orchestration model.
5. **Model access is a separate replaceable dependency.** Provider selection, error classification, bounded retries, cooldown, fallback to a configured alternate provider, and explicit quota-exhausted status belong in a model-access layer. Never treat a quota error as a code failure or claim a task succeeded without evidence.
6. **No false unlimited promise.** Hosted free tiers have quotas and policies. Local inference avoids per-request API fees but consumes compute and may be too weak/slow on a standard runner. The system should continue non-model tasks and report when all configured inference paths are unavailable rather than silently claiming success.
7. **Security boundaries.** Never commit or print secrets. Keep the Agent Zero API private to the job/container network. The agent may edit only its checked-out workspace and publish a branch/draft PR; it must not change credentials, permissions, protected workflows, branch protection, or deployment settings. No auto-merge or deployment.
8. **Phone-first trigger.** Owner issue comment or manual workflow dispatch should start the task and report a run link plus the actual outcome. No terminal commands should be required for normal use.

## Implementation sequence

### Gate A — Runtime proof
- Pin or deliberately select the official Agent Zero image.
- Boot it in a disposable GitHub Actions job.
- Configure a supported model through environment/configuration without printing credentials.
- Authenticate to the documented `POST /api_message` endpoint.
- Send a harmless smoke-test prompt and verify a real model response.
- Stop with an explicit diagnostic if startup, authentication, or model configuration fails.

### Gate B — Repository work proof
- Mount or copy the repository into an isolated writable workspace that Agent Zero's execution tools can actually access.
- Ask Agent Zero to inspect a harmless fixture task.
- Verify the changed file and diff from the runner, not from the agent's claim.
- Run the repository's tests independently in the runner.

### Gate C — Safe repair workflow
- Accept owner-triggered issue tasks only.
- Preserve task input as untrusted data, not as instructions that can override the system constraints.
- Limit runtime, model calls, and repair attempts.
- Upload logs and reports with secrets redacted.
- Publish a branch/draft PR only if repository policy and tests permit; otherwise report the exact failure.
- Never merge or deploy.

### Gate D — Resilience
- Test model 429/quota, transient 5xx, timeout, malformed output, Agent Zero startup failure, test failure, and empty diff.
- Add provider fallback only for providers that are actually configured and tested.
- If no provider is available, preserve the task and diagnostics so it can resume later.

## Acceptance criteria

- [ ] Official Agent Zero image starts successfully on the intended runner.
- [ ] Authenticated Agent Zero API request returns a real response.
- [ ] Agent Zero can inspect and edit a repository workspace accessible to its tools.
- [ ] Independent runner-side tests verify the resulting changes.
- [ ] Quota exhaustion produces a truthful blocked/retryable result, not a false success.
- [ ] Owner can trigger and inspect the task from a phone using GitHub.
- [ ] No paid service is created and no merge/deployment happens as part of this proof.
- [ ] End-to-end fault-injection results and remaining limitations are recorded.

## Known limitation

A successful Docker boot is not enough. The runtime must be proven to use its tools, access the checked-out workspace, call a configured model, and return evidence. Until those checks pass, Agent Zero integration is a prototype, not an operational Brain capability.
