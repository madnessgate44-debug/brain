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
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, "audit-log.md")

sys.path.insert(0, HERE)
from keypool import routes  # noqa: E402

KEY_ENV = "OHGeminiAPI"
REPO = "madnessgate44-debug/brain"


def _gemini_base() -> str:
    """Gemini API base. Overridable so Shadow can run end-to-end offline."""
    return os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")


def _gh_base() -> str:
    return os.environ.get("GITHUB_API_BASE", "https://api.github.com").rstrip("/")

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


_MAX_STEPS = 4
# Files are read at the ref under audit (a PR head sha), not always the default branch.
_AUDIT_REF = "HEAD"


def _tool_read_file(path: str, ref: str) -> str:
    """Read a repo file at a ref via the GitHub API, so Shadow reads ground truth."""
    c = _gh(f"/repos/{REPO}/contents/{urllib.parse.quote(path, safe='/')}?ref={ref}")
    if not isinstance(c, dict) or not c.get("content"):
        return f"could not read {path} at {ref}"
    import base64
    txt = base64.b64decode(c["content"]).decode("utf-8", "replace")
    cap = 12000
    mark = "COMPLETE" if len(txt) <= cap else f"TRUNCATED to {cap} of {len(txt)} bytes"
    return f"{path} ({mark}):\n{txt[:cap]}"


def _tool_list_dir(path: str, ref: str) -> str:
    c = _gh(f"/repos/{REPO}/contents/{urllib.parse.quote(path, safe='/')}?ref={ref}")
    if not isinstance(c, list):
        return f"could not list {path} at {ref}"
    return f"{path}: " + ", ".join(sorted(i.get("name", "?") for i in c))


def _tool_search(pattern: str, ref: str) -> str:
    """Search the repo's code for a pattern via the GitHub search API."""
    q = urllib.parse.quote(f"repo:{REPO} {pattern}")
    d = _gh(f"/search/code?q={q}&per_page=10")
    items = d.get("items") if isinstance(d, dict) else None
    if not items:
        return f"no code matches for {pattern!r}"
    return "\n".join(f"{i['path']}" for i in items)


def _tool_read_workflow(name: str) -> str:
    """Recent runs of one workflow — real history, so a claim about CI is checkable."""
    rr = _gh(f"/repos/{REPO}/actions/workflows/{urllib.parse.quote(name, safe='')}/runs?per_page=8")
    runs = (rr.get("workflow_runs") if isinstance(rr, dict) else None) or []
    if not runs:
        return f"no runs for workflow {name!r}"
    return "\n".join(f"{r['created_at']} {r['head_branch'][:24]} -> {r['conclusion']}" for r in runs)


def _tool_read_log(pr: int) -> str:
    """The verdicts Shadow already posted on a PR — so he does not re-flag a fixed item."""
    c = _gh(f"/repos/{REPO}/issues/{pr}/comments?per_page=100")
    if not isinstance(c, list):
        return f"could not read comments for PR #{pr}"
    shadow = [x.get("body", "") for x in c if "Shadow" in (x.get("body") or "")]
    return "\n---\n".join(shadow[-3:]) or f"no Shadow comments on PR #{pr}"


TOOLS: dict[str, Any] = {
    "read_file": (_tool_read_file, "read_file(path, ref) -> file contents at a git ref"),
    "list_dir": (_tool_list_dir, "list_dir(path, ref) -> names in a repo directory"),
    "search": (_tool_search, "search(pattern, ref) -> paths matching a code pattern"),
    "read_workflow": (_tool_read_workflow, "read_workflow(name) -> recent runs of a workflow"),
    "read_log": (_tool_read_log, "read_log(pr) -> Shadow's prior verdicts on a PR"),
}


def _tool_catalog() -> str:
    return "\n".join(f"- {name}: {desc}" for name, (_, desc) in TOOLS.items())


def _run_tool(name: str, args: dict[str, Any]) -> str:
    fn = TOOLS.get(name, (None, ""))[0]
    if fn is None:
        return f"unknown tool {name!r}"
    try:
        if name in ("read_file", "list_dir", "search"):
            return fn(str(args.get("path") or args.get("pattern") or "."),
                      str(args.get("ref") or _AUDIT_REF or "HEAD"))
        if name == "read_workflow":
            return fn(str(args.get("name") or ""))
        if name == "read_log":
            return fn(int(args.get("pr") or 0))
    except Exception as e:  # noqa: BLE001
        return f"{name} failed: {type(e).__name__}: {e}"
    return "no-op"


_TOOL_PROTOCOL = """

You may gather more evidence before judging. To call a tool, reply with ONLY:
TOOL: <name> {"arg": "value"}
Available tools:
""" + _tool_catalog() + """

When you have enough evidence, reply with the final verdict in the format above (starting
VERDICT:). Do not mix a tool call and a verdict in the same reply."""


def _parse_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Return (name, args) if the model asked for a tool, else None."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("TOOL:"):
            continue
        rest = line[len("TOOL:"):].strip()
        name, _, js = rest.partition(" ")
        try:
            args = json.loads(js.strip() or "{}")
        except json.JSONDecodeError:
            args = {}
        if name and isinstance(args, dict):
            return name, args
    return None


def _is_verdict(text: str) -> bool:
    return "VERDICT:" in text


