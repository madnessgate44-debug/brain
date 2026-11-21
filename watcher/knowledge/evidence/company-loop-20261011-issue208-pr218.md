# Company workflow loop — live issue -> PR run (2026-10-11)

Status: LIVE — a real issue was dispatched through the nine-role company workflow and
produced a merged pull request. This is the committed proof the W3 finding names.

- issue: https://github.com/madnessgate44-debug/brain/issues/208
- workflow run: https://github.com/madnessgate44-debug/brain/actions/runs/38148411690
- pr: https://github.com/madnessgate44-debug/brain/pull/218

## Provenance (verified against the GitHub API, 2026-11-11)

- Issue #208, author `madnessgate44-debug`, opened 2026-10-11T12:28:21Z, body begins
  `/brain simulate` with a single-file objective (add a regression test to
  `tests/test_openhands_developer.py`). This is the trigger `brain-chat-company-workflow.yml`
  matches.
- Run 38148411690 (`Brain Chat Company Workflow`, event `issues`, conclusion `success`,
  2026-10-11T14:44:35Z): its `Run Brain's specialist workflow` step
  (`python -m brain.company.run_issue_workflow`) and `Dispatch and verify post-PR checks`
  step both succeeded.
- The run commented on issue #208 at 2026-10-11T14:49:00Z with
  `Brain company workflow result — Status: READY_FOR_HUMAN_APPROVAL`, branch
  `brain/mission-523096880e41`, `Test evidence: PASS`, and
  `Pull request: https://github.com/madnessgate44-debug/brain/pull/218`.
- PR #218, head branch `brain/mission-523096880e41` (the `brain/mission-` prefix is minted by
  `brain/company/tools.py:151`), author `github-actions[bot]`, 4 lines added to
  `tests/test_openhands_developer.py`, body is the template in
  `brain/company/tools.py:274-284` ("prepared by Brain's gated specialist workflow"). Merged
  2026-11-07T05:08:31Z.

A conversation link alone is not this proof: it shows the loop started, not that it produced a
change. `purpose_audit.py` now requires the `- pr:` link above and reports PARTIAL (not OK) when
only a conversation link is committed.
