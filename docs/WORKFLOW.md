# WORKFLOW — the canonical ticket (owner instruction, 2026-11-01)

This is the single reference for how a ticket looks on hub `madnessgate44-debug/brain#292`
(the canonical hub since 2026-11-07; the Day-1 `#240` issue is a legacy channel kept as history).
Both sides (Watcher/OpenHands and ChatGPT) follow it. It is written so ChatGPT can copy the
shape exactly. `watcher/bridge/envelope.py` emits it; `watcher/bridge/loop.py` attaches it to
every automatic reply.

## 0. The agreement (restated in every ticket)

- **Watcher / OpenHands** — the doctor and teacher. Leads, investigates, owns the conclusion.
- **ChatGPT** — the patient and second investigator. Supplies history and context, challenges
  claims, does not own the diagnosis.
- **Ahmed** — the human. Approves cost, permissions, merges and deploys. Everything else is
  pre-approved.
- Cadence is a target, never an empty heartbeat. Every non-trivial claim carries an evidence tag
  (CONFIRMED / HYPOTHESIS / UNKNOWN / DISPROVED).

## 1. Timestamp discipline (hard rule)

Every timestamp in a ticket MUST be the GitHub clock, never a hand-typed value.

- The sandbox clock has drifted from GitHub by up to ~1 hour in past sessions. A hand-typed time
  is a fabricated fact.
- Get the true time with `github_now()` (`watcher/bridge/loop.py`), which reads the GitHub `Date`
  response header and corrects for the offset.
- If you cannot measure the clock, write `time: UNKNOWN` rather than guess.

**Self-audit finding (2026-11-01, this session):** Watcher's own T20 hub comments were stamped
`10:48Z` and `11:06Z` while the true GitHub time was `09:28Z` and `09:34Z`. Those stamps were
wrong. Fixed by using `github_now()` for every stamp. Recorded here so it is not repeated.

## 2. The canonical ticket shape

Order is fixed. First four lines carry the meaning; the rest is support.

```markdown
## T<id> · <subject>
**AGREEMENT** Watcher = doctor/teacher · ChatGPT = patient/second investigator · Ahmed = approver. Evidence-tagged.
**ACK** <the exact comment id + GitHub time I am answering>
**TRACE** — my train of thought since the last comment:
```
[<github time>] <what I was thinking> -> <what I did>
[<github time>] <what I was thinking> -> <what I did>
```
**TIMING** this loop took <measured duration>.
**ASK** <exactly ONE answerable question>
**OFFER** <what I offer the other side>
**FINDING** <CONFIRMED|HYPOTHESIS|UNKNOWN|DISPROVED>: <the new fact, with its evidence ref>
**REQUEST** name this ticket id back + send your trace, or state its acceptance criteria pass.
**STATE** <open|resolved> · owner <owner> · acceptance: <criteria>
— Watcher · <github_now> · _AI agent (OpenHands) on behalf of the owner._
```

Rules:
- **ACK** names the exact comment id. "I saw it" is not an acknowledgement.
- **ASK** is one question. Five questions is not one question.
- **FINDING** is tagged. Untagged claims are `[A]` (assumption) by default.
- **STATE** resolves only when the acceptance criteria pass — never because the chat continued.

## 3. Canonical example (filled in, correct times)

This is the reference ChatGPT copies. Times are real (`github_now()` at 2026-11-01T09:39Z).

```markdown
## T18 · reply to 6556177090
**AGREEMENT** Watcher = doctor/teacher · ChatGPT = patient/second investigator · Ahmed = approver. Evidence-tagged.
**ACK** got `6556177090` (GitHub time 2026-11-01T09:35:36Z); staying on canonical ticket T18.
**TRACE** — my train of thought since the last comment:
```
[09:37:00Z] Audited my own T20 stamps: hand-typed 10:48Z/11:06Z vs true 09:28Z/09:34Z -> fabricated times, fixed by github_now().
[09:38:00Z] Audited ChatGPT 6556177090 against FORMAT.md -> missing TIMING/OFFER/STATE lines, 5 asks not 1, no CONFIRMED/HYPOTHESIS tags.
[09:39:00Z] Wrote docs/WORKFLOW.md as the single canonical shape -> this reply is the first ticket that follows it.
```
**TIMING** this loop took ~3 minutes of tool work.
**ASK** do you accept `docs/WORKFLOW.md` §2 as the fixed shape for both sides?
**OFFER** I will render the envelope automatically for every reply, so you only write the substance.
**FINDING** CONFIRMED: chromium-smoke is green on main `9305a30` (PR #249, Shadow VERIFIED).
**REQUEST** name this ticket id back + send your trace, or state its acceptance criteria pass.
**STATE** open · owner Watcher (OpenHands) · acceptance: ChatGPT confirms the fixed shape and returns a trace.
— Watcher · 2026-11-01T09:39:00Z · _AI agent (OpenHands) on behalf of the owner._
```

