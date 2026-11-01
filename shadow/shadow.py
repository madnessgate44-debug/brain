#!/usr/bin/env python3
"""Shadow — the black-box auditor (WATCHER.md §1), running on the free Gemini route.

Shadow is the counter to the Watcher: cold on evidence, adversarial until proven
wrong, and a mentor that explains every correction. This makes that a running,
repeatable process instead of a manual role. Key values are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, "audit-log.md")

sys.path.insert(0, HERE)
from keypool import routes  # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY_ENV = "OHGeminiAPI"

SYSTEM = """You are Shadow, the black-box auditor for the Watcher agent (WATCHER.md §1).
Temperament: cold on evidence, adversarial until proven wrong, a mentor who explains every correction.
Audit the Watcher's claim or artifact against the LIVE EVIDENCE only.
Rules:
- CONFIRMED only if the evidence actually proves the claim. Otherwise UNPROVEN or DISPROVEN, with the reason.
- Name the single weakest point and the exact missing evidence.
- If it fails, give the fix, not only the rejection.
- Short. Phone-readable. No preamble.
Output exactly:
VERDICT: VERIFIED | REJECTED | PARTIAL
FINDINGS:
- <claim> — <CONFIRMED|UNPROVEN|DISPROVEN> — <reason>
WEAKEST POINT: <one line>
FIX: <one line>"""


def generate(prompt: str, timeout: int = 90) -> tuple[str, str]:
    """Walk the pool (key × model) and return (route_label, text).

    A quota or rate error on one route moves to the next; one exhausted key never
    stops the job (WATCHER.md §14.2 fallback).
    """
    last = "no route attempted"
    for label, key, model in routes():
        url = f"{BASE}/models/{model}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2}}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
        req.add_header("x-goog-api-key", key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            return f"{label}:{model}", d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last = f"{label}:{model} HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = f"{label}:{model} {type(e).__name__}"
    raise RuntimeError(f"all routes failed (last: {last})")


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def live_evidence() -> str:
    head = _git(["rev-parse", "--short", "HEAD"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = "yes" if _git(["status", "--porcelain"]) else "no"
    try:
        reg = json.load(open(os.path.join(ROOT, "watcher", "bridge", "tickets.json")))
        open_t = sorted(k for k, v in reg.items() if v.get("state") == "open")
    except Exception:  # noqa: BLE001
        open_t = []
    return f"branch={branch} head={head} dirty={dirty} open_tickets={open_t}"


def audit(subject: str, context: str = "") -> str:
    prompt = (f"{SYSTEM}\n\nLIVE EVIDENCE:\n{live_evidence()}\n\n"
              f"CONTEXT:\n{context}\n\nSUBJECT TO AUDIT:\n{subject}\n")
    model, verdict = generate(prompt)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"\n\n## Shadow audit — {ts} (route {model})\n\n{verdict}\n")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description="Shadow auditor (WATCHER.md §1)")
    ap.add_argument("--subject", help="text to audit")
    ap.add_argument("--subject-file", help="file containing the text to audit")
    ap.add_argument("--context", default="", help="extra context")
    a = ap.parse_args()
    if a.subject_file:
        subject = open(a.subject_file).read()
    elif a.subject:
        subject = a.subject
    else:
        subject = sys.stdin.read()
    print(audit(subject, a.context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
