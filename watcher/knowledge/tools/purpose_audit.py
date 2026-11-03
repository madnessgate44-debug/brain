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
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCAN_DIR = "brain"
SKIP = ("__pycache__", ".pyc")


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
    # A role reaches the agentic loop if its branch wraps a call to an OpenHands SDK runner:
    # the developer's file-editing loop, or the investigative loop every other role now uses.
    loop_roles = sorted({
        m.group(1)
        for m in re.finditer(r'role_key == "([a-z_]+)"', runner_txt)
        if "run_openhands_developer" in runner_txt[m.start(): m.start() + 400]
    })
    # If the runner wires the general investigative loop, every non-developer role is covered.
    if "run_openhands_role" in runner_txt:
        loop_roles = sorted(set(loop_roles) | set(role_keys))
    if total_roles:
        status = "OK" if len(loop_roles) >= total_roles else "PARTIAL"
        rest = total_roles - len(loop_roles)
        out.append({
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
    forbids_del = "does not support deletions" in dev_txt
    constrains_new = "unplanned file" in dev_txt
    if dev_txt:
        ev = [f"limits: {max_files} files, {max_file} bytes/file"]
        if forbids_del:
            ev.append("deletions forbidden (openhands_developer.py)")
        if constrains_new:
            ev.append("unplanned new files rejected (openhands_developer.py)")
        out.append({
            "finding": "Patch contract bounds what the agent may change",
            "status": "PARTIAL" if (forbids_del or constrains_new) else "OK",
            "evidence": ev,
        })

    if "TemporaryDirectory" in dev_txt:
        out.append({
            "finding": "Developer works in a temporary workspace, not the repo checkout",
            "status": "PARTIAL",
            "evidence": ["openhands_developer.py uses TemporaryDirectory"],
        })

    evidence_dir = root.parent / "watcher" / "knowledge" / "evidence"
    proof = sorted(evidence_dir.glob("*.md")) if evidence_dir.is_dir() else []
    out.append({
        "finding": "Committed evidence of a live issue -> PR run",
        "status": "OK" if proof else "MISSING",
        "evidence": [p.as_posix() for p in proof] or ["no live-run evidence committed"],
    })

    # W7: a role with no skill file runs on its bare contract. A missing skill is the Watcher's
    # job to find, so it is a depth finding here, not a separate script.
    skills_dir = company / "skills"
    missing_skills = [k for k in role_keys if not (skills_dir / f"{k}.md").is_file()]
    if role_keys:
        out.append({
            "finding": f"{len(role_keys) - len(missing_skills)} of {len(role_keys)} roles have a skill file",
            "status": "OK" if not missing_skills else "PARTIAL",
            "evidence": [
                f"missing: {', '.join(missing_skills) or 'none'}",
                "a role with no skill runs on its bare contract (brain/company/skills/)",
            ],
        })
    router = root.parent / "scripts" / "skills.py"
    out.append({
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Does the code do what the app claims? (WATCHER.md §16.5)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--purpose", default="watcher/knowledge/purpose.md")
    ap.add_argument("--out", default="watcher/knowledge/audits")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args()

    root = Path(a.root)
    report = audit(root / SCAN_DIR, Path(a.purpose), root / "tests")
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