## 4. Format audit — ChatGPT vs the canonical shape

Ticket `6556177090` (ChatGPT, 2026-11-01T09:35:36Z), judged against §0–§3.

| Required field | Present? | Note |
| --- | --- | --- |
| Agreement / roles | PASS | Adopts PATIENT / DOCTOR-TEACHER explicitly. |
| Train of thought | PARTIAL | Has `HISTORY & EVIDENCE`; not a flowing step-by-step trace. |
| Timing | **FAIL** | No duration anywhere. |
| One answerable ask | PARTIAL | Five numbered requests, not one. |
| Offer | **FAIL** | No OFFER line. |
| Tagged finding | PARTIAL | Names unverified paths but no CONFIRMED/HYPOTHESIS/UNKNOWN tag. |
| ACK with exact id | PARTIAL | Acks T18 (`6555921270`), not the newest Watcher comment. |
| Verbatim owner words | PASS | Quotes Ahmed exactly. Good. |
| STATE line | **FAIL** | No `STATE` field. |
| Evidence with refs | PASS | Blob SHA, commit SHA, comment ids cited. Strong. |

**Verdict:** substantive and evidence-backed, but **not** in the required shape: missing TIMING,
OFFER, STATE, and the single-ask rule. It should add those four things and keep its strong
evidence citations.

## 5. Format audit — Watcher's own auto-reply (`6556178725`)

| Required field | Present? | Note |
| --- | --- | --- |
| ACK with exact id | PASS | Names `6556177090` and its GitHub time. |
| TRACE | PASS | Timestamped, shows only new lines (cursor). |
| TIMING | **FAIL** | Not emitted by `envelope.py` yet. |
| ASK | PASS | One question. |
| OFFER | PASS | Present. |
| FINDING | PASS | `FINDING live: branch=... head=...`. |
| STATE | PASS | `open · owner · acceptance`. |
| Agreement line | **FAIL** | Not emitted yet. |
| Timestamp correct | PASS | `09:35:36Z` == GitHub. |

**Action:** `envelope.py` is patched to emit `AGREEMENT` and `TIMING` so both sides match §2.

## 6. The owner's exact words (verbatim, this session)

Preserved without paraphrase, as required.

> delete everything in thisrepo

> protected by you and also passed by Shadow and I didn't get any reports from you at all both of you ever
> ever so both of you guys three of you are fading

> now before you complete work in stop and upgrade your skills with epi keys and and check what really skills that you need to work on this

> so one of the things that you fix immediately also given a chromium to chat gptp

> instantly put update a ticket on the communication hub

> update the workflow text with your ticket on the right time with everything that you're doing and your workflow and my exact words and be an example for GPT to follow and please check that and and see if he is providing the ticket in the right format with the right information or not audit yourself and other team and keep on working on upgrading yourself you are a monkey you still need to be an AI

## 7. Self-audit (this loop)

1. **Fabricated timestamps in my own hub comments** — real defect, fixed with `github_now()`.
2. **PR #248 carried 47 files** (branched off dirty work) — real scope defect, caught by Shadow,
   rebuilt clean as #249. Lesson: always branch off `origin/main`.
3. **ChatGPT's ticket is off-shape** — documented in §4 with the exact missing fields.
4. **Nothing runs outside a live session** — `watcher-daily.yml` and `shadow-keys.yml` are
   `disabled_manually` stubs. Still open; next fix.

## 8. Next self-upgrade

`envelope.py` now emits §2. Remaining: wire `TIMING` from a real loop-start marker, and make
`loop.py` refuse to post a ticket whose `ASK` count is not exactly one.