def generate(prompt: str, timeout: int = 90) -> tuple[str, str]:
    """Walk the pool (key × model) and return (route_label, text).

    A quota or rate error on one route moves to the next; one exhausted key never
    stops the job (WATCHER.md §14.2 fallback).
    """
    last = "no route attempted"
    for label, key, model in routes():
        url = f"{_gemini_base()}/models/{model}:generateContent"
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
    req = urllib.request.Request(f"{_gh_base()}{path}")
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
    sizes = {f["filename"]: f.get("size", 0) for f in fl}
    # Include raw content of small changed files so the Shadow reads ground truth, not a diff excerpt.
    raw = []
    per_file_cap, total_cap = 16000, 64000
    prio = sorted(files, key=lambda f: (0 if f.startswith(".github/workflows/") else 1))
    for f in prio:
        if f == "shadow/shadow.py":
            continue  # the auditor's own source is not the artifact under audit
        included = (
            f.startswith(".github/workflows/") or f.endswith(".json")
            or (f.startswith(("watcher/", "shadow/", "tools/", "scripts/", "tests/"))
                and f.endswith((".py", ".txt", ".md")) and sizes.get(f, 0) <= per_file_cap)
            or (f.endswith(".py") and "/" not in f and sizes.get(f, 0) <= per_file_cap)
        )
        if included:
            c = _gh(f"/repos/{REPO}/contents/{urllib.parse.quote(f, safe='/')}?ref={sha}")
            if isinstance(c, dict) and c.get("content"):
                import base64
                txt = base64.b64decode(c["content"]).decode("utf-8", "replace")
                mark = "COMPLETE" if len(txt) <= per_file_cap else f"TRUNCATED {per_file_cap} of {len(txt)} bytes"
                raw.append(f"===== BEGIN FILE {f} ({mark}) =====\n" + txt[:per_file_cap] + f"\n===== END FILE {f} =====")
    rawtxt = "\n".join(raw)[:total_cap]
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


def issue_evidence(ref: str) -> str:
    """ref = 'owner/repo#N'. Returns real GitHub state so a claim is checked at its source."""
    try:
        repo, num = ref.split("#")
        d = _gh(f"/repos/{repo}/issues/{num}")
        if "number" not in d:
            return f"issue {ref} -> NOT FOUND (HTTP {d.get('error', '?')})"
        return (f"issue {ref} -> EXISTS title={d['title']!r} state={d['state']} "
                f"labels={[l['name'] for l in d.get('labels', [])]} created={d['created_at']}")
    except Exception as e:  # noqa: BLE001
        return f"issue {ref} -> UNVERIFIED ({e})"


def live_evidence(pr: int | None = None, issue: str | None = None) -> str:
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
        for m in ("gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"):
            rq = _u.Request(f"{_gemini_base()}/models/{m}:generateContent",
                            data=b'{"contents":[{"parts":[{"text":"ok"}]}]}', method="POST")
            rq.add_header("x-goog-api-key", key); rq.add_header("Content-Type", "application/json")
            try:
                with _u.urlopen(rq, timeout=25) as x:
                    probe.append(f"{m} -> HTTP {x.status}")
            except Exception as e:  # noqa: BLE001
                probe.append(f"{m} -> HTTP {getattr(e, 'code', '?')}")
    probe_txt = "\n".join(probe)
    out = (f"branch={branch} head={head} dirty={dirty}\n"
           f"brain hub open tickets (watcher/bridge/tickets.json — NOT GitHub issues): {open_t}\n"
           f"live model probe (independent, real API calls):\n{probe_txt}")
    if issue:
        out += f"\n{issue_evidence(issue)}"
    if pr is not None:
        out += f"\n{pr_evidence(pr)}"
    return out


def audit(subject: str, context: str = "", pr: int | None = None, issue: str | None = None) -> str:
    global _AUDIT_REF
    if pr is not None:
        sha = (_gh(f"/repos/{REPO}/pulls/{pr}") or {}).get("head", {}).get("sha")
        _AUDIT_REF = sha or _AUDIT_REF
    base = (f"{SYSTEM}{_TOOL_PROTOCOL}\n\nLIVE EVIDENCE:\n{live_evidence(pr, issue)}\n\n"
            f"CONTEXT:\n{context}\n\nSUBJECT TO AUDIT:\n{subject}\n")
    prompt = base
    model, reply = generate(prompt)
    trace: list[str] = []
    for _ in range(_MAX_STEPS):
        if _is_verdict(reply):
            break
        call = _parse_tool_call(reply)
        if call is None:
            break  # no verdict and no tool call: take what we have
        name, args = call
        result = _run_tool(name, args)
        trace.append(f"{name} {args} -> {len(result)} chars")
        prompt += (f"\n\nASSISTANT:\n{reply}\n\nTOOL RESULT ({name}):\n{result}\n\n"
                   f"Continue. Reply with the final verdict (VERDICT:) or one more TOOL call.")
        model, reply = generate(prompt)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tool_note = f" (tools: {'; '.join(trace)})" if trace else ""
    with open(LOG, "a") as f:
        f.write(f"\n\n## Shadow audit — {ts} (route {model}){tool_note}\n\n{reply}\n")
    return reply


def main() -> int:
    ap = argparse.ArgumentParser(description="Shadow auditor (WATCHER.md §1)")
    ap.add_argument("--subject", help="text to audit")
    ap.add_argument("--subject-file", help="file containing the text to audit")
    ap.add_argument("--context", default="", help="extra context")
    ap.add_argument("--pr", type=int, help="attach independent CI evidence for a PR")
    ap.add_argument("--issue", help="owner/repo#N to attach real GitHub issue state")
    a = ap.parse_args()
    if a.subject_file:
        subject = open(a.subject_file).read()
    elif a.subject:
        subject = a.subject
    else:
        subject = sys.stdin.read()
    print(audit(subject, a.context, a.pr, a.issue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
