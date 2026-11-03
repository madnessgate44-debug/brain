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
    return {"checked": len(results), "ok": ok, "results": results}


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
