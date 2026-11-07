#!/usr/bin/env python3
"""One-step SwarmChat bootstrap for a swarm of agents.

    python3 swarm_setup.py --data DIR --port 8484 --agents watcher,shadow,forge

Starts a SwarmChat server (unless --no-serve), adds one user per agent, and writes
DIR/agents.env (mode 0600) holding SWARMCHAT_SERVER and one SWARMCHAT_TOKEN_<ID> per agent.
Tokens are written to that file only, never printed to stdout.

    python3 swarm_setup.py ... --demo

additionally proves the blocking wait end to end: one agent sends, another blocks on
`wait`, and the script reports PASS only if the wait returned the message.

Read-only against any running server; it only calls the local `swarmchat` CLI and the
server it started. No key, no card, no network beyond localhost.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOKEN_RE = re.compile(r"Token:\s*(\S+)")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def swarm(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return run([sys.executable, "-m", "swarmchat", *args], env=env)


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, deadline: float) -> bool:
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(0.2)
    return False


def start_server(data: str, host: str, port: int) -> subprocess.Popen:
    os.makedirs(data, exist_ok=True)
    log = open(os.path.join(data, "serve.log"), "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "swarmchat", "serve", "--data", data, "--host", host, "--port", str(port)],
        stdout=log, stderr=subprocess.STDOUT,
    )
    if not wait_for_port(host, port, time.time() + 15):
        proc.terminate()
        raise SystemExit(f"server did not open {host}:{port}; see {data}/serve.log")
    return proc


def add_agent(data: str, agent: str) -> str:
    r = swarm(["admin", "--data", data, "add", agent, "--name", agent.capitalize()])
    if r.returncode != 0:
        if "already" in (r.stdout + r.stderr).lower():
            raise SystemExit(
                f"agent '{agent}' already exists; use a fresh --data dir or drop it from --agents")
        raise SystemExit(f"could not add '{agent}': {r.stderr.strip() or r.stdout.strip()}")
    m = TOKEN_RE.search(r.stdout)
    if not m:
        raise SystemExit(f"could not read the token for '{agent}' from: {r.stdout.strip()!r}")
    return m.group(1)


def write_env(path: str, server: str, tokens: dict[str, str]) -> None:
    lines = [f"# SwarmChat env — generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
             "# Source this in each agent's shell, then set SWARMCHAT_TOKEN from the line for that agent.",
             f"SWARMCHAT_SERVER={server}", ""]
    for agent, tok in tokens.items():
        lines.append(f"SWARMCHAT_TOKEN_{agent.upper()}={tok}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")


def demo(server: str, sender: str, sender_tok: str, waiter: str, waiter_tok: str) -> bool:
    """Prove the blocking wait: start a wait, then send; PASS only if it returns the text."""
    env_w = {**os.environ, "SWARMCHAT_SERVER": server, "SWARMCHAT_TOKEN": waiter_tok}
    env_s = {**os.environ, "SWARMCHAT_SERVER": server, "SWARMCHAT_TOKEN": sender_tok}
    text = f"demo handoff {int(time.time())}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "swarmchat", "wait", "--from", sender],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env_w,
    )
    time.sleep(2)
    swarm(["send", waiter, text], env=env_s)
    try:
        out, _ = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        return False
    return proc.returncode == 0 and text in out


def main() -> int:
    ap = argparse.ArgumentParser(description="Bootstrap a SwarmChat swarm.")
    ap.add_argument("--data", required=True, help="data directory for the server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8484)
    ap.add_argument("--agents", default="watcher,shadow", help="comma-separated agent ids")
    ap.add_argument("--no-serve", action="store_true", help="use an already-running server")
    ap.add_argument("--demo", action="store_true", help="also prove the blocking wait end to end")
    args = ap.parse_args()

    probe = swarm(["--version"])
    if probe.returncode != 0:
        raise SystemExit("swarmchat is not installed: pip install swarmchat")

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    if len(agents) < 1:
        raise SystemExit("give at least one agent in --agents")

    server = f"http://{args.host}:{args.port}"
    proc = None
    if not args.no_serve:
        proc = start_server(args.data, args.host, args.port)
        print(f"server up at {server} (data {args.data})")
    elif not port_open(args.host, args.port):
        raise SystemExit(f"no server answering at {server}")

    tokens = {a: add_agent(args.data, a) for a in agents}
    env_path = os.path.join(args.data, "agents.env")
    write_env(env_path, server, tokens)
    print(f"added {len(agents)} agent(s): {', '.join(agents)}")
    print(f"tokens written to {env_path} (mode 0600); they are not printed here")

    ok = True
    if args.demo:
        if len(agents) < 2:
            raise SystemExit("--demo needs at least two agents")
        sender, waiter = agents[0], agents[1]
        ok = demo(server, sender, tokens[sender], waiter, tokens[waiter])
        print(f"blocking wait ({sender} -> {waiter}): {'PASS' if ok else 'FAIL'}")

    if proc is not None:
        print(f"server is running (pid {proc.pid}); stop it with: kill {proc.pid}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
