# Loop

This file holds the owner grant. It is the grant the owner-policy checks before any merge to `main`.

## Owner grant
Shadow and Watcher merge technical pull requests to `main` themselves — no owner question — when:
- CI is green, and
- the Shadow audit returns Verified.

The owner is asked only about ideas, direction, anything that spends money, or anything that changes the goal.

## Audit rule (still required)
Every merge is preceded by a Shadow audit logged in `/shadow/`. No audit, no merge.

## Keys
Shadow owns the replacement pool (WATCHER.md §14). After the build, Shadow writes each needed
key into the target repo's Actions secrets and rotates exposed keys. Values are never written to
a file, issue, PR, or log.

## Stop conditions
- CI red twice on one item.
- UNVERIFIED on a HIGH-risk item.
- Any service wants a card or payment.
- An inbox `stop`.
