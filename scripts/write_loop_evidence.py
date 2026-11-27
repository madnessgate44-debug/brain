#!/usr/bin/env python3
"""Record the proof of one live issue -> PR run as a committable evidence file.

`purpose_audit.py`'s depth finding "Committed evidence of a live issue -> PR run" is `OK` only
when one file names the issue, the workflow run, and the pull request. Nothing produced that
file: `start_session_loop.py` records a conversation link, which the finding rejects, so a real
run left no committed proof and the only conforming file was typed by hand. A hand-written
proof is an artifact, not a producer — the same W3 shape one level deeper.

This script is the producer. The company workflow calls it with the three links it already
knows (the issue it was dispatched on, its own run id, and the pull request it opened). It
validates with the checker's own predicates, so the writer and the check cannot drift, and it
refuses to write a file the check would not accept.

    python3 scripts/write_loop_evidence.py --issue <url> --run <url> --pr <url> [--out DIR]
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CHECKER = _ROOT / "watcher" / "knowledge" / "tools" / "purpose_audit.py"
_FIELD = {"issue": "issues/<n>", "workflow run": "actions/runs/<n>", "pull request": "pull/<n>"}


def _checker():
    """Load the checker so the writer reuses its exact URL and repository rules."""
    spec = importlib.util.spec_from_file_location("purpose_audit", _CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_evidence(issue: str, run: str, pr: str, *, stamp: str) -> str:
    """Render the evidence body, or raise ValueError naming the link that is not usable."""
    pa = _checker()
    for label, url, pattern in (
        ("issue", issue, pa._ISSUE_RE),
        ("workflow run", run, pa._RUN_RE),
        ("pull request", pr, pa._PULL_REQUEST_RE),
    ):
        if not pattern.match(url or ""):
            raise ValueError(
                f"{label} is not a GitHub {label} URL: {url!r}. "
                f"Only https://github.com/<owner>/<repo>/{_FIELD[label]} counts."
            )
    proof = {"issue": issue, "run": run, "pr": pr}
    if not pa._same_repository(proof):
        raise ValueError(
            "the issue, run, and pull request must name one repository: a run triggers on an "
            "issue in the repository that hosts it and opens its pull request there."
        )
    return (
        f"# Company workflow loop — live issue -> PR run ({stamp} UTC)\n\n"
        "Status: LIVE — an issue was dispatched through the company workflow and produced a "
        "pull request. This is the proof the W3 depth finding names.\n\n"
        f"- issue: {issue}\n"
        f"- workflow run: {run}\n"
        f"- pr: {pr}\n"
    )


def write_evidence(issue: str, run: str, pr: str, out_dir: Path, *,
                   stamp: str | None = None) -> Path:
    """Write the evidence file and re-read it with the checker before returning its path."""
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    body = build_evidence(issue, run, pr, stamp=stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"company-loop-{stamp}-issue{_last_int(issue)}-pr{_last_int(pr)}.md"
    dest.write_text(body, encoding="utf-8")

    pa = _checker()
    proof = pa._run_proof(dest)
    if not (proof["issue"] and proof["run"] and proof["pr"] and pa._same_repository(proof)):
        dest.unlink()
        raise ValueError(f"the written evidence file is not accepted by the check: {dest}")
    return dest


def _last_int(url: str) -> int:
    return int(url.rstrip("/").rsplit("/", 1)[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issue", required=True, help="the issue the run was dispatched on")
    ap.add_argument("--run", required=True, help="the workflow run that produced the pull request")
    ap.add_argument("--pr", required=True, help="the pull request the run opened")
    ap.add_argument("--out", default="watcher/knowledge/evidence")
    a = ap.parse_args()
    try:
        dest = write_evidence(a.issue, a.run, a.pr, Path(a.out))
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
