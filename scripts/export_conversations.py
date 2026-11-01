#!/usr/bin/env python3
"""Export OpenHands Cloud conversations into a dated, verbatim daily log.

Owner request (2026-11-01): keep a daily log on the repo with the complete transcript of
all conversations, including everything the owner said.

Design:
- Enumerate conversations via /api/v1/app-conversations/search (paginate to exhaustion).
- Pull events per conversation via /api/v1/conversation/{id}/events/search (paginate; 429 backoff).
- Raw events -> <raw-dir>/<id>.events.json.gz (+ .sha256). Readable render -> the daily log.
- Owner lines are reproduced verbatim (garbled speech preserved). Agent lines are trimmed of
  system/hook noise and marked; tool chatter is omitted from the log but kept in the raw file.
- Secrets are redacted in both the raw and readable output before anything is written to git.

Never invent counts: report only what the API returned.
"""
from __future__ import annotations

import argparse
import gzip
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://app.all-hands.dev/api/v1"
KEY = os.environ.get("OPENHANDS_API_KEY", "")

SECRET_PATTERNS = [
    (re.compile(r"gAAAAA[A-Za-z0-9_\-]{20,}"), "[REDACTED-FERNET]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED-OPENAI]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghu_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
     "[REDACTED-GITHUB]"),
    (re.compile(r"https://[A-Za-z0-9_\-]+@github\.com"), "https://[REDACTED]@github.com"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "[REDACTED-GOOGLE]"),
    (re.compile(r"AQ\.[A-Za-z0-9_\-]{40,}"), "[REDACTED-GOOGLE]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "[REDACTED-PRIVATE-KEY]"),
]


def redact(text: str) -> str:
    for pat, repl in SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _get(url: str, tries: int = 6) -> dict:
    for i in range(tries):
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + KEY)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(60, 5 * (i + 1))
                print(f"  429, backing off {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"gave up after {tries} tries: {url}")


def list_conversations() -> list[dict]:
    out, nxt = [], None
    while True:
        u = f"{API}/app-conversations/search?limit=100" + (f"&page_id={urllib.parse.quote(nxt)}" if nxt else "")
        d = _get(u)
        out += d.get("items", [])
        nxt = d.get("next_page_id")
        if not nxt:
            break
    return out


def pull_events(cid: str) -> tuple[list[dict], int]:
    out, nxt, pages = [], None, 0
    while True:
        u = f"{API}/conversation/{cid}/events/search?limit=100" + (f"&page_id={urllib.parse.quote(nxt)}" if nxt else "")
        d = _get(u)
        out += d.get("items", [])
        pages += 1
        nxt = d.get("next_page_id")
        if not nxt:
            break
    return out, pages


def text_of(block) -> str:
    """Flatten an llm_message.content (list of blocks) to plain text."""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        if block.get("type") == "text":
            return block.get("text", "")
        if "text" in block:
            return block["text"]
    if isinstance(block, list):
        return "".join(text_of(b) for b in block)
    return ""


# Automation runs inject a single machine-written prompt; those are not the owner's words.
AUTOMATION_TITLE_PREFIXES = (
    "Openhands loop —", "Openhands loop -", "Watcher engagement heartbeat",
    "Watcher channel -", "GitHub Issue #",
)
TEMPLATE_PREFIXES = (
    "## Cloned Repositories", "You are requested to fix issue", "Read the attached",
    "[Stop hook feedback]", "You are OpenHands", "## Task", "# Task",
    "The following repositories have been cloned",
)


def is_automation_conversation(c: dict) -> bool:
    return any(str(c.get("title", "")).startswith(p) for p in AUTOMATION_TITLE_PREFIXES)


def looks_like_template(text: str) -> bool:
    t = text.lstrip()
    return any(t.startswith(p) for p in TEMPLATE_PREFIXES)


def is_human_user(e: dict) -> bool:
    """True only for text the human actually typed (not hook/system feedback)."""
    return e.get("source") == "user" and "llm_message" in e


def is_agent_message(e: dict) -> bool:
    return e.get("source") == "agent" and "llm_message" in e and e["llm_message"].get("role") == "assistant"


def is_agent_thought(e: dict) -> bool:
    return e.get("source") == "agent" and bool(e.get("thought"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def render_conversation(c: dict, events: list[dict]) -> str:
    automation = is_automation_conversation(c)
    lines = [f"### {c.get('title', '(untitled)')}",
             f"- conversation: `{c['id']}`  |  created {c.get('created_at','')}  |  sandbox `{c.get('sandbox_status','?')}`",
             f"- events: {len(events)}  |  type: {'automation run' if automation else 'interactive session'}"]
    for e in events:
        ts = str(e.get("timestamp", ""))[11:19]
        if is_human_user(e):
            body = text_of(e["llm_message"].get("content")).strip()
            if not body:
                continue
            if automation or looks_like_template(body):
                lines.append(f"\n**[{ts}] automation prompt (not the owner):**\n\n> " +
                             body[:400].replace("\n", "\n> ") + (" …" if len(body) > 400 else ""))
            else:
                lines.append(f"\n**[{ts}] OWNER (verbatim):**\n\n> " + body.replace("\n", "\n> "))
        elif is_agent_message(e):
            body = text_of(e["llm_message"].get("content")).strip()
            if body:
                lines.append(f"\n**[{ts}] Watcher/agent:**\n\n" + body)
    return "\n".join(lines) + "\n"


def owner_text(e: dict) -> str | None:
    """Return the owner's verbatim text for a user event, or None if it is a template."""
    if not is_human_user(e):
        return None
    body = text_of(e["llm_message"].get("content")).strip()
    if not body or looks_like_template(body):
        return None
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description="Export OpenHands conversations to a daily log")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    help="YYYY-MM-DD (UTC); selects conversations created that day")
    ap.add_argument("--out", default="docs/sessions", help="directory for the dated log")
    ap.add_argument("--raw-dir", default=".openhands/export/raw", help="directory for gzipped raw events")
    ap.add_argument("--from-raw", action="store_true",
                    help="render from cached raw files (no API calls; re-pull with --refresh)")
    a = ap.parse_args()
    if not a.from_raw and not KEY:
        print("OPENHANDS_API_KEY not set", file=sys.stderr)
        return 1

    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.raw_dir, exist_ok=True)

    if a.from_raw:
        convos = []
        for p in sorted(glob.glob(os.path.join(a.raw_dir, "*.events.json.gz"))):
            d = json.loads(gzip.open(p).read())
            if str(d["conversation"].get("created_at", "")).startswith(a.date):
                convos.append(d["conversation"])
        convos.sort(key=lambda c: c["created_at"])
    else:
        convos = [c for c in list_conversations() if str(c.get("created_at", "")).startswith(a.date)]
        convos.sort(key=lambda c: c["created_at"])
    print(f"conversations created {a.date}: {len(convos)}")

    sections, manifest = [], []
    for c in convos:
        cid = c["id"]
        automation = is_automation_conversation(c)
        if a.from_raw:
            d = json.loads(gzip.open(os.path.join(a.raw_dir, f"{cid}.events.json.gz")).read())
            events, pages = d["events"], None
        else:
            try:
                events, pages = pull_events(cid)
            except Exception as ex:  # noqa: BLE001
                print(f"  FAILED {cid}: {ex}", file=sys.stderr)
                return 1
            raw = redact(json.dumps({"conversation": c, "events": events}, ensure_ascii=False)).encode()
            gz = gzip.compress(raw)
            rp = os.path.join(a.raw_dir, f"{cid}.events.json.gz")
            with open(rp, "wb") as f:
                f.write(gz)
            with open(rp + ".sha256", "w") as f:
                f.write(sha256_bytes(gz) + "\n")
        n_owner = 0 if automation else sum(1 for e in events if owner_text(e))
        n_agent = sum(1 for e in events if is_agent_message(e))
        manifest.append({"id": cid, "title": c.get("title"), "events": len(events), "pages": pages,
                         "owner_messages": n_owner, "agent_messages": n_agent,
                         "automation": automation,
                         "sandbox_status": c.get("sandbox_status"),
                         "raw_sha256": sha256_bytes(gzip.compress(
                             redact(json.dumps({"conversation": c, "events": events}, ensure_ascii=False)).encode()))})
        sections.append(render_conversation(c, events))
        print(f"  {cid[:12]} events={len(events)} owner={n_owner} agent={n_agent}"
              f"{' [automation]' if automation else ''}")

    header = [f"# Session log — {a.date} (verbatim owner transcript)",
              "",
              f"Complete transcript of every conversation created on {a.date} (UTC), from the OpenHands",
              "Cloud API. Owner lines are verbatim (garbled speech preserved). Tool chatter, system",
              "feedback, and automation prompts are not the owner and are marked as such or omitted;",
              "the gzipped raw events under the raw directory hold everything.",
              "",
              f"Conversations: {len(convos)} | owner messages: {sum(m['owner_messages'] for m in manifest)}"
              f" | agent messages: {sum(m['agent_messages'] for m in manifest)}",
              ""]
    body = redact("\n".join(header) + "\n".join(sections))
    out_path = os.path.join(a.out, f"{a.date}.md")
    with open(out_path, "w") as f:
        f.write(body)
    with open(os.path.join(a.out, f"{a.date}.manifest.json"), "w") as f:
        json.dump({"date": a.date, "count": len(convos), "conversations": manifest}, f, indent=1)
    print(f"wrote {out_path} ({len(body)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
