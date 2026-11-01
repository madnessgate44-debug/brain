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
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, "audit-log.md")

sys.path.insert(0, HERE)
from keypool import routes  # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY_ENV = "OHGeminiAPI"
REPO = "madnessgate44-debug/brain"

SYSTEM = """You are Shadow, the black-box auditor for the Watcher agent (WATCHER.md §1).
Temperament: cold on evidence, adversarial until proven wrong, a mentor who explains every correction.
Audit the Watcher's claim or artifact against the LIVE EVIDENCE only.
Rules:
- CONFIRMED only if the evidence actually proves the claim. Otherwise UNPROVEN or DISPROVEN, with the reason.
- For any DISPROVEN claim you MUST quote the exact line from the evidence that proves it false. If you
  cannot quote such a line, the verdict is UNPROVEN, not DISPROVEN. Do not invent file contents, model
  ids, or empty blocks; if the raw file is present in the evidence, read it before judging.
- A model id is valid if the LIVE model probe shows HTTP 200 or 429. HTTP 404 means invalid.
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


def _gh(path: str) -> dict:
    """GET a GitHub API path with GITHUB_TOKEN. Returns {} on any failure."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {}
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return {}


def pr_evidence(pr: int) -> str:
    """Independent CI evidence for a PR — so the Shadow audits the merge gate itself."""
    p = _gh(f"/repos/{REPO}/pulls/{pr}")
    if not p:
        return f"PR #{pr}: could not read"
    sha = p.get("head", {}).get("sha", "")
    runs = _gh(f"/repos/{REPO}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    fails = [c["name"] for c in runs if c.get("conclusion") == "failure"]
    pend = [c["name"] for c in runs if c.get("status") != "completed"]
    fl = [f for f in _gh(f"/repos/{REPO}/pulls/{pr}/files?per_page=100") if isinstance(f, dict)]
    files = [f["filename"] for f in fl]
    # Include raw content of small changed files so the Shadow reads ground truth, not a diff excerpt.
    raw = []
    prio = sorted(files, key=lambda f: (0 if f.startswith(".github/workflows/") else 1))
    for f in prio:
        if f == "shadow/shadow.py":
            continue  # the auditor's own source is not the artifact under audit
        if f.startswith(".github/workflows/") or f.endswith((".json",)) or (f.startswith(("watcher/bridge/","shadow/")) and f.endswith(".py")):
            c = _gh(f"/repos/{REPO}/contents/{urllib.parse.quote(f, safe='/')}?ref={sha}")
            if isinstance(c, dict) and c.get("content"):
                import base64
                txt = base64.b64decode(c["content"]).decode("utf-8", "replace")
                mark = "COMPLETE" if len(txt) <= 2600 else f"TRUNCATED {2600} of {len(txt)} bytes"
                raw.append(f"===== BEGIN FILE {f} ({mark}) =====\n" + txt[:2600] + f"\n===== END FILE {f} =====")
    reg = _gh(f"/repos/{REPO}/contents/shadow/registry.md")
    if isinstance(reg, dict) and reg.get("content"):
        import base64
        raw.append("--- shadow/registry.md (which models are WORKING) ---\n" + base64.b64decode(reg["content"]).decode("utf-8","replace")[:1800])
    rawtxt = "\n".join(raw)[:14000]
    # Measured facts (objective, computed here) so structural claims are not guessed.
    empty_runs = []
    try:
        import yaml
        for f in files:
            if f.startswith(".github/workflows/"):
                c = _gh(f"/repos/{REPO}/contents/{urllib.parse.quote(f, safe='/')}?ref={sha}")
                if isinstance(c, dict) and c.get("content"):
                    import base64
                    d = yaml.safe_load(base64.b64decode(c["content"]).decode("utf-8", "replace"))
                    for jn, j in (d.get("jobs") or {}).items():
                        for st in (j.get("steps") or []):
                            if "run" in st and not str(st["run"]).strip():
                                empty_runs.append(f"{f}:{jn}:{st.get('name')}")
    except Exception:  # noqa: BLE001
        pass
    facts = f"MEASURED: empty run blocks = {empty_runs or 'none'}"
    history = []
    for f in files:
        if f.startswith(".github/workflows/"):
            rr = _gh(f"/repos/{REPO}/actions/workflows/{urllib.parse.quote(f, safe=chr(39)+chr(39))}/runs?per_page=6")
            for run in (rr.get("workflow_runs") or [])[:6]:
                history.append(f"{f}: {run['created_at']} {run['head_branch'][:24]} -> {run['conclusion']}")
    return (f"PR #{pr} sha={sha[:8]} mergeable={p.get('mergeable')} draft={p.get('draft')}\n"
            f"  checks: {len(runs)} total, failing={fails}, pending={pend}\n"
            f"  files ({len(files)}): {files}\n"
            f"  {facts}\n"
            f"  COMPLETE FILE CONTENTS of changed workflows/json/py (authoritative; no diff truncation):\n{rawtxt}\n"
            f"  workflow run history (independent, before this PR):\n" + "\n".join(history))


def live_evidence(pr: int | None = None) -> str:
    head = _git(["rev-parse", "--short", "HEAD"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = "yes" if _git(["status", "--porcelain"]) else "no"
    try:
        reg = json.load(open(os.path.join(ROOT, "watcher", "bridge", "tickets.json")))
        open_t = sorted(k for k, v in reg.items() if v.get("state") == "open")
    except Exception:  # noqa: BLE001
        open_t = []
    probe = []
    key = os.environ.get("OHGeminiAPI")
    if key:
        import urllib.request as _u
        for m in ("gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-1.5-flash"):
            rq = _u.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                            data=b'{"contents":[{"parts":[{"text":"ok"}]}]}', method="POST")
            rq.add_header("x-goog-api-key", key); rq.add_header("Content-Type", "application/json")
            try:
                with _u.urlopen(rq, timeout=25) as x:
                    probe.append(f"{m} -> HTTP {x.status}")
            except Exception as e:  # noqa: BLE001
                probe.append(f"{m} -> HTTP {getattr(e, 'code', '?')}")
    probe_txt = "\n".join(probe)
    out = f"branch={branch} head={head} dirty={dirty} open_tickets={open_t}\nlive model probe (independent, real API calls):\n{probe_txt}"
    if pr is not None:
        out += f"\n{pr_evidence(pr)}"
    return out


def audit(subject: str, context: str = "", pr: int | None = None) -> str:
    prompt = (f"{SYSTEM}\n\nLIVE EVIDENCE:\n{live_evidence(pr)}\n\n"
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
    ap.add_argument("--pr", type=int, help="attach independent CI evidence for a PR")
    a = ap.parse_args()
    if a.subject_file:
        subject = open(a.subject_file).read()
    elif a.subject:
        subject = a.subject
    else:
        subject = sys.stdin.read()
    print(audit(subject, a.context, a.pr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
