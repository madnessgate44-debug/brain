#!/usr/bin/env python3
"""End-to-end simulation of the Watcher loop — offline, deterministic, hermetic.

Owner (2026-11-01): "run an end-to-end simulation; let your first job be you."
This runs the REAL watcher code (loop.py, hub.py, shadow.py) against a local fake
GitHub + Gemini server. Only the external services are faked; the code under test
is untouched. Nothing touches the live GitHub or Gemini APIs.

  python3 scripts/e2e_sim.py            # run all stages, print PASS/FAIL
  python3 scripts/e2e_sim.py --verbose  # also stream each stage's stdout

Stages:
  1. idle        loop --once with no new counterpart -> "idle", no post
  2. reply       a counterpart comment appears -> loop posts a reply with the envelope
  3. hub read    hub.py read sees the posted reply, time from the Date header
  4. hub post    hub.py post appends a comment
  5. self-audit  shadow.py audits Watcher's own artifact and returns a verdict
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "madnessgate44-debug/brain"
ISSUE = 240
VERDICT = ("VERDICT: VERIFIED\n"
           "FINDINGS:\n- self-audit claim — CONFIRMED — the simulation exercised the real code.\n"
           "WEAKEST POINT: the fake server is not GitHub.\n"
           "FIX: none; this is a simulation.")


class Store:
    """Mutable hub state shared by the fake server."""

    def __init__(self) -> None:
        self.comments: list[dict] = []
        self.next_id = 1000

    def add(self, body: str, created: str | None = None) -> dict:
        self.next_id += 1
        c = {"id": self.next_id, "body": body,
             "created_at": created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.comments.append(c)
        return c


def make_handler(store: Store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _send(self, obj, code=200):
            raw = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/rate_limit":
                return self._send({"rate": {"limit": 5000}})
            if u.path == f"/repos/{REPO}/issues/{ISSUE}":
                return self._send({"number": ISSUE, "title": "hub"})
            if u.path == f"/repos/{REPO}/issues/{ISSUE}/comments":
                page = int(q.get("page", ["1"])[0])
                per = int(q.get("per_page", ["100"])[0])
                batch = store.comments[(page - 1) * per: page * per]
                return self._send(batch)
            # Shadow's PR evidence paths -> minimal but well-formed
            if u.path.startswith("/repos/") and "/pulls/" in u.path and u.path.endswith("/files"):
                return self._send([{"filename": "watcher/bridge/loop.py", "patch": "..."}])
            if u.path.startswith("/repos/") and "/pulls/" in u.path:
                return self._send({"number": 0, "mergeable": True, "draft": False,
                                   "head": {"sha": "0" * 40}})
            if "/check-runs" in u.path:
                return self._send({"check_runs": [{"name": "sim", "status": "completed", "conclusion": "success"}]})
            if "/contents/" in u.path:
                return self._send({"content": "", "encoding": "base64"})
            if u.path.startswith("/v1beta/models/"):
                return self._send({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
            return self._send({})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n).decode() if n else "{}"
            from urllib.parse import urlparse
            u = urlparse(self.path)
            if u.path.endswith("/comments"):
                try:
                    data = json.loads(body)
                except ValueError:
                    data = {}
                c = store.add(data.get("body", ""))
                return self._send(c, 201)
            if u.path.startswith("/v1beta/models/"):
                return self._send({"candidates": [{"content": {"parts": [{"text": VERDICT}]}}]})
            return self._send({}, 404)

    return H


def run(cmd, env_extra, verbose):
    env = dict(os.environ)
    env.update(env_extra)
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    if verbose:
        print(f"  $ {' '.join(cmd)}")
        print("  " + (p.stdout.strip().replace("\n", "\n  ") or "(no stdout)"))
        if p.stderr.strip():
            print("  [stderr] " + p.stderr.strip().replace("\n", "\n  "))
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    store = Store()
    store.add("### Sim counterpart\nThis is ChatGPT's opening message.", created="2026-11-01T10:00:00Z")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    gh = {"GITHUB_API_BASE": base, "GITHUB_TOKEN": "sim-token"}
    gem = {"GEMINI_API_BASE": f"{base}/v1beta"}
    print(f"fake server on {base} ({len(store.comments)} seeded comment)")

    results: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    # --- stage 1: idle (state says we've already seen comment 1001) ---
    state = os.path.join(ROOT, "watcher", "bridge", "state.json")
    saved = open(state).read() if os.path.exists(state) else None
    try:
        with open(state, "w") as f:
            json.dump({"last_seen_id": 1001, "seq": 18}, f)
        p = run([sys.executable, "watcher/bridge/loop.py", "--once"], gh, a.verbose)
        check("stage1 idle: loop reports idle, posts nothing",
              "idle" in p.stdout and len(store.comments) == 1, p.stdout.strip()[:80])

        # --- stage 2: a new counterpart -> loop replies ---
        # GitHub stamps created_at at post time, so the counterpart is posted "now".
        store.add("### Sim counterpart\nNew question for the Watcher.")
        p = run([sys.executable, "watcher/bridge/loop.py", "--once"], gh, a.verbose)
        posted = len(store.comments) == 3
        reply = store.comments[-1]["body"] if posted else ""
        check("stage2 reply: loop posted a reply to the new counterpart",
              posted and "ALERT new counterpart" in p.stdout, p.stdout.strip()[:90])
        check("stage2 envelope: reply carries the standard ticket fields",
              all(k in reply for k in ("**ACK**", "**TRACE**", "**ASK**", "**STATE**")),
              f"{len(reply)} bytes")
        check("stage2 loop-guard: reply does not echo the guard marker",
              "@watcher" not in reply.lower())
        # The reply's own stamp must track measured GitHub time, not the local clock.
        # github_now() corrects from the counterpart's created_at vs the Date header;
        # with a just-posted counterpart that offset is ~0, so the stamp is within a
        # few seconds of the reply comment's created_at.
        def _t(x):
            return datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        import re as _re
        m = _re.search(r"\u2014 Watcher \u00b7 (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \u00b7", reply)
        stamp = m.group(1) if m else ""
        try:
            drift = abs((_t(store.comments[-1]["created_at"]) - _t(stamp)).total_seconds())
        except Exception:
            drift = 10**9
        check("stage2 timestamp: body stamp tracks measured GitHub time (<=5s drift)",
              drift <= 5, f"stamp={stamp} drift={drift:.0f}s")

        # --- stage 3: hub read sees it ---
        p = run([sys.executable, "watcher/bridge/hub.py", "read", "1"], gh, a.verbose)
        check("stage3 hub read: newest comment is visible and timed",
              "total comments seen: 3" in p.stdout and "github_now:" in p.stdout)

        # --- stage 4: hub post appends ---
        p = run([sys.executable, "watcher/bridge/hub.py", "post", "-"], gh, a.verbose) if False else None
        env = dict(os.environ); env.update(gh)
        p = subprocess.run([sys.executable, "watcher/bridge/hub.py", "post", "-"], cwd=ROOT, env=env,
                           input="### hub post from sim\nhello", capture_output=True, text=True, timeout=60)
        check("stage4 hub post: comment appended",
              len(store.comments) == 4 and "posted id=" in p.stdout, p.stdout.strip()[:60])

        # --- stage 5: shadow self-audit ---
        env2 = dict(os.environ); env2.update(gh); env2.update(gem)
        p = subprocess.run([sys.executable, "shadow/shadow.py", "--subject",
                            "Watcher self-audit: the loop, hub, and shadow code all ran end-to-end in the simulation."],
                           cwd=ROOT, env=env2, capture_output=True, text=True, timeout=180)
        check("stage5 self-audit: shadow returns a verdict",
              "VERDICT:" in p.stdout, p.stdout.splitlines()[0] if p.stdout else p.stderr[:80])
    finally:
        if saved is not None:
            open(state, "w").write(saved)

    srv.shutdown()
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
