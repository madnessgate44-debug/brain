#!/usr/bin/env python3
"""Fan a daily report out to every integrated communication channel.

The report is the deliverable of brain's audit loop. This script posts one Markdown
report to each channel that is reachable in the current run and prints an honest,
per-channel result table (posted / skipped / failed). A channel that is not
configured is reported as skipped, never as posted.

Channels:
  github  - a comment on the durable reporting issue (survives sandbox resets).
  swarmchat - the live agent bus (#reports, #audits); needs a reachable server.

Reads the report body from a file (``--body FILE``) or stdin. Never prints or
writes a secret value; the tokens are only ever put into request headers.

    python3 scripts/report_to_channels.py --body report.md
    python3 scripts/report_to_channels.py --body report.md --channels github
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

GITHUB_REPO = os.environ.get("REPORT_REPO", "madnessgate44-debug/brain")
GITHUB_ISSUE = int(os.environ.get("REPORT_ISSUE", "292"))
SWARM_CHANNELS = ("#reports", "#audits")


@dataclass
class Result:
    channel: str
    status: str  # posted | skipped | failed
    detail: str = ""


def _post_json(url: str, body: dict, headers: dict) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode("utf-8", "replace")


def post_github(report: str) -> Result:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return Result("github", "skipped", "GITHUB_TOKEN not set")
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{GITHUB_ISSUE}/comments"
    try:
        status, _ = _post_json(
            url,
            {"body": report},
            {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        return Result("github", "posted", f"HTTP {status} on issue #{GITHUB_ISSUE}")
    except urllib.error.HTTPError as e:
        return Result("github", "failed", f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001 - report any transport failure honestly
        return Result("github", "failed", type(e).__name__)


SWARM_MAX_TEXT = 19000  # the server's max_text default is 20000


def _clip_for_swarm(report: str) -> str:
    if len(report) <= SWARM_MAX_TEXT:
        return report
    tail = f"\n\n[truncated — full report on the GitHub issue #{GITHUB_ISSUE}]"
    return report[: SWARM_MAX_TEXT - len(tail)] + tail


def post_swarmchat(report: str, channels: tuple[str, ...]) -> list[Result]:
    server = os.environ.get("SWARMCHAT_SERVER")
    token = os.environ.get("SWARMCHAT_TOKEN")
    if not (server and token):
        return [Result("swarmchat", "skipped", "SWARMCHAT_SERVER/TOKEN not set")]
    text = _clip_for_swarm(report)
    out: list[Result] = []
    for ch in channels:
        try:
            status, _ = _post_json(
                f"{server.rstrip('/')}/v1/send",
                {"chat": ch, "text": text},
                {"Authorization": f"Bearer {token}"},
            )
            out.append(Result(f"swarmchat {ch}", "posted", f"HTTP {status}"))
        except urllib.error.HTTPError as e:
            out.append(Result(f"swarmchat {ch}", "failed", f"HTTP {e.code}"))
        except Exception as e:  # noqa: BLE001
            out.append(Result(f"swarmchat {ch}", "failed", type(e).__name__))
    return out


def render(results: list[Result]) -> str:
    lines = ["| channel | result | detail |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r.channel} | {r.status} | {r.detail} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Post a report to every integrated channel.")
    ap.add_argument("--body", help="path to the report Markdown (default: stdin)")
    ap.add_argument(
        "--channels",
        default="github,swarmchat",
        help="comma list of channels to try (default: github,swarmchat)",
    )
    args = ap.parse_args(argv)

    report = Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.read()
    if not report.strip():
        print("empty report; nothing posted", file=sys.stderr)
        return 2

    wanted = [c.strip() for c in args.channels.split(",") if c.strip()]
    results: list[Result] = []
    if "github" in wanted:
        results.append(post_github(report))
    if "swarmchat" in wanted:
        results.extend(post_swarmchat(report, SWARM_CHANNELS))

    print(render(results))
    return 0 if any(r.status == "posted" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
