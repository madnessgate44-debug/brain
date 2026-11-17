#!/usr/bin/env python3
"""Purpose audit: does the code do what the app claims it does? (WATCHER.md §16.5)

This is the audit the Watcher should run first. It does not ask "is there a feature?".
It asks "does the running code fulfil the app's stated purpose?" — and it separates a
claim that is implemented from one that is only reachable from tests (a dead path).

Reads watcher/knowledge/purpose.md (claim, probe regex, path hint), scans brain/, and
reports per claim:
  OK          the probe matches production code (file:line shown)
  UNTESTED    it matches only test code, so it is not proven to run in production
  MISSING     no match anywhere — the app claims something it does not have

    python3 purpose_audit.py [--root .] [--purpose watcher/knowledge/purpose.md]
                             [--out watcher/knowledge/audits] [--json]
    python3 purpose_audit.py --gate            # exit 1 if fit-for-purpose regressed
    python3 purpose_audit.py --update-baseline # lock the current state in as the floor
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import tokenize
from datetime import datetime, timezone
from pathlib import Path

SCAN_DIR = "brain"
SKIP = ("__pycache__", ".pyc")

# Depth/claims statuses ordered worst-last, so a rising rank is a regression.
RANK = {"OK": 0, "PARTIAL": 1, "MISSING": 2}
DEFAULT_BASELINE = "watcher/knowledge/depth-baseline.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_claims(path: Path) -> list[tuple[str, str, str]]:
    claims = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) >= 2:
            claims.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return claims


def is_test_file(path: Path) -> bool:
    return "test" in path.name or "tests" in path.parts


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan(root: Path, pattern: re.Pattern) -> list[tuple[str, int, bool]]:
    """Return (path, line_no, in_test) for every match of pattern under root."""
    hits: list[tuple[str, int, bool]] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in (".py",):
            continue
        if any(s in f.parts for s in SKIP):
            continue
        try:
            for i, text in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(text):
                    hits.append((f.as_posix(), i, is_test_file(f)))
        except OSError:
            continue
    return hits


def imported_outside_tests(module_path: str, root: Path, tests_root: Path) -> bool:
    """True if a module is imported by any production file (not tests)."""
    stem = Path(module_path).stem
    pattern = re.compile(rf"\b{re.escape(stem)}\b")
    for f in sorted(root.rglob("*.py")):
        if any(s in f.parts for s in SKIP) or f.as_posix() == module_path:
            continue
        if f.is_relative_to(tests_root) if tests_root else False:
            continue
        try:
            if pattern.search(f.read_text(encoding="utf-8", errors="replace")):
                return True
        except OSError:
            continue
    return False


# The live-run finding names an issue -> PR run, so its proof is three links: the issue that
# triggered the run, the workflow run itself, and the pull request the run produced. Anything
# less (a conversation link; an issue and a pull request with no run between them) shows only
# part of the path.
_ISSUE_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+$")
_PULL_REQUEST_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+$")
_RUN_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+$")
_GITHUB_ITEM_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(?:issues|pull|actions/runs)/\d+$"
)


def _repo_of(url: str) -> str:
    """The `owner/repo` slug of a GitHub issue or pull-request URL, or "" if it is not one."""
    match = _GITHUB_ITEM_RE.match(url)
    return match.group(1) if match else ""


def _field_url(path: Path, field: str) -> str:
    """Return the first `http(s)` URL recorded under `field` in an evidence file, or ""."""
    for line in _read(path).splitlines():
        stripped = line.strip()
        if stripped.startswith(field):
            value = stripped.split(":", 1)[1].strip()
            if value.startswith(("http://", "https://")):
                return value
    return ""


def _call_offsets(text: str) -> dict[str, list[int]]:
    """Map each called name to the character offsets it is *called* at (`name(`), or {} if unparsable.

    W3: a raw `"run_openhands_role" in text` match is satisfied by a comment or a docstring, so
    the audit could report the loop "wired" while no role reaches it. Tokenizing drops comments
    and strings, and requiring a following `(` distinguishes a call from a mere import or a
    mention in a string, so the check reads code, not text. (Reachability inside dead code is
    beyond a tokenizer; a call is credited wherever it textually appears as a call.)
    """
    calls: dict[str, list[int]] = {}
    line_start = [0]
    for line in text.splitlines(keepends=True):
        line_start.append(line_start[-1] + len(line))
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return {}
    for first, second in zip(tokens, tokens[1:]):
        if first.type == tokenize.NAME and second.type == tokenize.OP and second.string == "(":
            row, col = first.start
            calls.setdefault(first.string, []).append(line_start[row - 1] + col)
    return calls


def evidence_link(path: Path) -> str:
    """Return the conversation link recorded in an evidence file, or "" if there is none.

    A DRY RUN records no conversation, so it is not proof the loop ran. Only a real URL under
    the writer's `- link:` field counts; the placeholder it writes when it has no link does not.
    """
    return _field_url(path, "- link:")


def pull_request_link(path: Path) -> str:
    """Return the pull-request link recorded in an evidence file, or "" if there is none.

    The live-run finding claims an issue -> PR run, so a conversation link alone is not proof:
    the run must name the pull request it produced. Only a real
    `https://github.com/<owner>/<repo>/pull/<n>` URL under the writer's `- pr:` field counts.
    This is what stops the finding passing on a conversation-only file (W3: a check must fail
    when the thing it names is absent).
    """
    value = _field_url(path, "- pr:")
    return value if _PULL_REQUEST_RE.match(value) else ""


def issue_link(path: Path) -> str:
    """Return the issue link recorded in an evidence file, or "" if there is none.

    The finding names an **issue** -> PR run, so the pull request alone is not the whole proof:
    the record must also name the issue that triggered the run. Only a real
    `https://github.com/<owner>/<repo>/issues/<n>` URL under the writer's `- issue:` field
    counts. Without this, a bare PR link passes a claim about an issue -> PR run (the same W3
    shape, one level deeper).
    """
    value = _field_url(path, "- issue:")
    return value if _ISSUE_RE.match(value) else ""


def run_link(path: Path) -> str:
    """Return the workflow-run link recorded in an evidence file, or "" if there is none.

    The finding names an issue -> PR **run**, so the issue and the pull request alone are not
    the whole proof: the record must also name the run that connected them. Without it, two
    URLs typed into one file pass a claim about a run that took the issue to the pull request.
    Only a real `https://github.com/<owner>/<repo>/actions/runs/<n>` URL under the writer's
    `- workflow run:` field counts.
    """
    value = _field_url(path, "- workflow run:")
    return value if _RUN_RE.match(value) else ""


def _run_proof(path: Path) -> dict[str, str]:
    """The live-run links one evidence file records: issue, run, pull request, conversation.

    One file is one run. The finding names *a* live issue -> PR run, so the links that prove it
    must come from the same file; see `depth_findings`.
    """
    return {
        "issue": issue_link(path),
        "run": run_link(path),
        "pr": pull_request_link(path),
        "conversation": evidence_link(path),
    }


def _same_repository(r: dict[str, str]) -> bool:
    """True when the file's issue, run, and pull request are all GitHub items in one repository.

    A run triggers on an issue, runs in the repository that hosts it, and produces a pull
    request in the repository it is allowed to write (the gateway allowlists one owner, and
    `brain/company/tools.py:225` requires the run's reported target repository to match). So
    the three links that prove one run must name the *same* `owner/repo`; links from different
    repositories are unrelated items, not one run's issue -> PR path.
    """
    repos = [_repo_of(r[key]) for key in ("issue", "run", "pr")]
    return "" not in repos and len({repo.casefold() for repo in repos}) == 1


def _repo_owner(repo: str) -> str:
    """The owner part of an `owner/repo` slug, or ""."""
    return repo.split("/", 1)[0].casefold() if "/" in repo else ""


def _owner_scope() -> str:
    """The owner this repository is, so a proof from a foreign repository cannot pass.

    The finding names the app's own live run: an issue dispatched through Brain's company
    workflow that produced a pull request. Brain writes to one owner only — the gateway
    allowlists it (`github_gateway.py:47`) and the task runner accepts issues "owned by the
    Brain repository owner" (`brain-task-runner.yml:50`) — so a proof whose links name a
    different owner is not this app's run, however well-formed it looks. The owner comes from
    the environment the audit runs in (`GITHUB_REPOSITORY` under Actions); with none set (a
    local run) the check stays lenient and only requires the three links to agree with each
    other. Never guessed from the working tree, so a test tree cannot silence it.
    """
    slug = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if slug and "/" in slug:
        return _repo_owner(slug)
    owner = os.environ.get("BRAIN_GITHUB_OWNER", "").strip()
    return owner.casefold()



def _proof_owners(r: dict[str, str]) -> set[str]:
    """The owners named by the links a proof file holds (only the fields it records)."""
    return {_repo_owner(repo) for key in ("issue", "run", "pr") if (repo := _repo_of(r[key]))}


def _proof_in_scope(r: dict[str, str], owner: str) -> bool:
    """True when every link a proof holds names this repository's owner (or no scope is known).

    With no `owner` (a local run) every repository is in scope; the three links still have to
    agree with each other, so this is strictly narrower, never looser.
    """
    if not owner:
        return True
    owners = _proof_owners(r)
    return bool(owners) and owners == {owner}


_ITEM_FIELDS = (("issue", "issue"), ("run", "workflow run"), ("pr", "pull request"))


def _describe_fragment(name: str, r: dict[str, str], owner: str = "") -> str:
    """Name which part of the issue -> run -> PR path a single evidence file holds."""
    present = [(label, r[key]) for key, label in _ITEM_FIELDS if r[key]]
    owners = _proof_owners(r)
    # A foreign proof only reads as "foreign" when its links agree on one repository; a mixed
    # file is reported as the incomplete path it is, below.
    if owner and len(owners) == 1 and next(iter(owners)) != owner:
        repo = next(repo for key in ("issue", "run", "pr") if (repo := _repo_of(r[key])))
        return (f"{name} -> {repo} (not this repository's owner {owner!r}; a run this app did "
                "not perform)")
    if len(present) == 1:
        label, url = present[0]
        return f"{name} -> {url} ({label} only; no complete issue -> run -> PR path recorded)"
    if present:
        return (f"{name} -> " + "; ".join(f"{label} {url}" for label, url in present)
                + " (incomplete issue -> run -> pull request path: links are in different "
                  "repositories, or a step is missing)")
    return f"{name} -> {r['conversation']} (conversation only; no pull request recorded)"


def depth_findings(root: Path) -> list[dict]:
    """Find depth gaps a presence check misses: does the feature cover the whole app?

    These are the mistakes a claim-by-claim audit passes over. Each finding is derived from
    the code, with file evidence, so the Watcher finds them without a human reading by hand.
    """
    company = root / "company"
    roles_txt = _read(company / "roles.py")
    runner_txt = _read(company / "agent_runner.py")
    dev_txt = _read(company / "openhands_developer.py")
    out: list[dict] = []

    total_roles = len(re.findall(r"SpecialistRole\(", roles_txt))
    role_keys = re.findall(r'key="([a-z_]+)"', roles_txt)
    # A role reaches the agentic loop only if the runner *calls* an OpenHands SDK runner on its
    # branch. W3: match the tokenized call, not the bare name — a comment or a docstring mention
    # satisfied a substring check and reported the loop wired when it was not.
    calls = _call_offsets(runner_txt)
    dev_calls = calls.get("run_openhands_developer", [])
    loop_roles = sorted({
        m.group(1)
        for m in re.finditer(r'role_key == "([a-z_]+)"', runner_txt)
        if any(m.start() <= offset <= m.start() + 400 for offset in dev_calls)
    })
    # The general investigative loop (run_openhands_role) covers every non-developer role; the
    # developer keeps its own file-editing loop above. A real call here must not be credited to
    # the developer, or deleting the developer branch still reads as full coverage (W3).
    if calls.get("run_openhands_role"):
        loop_roles = sorted(set(loop_roles) | (set(role_keys) - {"developer"}))
    if total_roles:
        status = "OK" if len(loop_roles) >= total_roles else "PARTIAL"
        rest = total_roles - len(loop_roles)
        out.append({
            "id": "loop-coverage",
            "finding": f"Agentic loop covers {len(loop_roles)} of {total_roles} roles "
                       f"({rest} run single-shot)",
            "status": status,
            "evidence": [
                f"loop roles: {', '.join(loop_roles) or 'none'}",
                ("the rest call provider.complete once (agent_runner.py:412)"
                 if rest else "every role reaches an OpenHands SDK loop"),
            ],
        })

    max_files = (re.findall(r"_MAX_FILES = (\d+)", dev_txt) or ["?"])[0]
    max_file = (re.findall(r"_MAX_FILE_BYTES = (\d+)", dev_txt) or ["?"])[0]
    # W3: the contract bounds size, but no longer forbids deletions or unplanned new files.
    # A bound is present only if the developer still rejects a whole class of change.
    forbids_del = "does not support deletions" in dev_txt
    constrains_new = "unplanned file" in dev_txt
    lifts_del = '"deleted": True' in dev_txt or "'deleted': True" in dev_txt
    if dev_txt:
        ev = [f"limits: {max_files} files, {max_file} bytes/file"]
        if forbids_del:
            ev.append("deletions forbidden (openhands_developer.py)")
        elif lifts_del:
            ev.append("deletions allowed and collected as {path, deleted: true} (openhands_developer.py)")
        if constrains_new:
            ev.append("unplanned new files rejected (openhands_developer.py)")
        else:
            ev.append("unplanned new files allowed (openhands_developer.py)")
        out.append({
            "id": "patch-contract",
            "finding": "Patch contract bounds what the agent may change",
            "status": "PARTIAL" if (forbids_del or constrains_new) else "OK",
            "evidence": ev,
        })

    if "TemporaryDirectory" in dev_txt:
        out.append({
            "id": "repo-checkout",
            "finding": "Developer works in a temporary workspace, not the repo checkout",
            "status": "PARTIAL",
            "evidence": ["openhands_developer.py uses TemporaryDirectory"],
        })

    evidence_dir = root.parent / "watcher" / "knowledge" / "evidence"
    proof = sorted(evidence_dir.glob("*.md")) if evidence_dir.is_dir() else []
    # W3: the finding names a live issue -> PR run, so a single evidence file — one run — must
    # name all three steps: the issue that triggered the run, the workflow run, and the pull
    # request the run produced. Aggregating the links across separate files, or accepting an
    # issue and a pull request with no run between them, would pass on a path no single run
    # took — exactly the false pass this check exists to catch. OK therefore requires all three
    # links in the SAME file; any partial file keeps the finding below OK.
    proofs = {p.name: _run_proof(p) for p in proof}
    # OK needs all three links in one file AND in one repository: an issue in repo A with a
    # run or pull request in repo B is not the issue -> PR path this finding names. It must
    # also be THIS repository's owner: a well-formed proof from a foreign repository is a run
    # this app did not perform (W3, one level deeper — "same repository" let a foreign repo
    # through as long as its own three links agreed).
    owner = _owner_scope()
    complete = {name: r for name, r in proofs.items()
                if r["issue"] and r["run"] and r["pr"] and _same_repository(r)
                and _proof_in_scope(r, owner)}
    partial = {name: r for name, r in proofs.items() if name not in complete
               and (r["issue"] or r["run"] or r["pr"] or r["conversation"])}
    if complete:
        live_status = "OK"
        live_evidence = [f"{name} -> issue {r['issue']}; run {r['run']}; pull request {r['pr']}"
                         for name, r in complete.items()]
    elif partial:
        live_status = "PARTIAL"
        live_evidence = [_describe_fragment(name, r, owner) for name, r in partial.items()]
    else:
        live_status = "MISSING"
        live_evidence = ["no live-run evidence committed (a DRY RUN or an evidence file with no "
                         "conversation link does not prove the loop ran)"]
    out.append({
        "id": "live-run-evidence",
        "finding": "Committed evidence of a live issue -> PR run",
        "status": live_status,
        "evidence": live_evidence,
    })

    # W7: a role with no skill file runs on its bare contract. A missing skill is the Watcher's
    # job to find, so it is a depth finding here, not a separate script.
    skills_dir = company / "skills"
    missing_skills = [k for k in role_keys if not (skills_dir / f"{k}.md").is_file()]
    if role_keys:
        out.append({
            "id": "role-skills",
            "finding": f"{len(role_keys) - len(missing_skills)} of {len(role_keys)} roles have a skill file",
            "status": "OK" if not missing_skills else "PARTIAL",
            "evidence": [
                f"missing: {', '.join(missing_skills) or 'none'}",
                "a role with no skill runs on its bare contract (brain/company/skills/)",
            ],
        })
    router = root.parent / "scripts" / "skills.py"
    out.append({
        "id": "skill-router",
        "finding": "A skill router exists so work finds its skill instead of guessing",
        "status": "OK" if router.is_file() else "MISSING",
        "evidence": ["scripts/skills.py" if router.is_file() else "scripts/skills.py is absent"],
    })

    # W4: a capability that no workflow schedules does not run.
    tools_dir = root.parent / "watcher" / "knowledge" / "tools"
    workflows = root.parent / ".github" / "workflows"
    wf_text = "".join(_read(p) for p in sorted(workflows.glob("*.yml")))
    tools = [p.name for p in sorted(tools_dir.glob("*.py"))] if tools_dir.is_dir() else []
    unscheduled = [t for t in tools if t not in wf_text]
    if tools:
        out.append({
            "id": "tools-scheduled",
            "finding": f"{len(tools) - len(unscheduled)} of {len(tools)} Watcher tools are scheduled",
            "status": "OK" if not unscheduled else "PARTIAL",
            "evidence": [f"unscheduled: {', '.join(unscheduled) or 'none'}"],
        })
    return out


def audit(root: Path, purpose: Path, tests_root: Path, base: Path | None = None) -> dict:
    base = base or root.parent
    results = []
    for claim, probe, hint in parse_claims(purpose):
        hits = scan(root, re.compile(probe))
        prod = [h for h in hits if not h[2]]
        test = [h for h in hits if h[2]]
        if prod:
            status = "OK"
            reachable = True
        elif test:
            status = "UNTESTED"
            reachable = False
        else:
            status = "MISSING"
            reachable = False
        evidence = []
        for p, n, _ in (prod or test)[:4]:
            try:
                p = Path(p).relative_to(base).as_posix()
            except ValueError:
                pass
            evidence.append(f"{p}:{n}")
        results.append({
            "claim": claim, "status": status, "reachable": reachable,
            "hint": hint, "evidence": evidence,
        })
    ok = sum(1 for r in results if r["status"] == "OK")
    depth = depth_findings(root)
    return {"checked": len(results), "ok": ok, "results": results, "depth": depth}


def render(report: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Purpose audit — {ts}", "",
             f"{report['ok']}/{report['checked']} claims are implemented in production code.", ""]
    for r in report["results"]:
        mark = {"OK": "[x]", "UNTESTED": "[~]", "MISSING": "[ ]"}[r["status"]]
        lines.append(f"{mark} **{r['claim']}** — {r['status']}")
        if r["evidence"]:
            lines.append(f"    - {', '.join(r['evidence'])}")
        elif r["hint"]:
            lines.append(f"    - expected around `{r['hint']}`")
    depth = report.get("depth", [])
    if depth:
        gaps = sum(1 for d in depth if d["status"] != "OK")
        lines += ["", f"## Depth — {gaps} gap(s) a presence check would miss", ""]
        for d in depth:
            mark = {"OK": "[x]", "PARTIAL": "[~]", "MISSING": "[ ]"}[d["status"]]
            lines.append(f"{mark} **{d['finding']}** — {d['status']}")
            if d["evidence"]:
                lines.append(f"    - {'; '.join(d['evidence'])}")
    return "\n".join(lines) + "\n"


def gate_findings(report: dict, baseline: dict) -> list[dict]:
    """Findings that regressed against the locked floor.

    A finding regresses when its status rank rises (OK -> PARTIAL -> MISSING). Findings
    absent from the baseline are new and never fail; a depth finding with no stable id is
    reported so a renamed finding cannot silently slip past the gate.
    """
    out: list[dict] = []
    base = baseline.get("depth", {})
    for d in report.get("depth", []):
        key = d.get("id")
        if not key:
            out.append({"id": "?", "finding": d["finding"], "why": "no stable id"})
            continue
        was = base.get(key)
        now = d["status"]
        if was is None:
            continue  # new finding: not a regression
        if RANK.get(now, 9) > RANK.get(was, 9):
            out.append({"id": key, "finding": d["finding"], "why": f"{was} -> {now}"})
    return out


def baseline_from(report: dict) -> dict:
    """The floor to lock in: each finding's current status."""
    return {
        "depth": {d["id"]: d["status"] for d in report.get("depth", []) if d.get("id")},
        "ok": report["ok"],
        "checked": report["checked"],
    }


def render_gate(failed: list[dict], baseline: dict) -> str:
    if not failed:
        return (f"purpose gate: OK — no fit-for-purpose regression against "
                f"{len(baseline.get('depth', {}))} locked finding(s).")
    lines = [f"purpose gate: FAIL — {len(failed)} fit-for-purpose regression(s):"]
    for f in failed:
        lines.append(f"  - {f['id']}: {f['finding']} ({f['why']})")
    lines.append("Fix the regression, or run --update-baseline only if the change is intended.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Does the code do what the app claims? (WATCHER.md §16.5)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--purpose", default="watcher/knowledge/purpose.md")
    ap.add_argument("--out", default="watcher/knowledge/audits")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if a fit-for-purpose finding regressed against the baseline")
    ap.add_argument("--update-baseline", action="store_true",
                    help="lock the current state in as the new floor (intended changes only)")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    a = ap.parse_args()

    root = Path(a.root)
    report = audit(root / SCAN_DIR, Path(a.purpose), root / "tests")

    if a.update_baseline:
        dest = Path(a.baseline)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(baseline_from(report), indent=2) + "\n", encoding="utf-8")
        log(f"baseline updated -> {dest}")
        return 0

    if a.gate:
        baseline_path = Path(a.baseline)
        baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else {}
        failed = gate_findings(report, baseline)
        log(render_gate(failed, baseline))
        return 1 if failed else 0

    if a.json:
        log(json.dumps(report, indent=2))
        return 0
    text = render(report)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"purpose-{datetime.now(timezone.utc):%Y%m%d}.md"
    dest.write_text(text, encoding="utf-8")
    log(text)
    log(f"-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
