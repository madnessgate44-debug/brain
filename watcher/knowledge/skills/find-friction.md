# Skill: Find the friction (do not wait to be told)

## When to use
At the start of every Watcher cycle, and whenever the owner repeats himself, argues, or asks
"are you done?". Use it before reporting anything. This is WATCHER.md §16.5 as a repeatable
method.

## The signals (all from the record — never from our own opinion)
1. **The owner's words.** `watcher/bridge/owner-transcript.md` is his verbatim trail. Frustration
   language, and the same topic raised more than once, is the diagnosis.
2. **Churn without close.** Many commits in a day, few merges, many branches = motion, not
   progress. `git log`, `git branch`.
3. **Report-only commits.** Commits that change only docs. We look busy and ship nothing.
4. **Presence vs depth.** A feature that exists but does not cover the whole app.
   `purpose_audit.py`.

## The method
1. Run `python3 watcher/knowledge/tools/friction.py`. Read the findings, not the summary.
2. For every finding, find the **cause** in the code or the record, not the symptom in the
   message. "The owner says 'pretend'" is a symptom; "the report listed promises and no
   artifacts" is the cause.
3. Act. A finding you do not close is a failure, not a finding.
4. Re-run the tool. If the same signal is still there next cycle, the fix did not work.

## The rule
The owner is the external signal. When he repeats himself, we already failed once. Reading his
own words is how we catch it before he has to say it again.

## What a false pass looks like (do not do this)
- Reporting "N open issues" instead of the cause and the fix.
- Marking OK when the evidence is a document we wrote ourselves.
- A tool that flags a phrase out of context ("I do not pretend" read as "pretend").
