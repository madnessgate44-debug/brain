#!/usr/bin/env python3
"""Reverse-engineer a public repository (WATCHER.md §7, the "core job").

Read-only. Reads a public repo through the GitHub API (bounded), maps its structure,
picks the files that carry the architecture, and writes a dissection: what it is, how it
is built, the algorithms worth extracting, and how it maps to Forge/brain and the
Claude-Code-like north star. Never clones, installs, or executes third-party code.

    python3 reverse.py <owner/repo | github URL> [--ref main] [--path src/x.ts]
                       [--max-files 12] [--out DIR] [--no-ai]

Needs GITHUB_TOKEN for private repos and to avoid rate limits; public repos work
anonymously at low volume.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
GEMINI_FALLBACKS = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"

SECTIONS = ("What it is", "How it is built", "Algorithms worth extracting",
            "What to steal for Forge", "What to steal for brain", "North-star move")

# Files that usually carry the architecture, best first.
NOTABLE = re.compile(
    r"(^|/)(readme|architecture|design|agents?|loop|tools?|runner|orchestrat|kernel|"
    r"planner|memory|session|skills?|hooks?|repomap|context|prompt|config)\.(md|py|ts|js|go|rs)$",
    re.I,
)


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "repo"


def _get(url: str, token: str | None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "watcher-reverse"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as x:
        return json.load(x)


def parse_repo(spec: str) -> str:
    """Accept 'owner/repo' or any github URL and return 'owner/repo'."""
    m = re.search(r"github\.com[/:]([^/]+)/([^/#?]+)", spec)
    if m:
        return f"{m.group(1)}/{m.group(2).removesuffix('.git')}"
    if re.match(r"^[^/\s]+/[^/\s]+$", spec):
        return spec
    raise SystemExit(f"cannot parse a repository from {spec!r}")


def repo_tree(repo: str, ref: str, token: str | None) -> tuple[dict, list[str]]:
    """Return (repo metadata, sorted blob paths). Raises SystemExit if unreachable."""
    try:
        meta = _get(f"{API}/repos/{repo}", token)
        tree = _get(f"{API}/repos/{repo}/git/trees/{ref}?recursive=1", token)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"cannot read {repo}@{ref}: HTTP {e.code}")
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    return meta, paths


def pick_files(paths: list[str], max_files: int) -> list[str]:
    """Notable files first (shallow first), then any remaining source files."""
    def depth(p: str) -> int:
        return p.count("/")

    notable = sorted([p for p in paths if NOTABLE.search(p)], key=lambda p: (depth(p), p))
    rest = sorted([p for p in paths if p not in set(notable) and p.endswith((".py", ".ts", ".js", ".go", ".rs", ".md"))],
                  key=lambda p: (depth(p), p))
    return (notable + rest)[:max_files]


def fetch_file(repo: str, path: str, ref: str, token: str | None, limit: int = 6000) -> str:
    try:
        d = _get(f"{API}/repos/{repo}/contents/{path}?ref={ref}", token)
    except urllib.error.HTTPError:
        return ""
    if not isinstance(d, dict) or d.get("encoding") != "base64":
        return ""
    try:
        text = base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    return text[:limit]


def _gemini(prompt: str, key: str) -> str | None:
    for m in GEMINI_FALLBACKS:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(GEMINI_URL.format(m=m, k=key), data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as x:
                return json.load(x)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            log(f"  gemini {m}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            log(f"  gemini {m}: {type(e).__name__}")
    return None


ANALYSIS_PROMPT = """You are reverse-engineering a public repository to extract what is worth
copying into two agents: "Forge" (a deterministic coding agent) and "brain" (a mission
orchestrator). The owner's north star is a Claude-Code-like experience (arbitrary shell,
skills, hooks, session resume, parallel subagents, long-horizon loops).

Read the file excerpts. Do not invent files or facts you cannot see. If a section is not
supported by the excerpts, write "not shown in the files read".

Output EXACTLY these headings, in this order:

## What it is
One paragraph: what this project does and its architecture in outline.

## How it is built
The modules that matter and how they fit (bullets, cite the file paths you saw).

## Algorithms worth extracting
The specific, nameable techniques (e.g. PageRank repo map, context budgeting, retry policy).

## What to steal for Forge
Concrete, bounded changes to Forge, each with the file/idea to port.

## What to steal for brain
Same for brain.

## North-star move
The single highest-value change toward a Claude-Code-like experience.

REPO: {repo}
FILES:
{files}
---"""


def build_dissection(repo: str, meta: dict, files: dict[str, str], key: str | None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    head = [f"# Reverse engineering — {repo}", "",
            f"- **Repo:** {meta.get('html_url', repo)}",
            f"- **Language:** {meta.get('language') or 'unknown'}",
            f"- **Stars:** {meta.get('stargazers_count')}",
            f"- **License:** {(meta.get('license') or {}).get('spdx_id') or 'none'}",
            f"- **Read:** {ts} by the Watcher (WATCHER.md §7)", ""]
    if not key:
        body = []
        for s in SECTIONS:
            body += [f"## {s}", "_TODO: no model route (OHGeminiAPI not set) — not analysed._", ""]
    else:
        blob = "\n\n".join(f"### {p}\n```\n{txt}\n```" for p, txt in files.items())
        reply = _gemini(ANALYSIS_PROMPT.format(repo=repo, files=blob[:40000]), key)
        if not reply:
            body = [f"## {SECTIONS[0]}", "_TODO: model route failed — not analysed._", ""]
            for s in SECTIONS[1:]:
                body += [f"## {s}", "_TODO: not analysed._", ""]
        else:
            got = {}
            cur = None
            for line in reply.splitlines():
                m = re.match(r"^##\s+(.+?)\s*$", line)
                if m:
                    cur = m.group(1).strip(); got[cur] = ""
                elif cur:
                    got[cur] += line + "\n"
            body = []
            for s in SECTIONS:
                body += [f"## {s}", got.get(s, "_not shown in the files read_").strip(), ""]
    listing = "\n".join(f"- `{p}`" for p in files)
    body += ["## Files read", "", listing, ""]
    return "\n".join(head + body)


def main() -> int:
    ap = argparse.ArgumentParser(description="Reverse-engineer a public repo (WATCHER.md §7)")
    ap.add_argument("repo", help="owner/repo or a GitHub URL")
    ap.add_argument("--ref", default="", help="branch, tag, or sha (default: the repo default)")
    ap.add_argument("--max-files", type=int, default=12)
    ap.add_argument("--out", default="watcher/knowledge/reverse")
    ap.add_argument("--no-ai", action="store_true")
    a = ap.parse_args()

    repo = parse_repo(a.repo)
    token = os.environ.get("GITHUB_TOKEN")
    meta, paths = repo_tree(repo, a.ref or "HEAD", token)
    ref = a.ref or meta.get("default_branch", "main")
    if not a.ref:
        meta, paths = repo_tree(repo, ref, token)
    log(f"{repo}@{ref}: {len(paths)} files")
    picked = pick_files(paths, a.max_files)
    log(f"reading {len(picked)} file(s): {', '.join(picked)}")
    files = {p: fetch_file(repo, p, ref, token) for p in picked}
    files = {p: t for p, t in files.items() if t}

    key = None if a.no_ai else (os.environ.get("OHGeminiAPI") or os.environ.get("GEMINI_API_KEY"))
    if not key:
        log("no key set - writing an honest scaffold (no findings invented)")
    md = build_dissection(repo, meta, files, key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{slugify(repo.replace('/', '-'))}.md"
    dest.write_text(md, encoding="utf-8")
    log(f"done -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
