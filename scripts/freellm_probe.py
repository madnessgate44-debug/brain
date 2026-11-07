#!/usr/bin/env python3
"""Bounded, metadata-only probe for the pinned FreeLLMPool proxy."""
import json
import os
import time
import urllib.error
import urllib.request
BASE = "http://127.0.0.1:8080"
AUTH = {"Authorization": "Bearer unused"}
MARKER_PREFIX = "PROBE_OK_"
def request(path, payload=None, timeout=60):
    headers = dict(AUTH)
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return response.status, response.headers, body, round((time.monotonic() - started) * 1000)
    except urllib.error.HTTPError as exc:
        # Never print provider/proxy response bodies.
        return exc.code, exc.headers, b"", round((time.monotonic() - started) * 1000)
    except Exception as exc:
        print(f"Request transport failure for {path}: {type(exc).__name__}")
        return 0, {}, b"", round((time.monotonic() - started) * 1000)
def json_body(body):
    try:
        value = json.loads(body.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
def write_table(title, headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = [f"### {title}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)
    block = "\n".join(lines) + "\n"
    print(block)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(block + "\n")
def main():
    deadline = time.monotonic() + 90
    ready = False
    while time.monotonic() < deadline:
        status, _, _, _ = request("/readyz", timeout=5)
        if status == 200:
            ready = True
            break
        time.sleep(3)
    if not ready:
        print("STOP: FreeLLMPool /readyz did not return HTTP 200 within 90 seconds.")
        return 1
    status, _, body, _ = request("/v1/models?ready=true", timeout=15)
    if status != 200:
        print(f"STOP: ready model inventory returned HTTP {status}; response body suppressed.")
        return 1
    inventory = json_body(body)
    models = inventory.get("data", [])
    if not isinstance(models, list):
        print("STOP: /v1/models?ready=true returned an unexpected JSON shape.")
        return 1

    # Also validate the documented provider inventory endpoint without printing its body.
    provider_status, _, provider_body, _ = request("/v1/providers", timeout=15)
    if provider_status != 200:
        print(f"STOP: provider inventory returned HTTP {provider_status}; response body suppressed.")
        return 1
    providers_doc = json_body(provider_body)
    provider_rows = providers_doc.get("providers", [])
    known_provider_ids = set()
    if isinstance(provider_rows, list):
        for item in provider_rows:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                known_provider_ids.add(item["id"])

    chosen = []
    seen = set()
    for item in models:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        route_id = item["id"]
        if "/" not in route_id:
            continue
        provider = route_id.split("/", 1)[0]
        if provider in seen:
            continue
        # Inventory IDs are the authority; provider endpoint is observational only.
        seen.add(provider)
        chosen.append((provider, route_id))
        if len(chosen) == 6:
            break

    if not chosen:
        print("STOP: no ready provider/model IDs were returned.")
        return 1

    rows = []
    any_http_success = False
    marker_found_any = False
    for index, (provider, route_id) in enumerate(chosen):
        if index:
            time.sleep(2)
        marker = MARKER_PREFIX + os.urandom(4).hex()
        payload = {
            "model": route_id,
            "temperature": 0,
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with exactly " + marker}],
        }
        status, headers, body, latency = request("/v1/chat/completions", payload, timeout=75)
        if status in (401, 403):
            rows.append((route_id, "not returned", status, latency, "not available", "not available", False))
            write_table("Keyless route probe (stopped on authentication response)",
                        ["Route ID", "Response model", "HTTP", "Latency ms", "Finish", "Usage integers", "Marker found"],
                        rows)
            print(f"STOP: route {route_id} returned HTTP {status}; it is credentialed and does not qualify.")
            return 1
        result = json_body(body)
        response_model = result.get("model", "not returned")
        choices = result.get("choices", [])
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        finish = choice.get("finish_reason", "not returned")
        usage = result.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        usage_ints = {
            key: usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool)
        }
        content = ""
        message = choice.get("message", {})
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"]
        marker_found = marker in content
        any_http_success = any_http_success or status == 200
        marker_found_any = marker_found_any or (status == 200 and marker_found)
        rows.append((route_id, response_model, status, latency, finish, json.dumps(usage_ints, sort_keys=True), marker_found))

    write_table("Keyless route probe",
                ["Route ID", "Response model", "HTTP", "Latency ms", "Finish", "Usage integers", "Marker found"],
                rows)

    if not any_http_success:
        print("STOP: every selected route request failed; context probes skipped.")
        return 1

    context_rows = []
    for label, repetitions in (("~24,000 characters", 511), ("~100,000 characters", 2128)):
        prompt = ("Neutral context text for capacity measurement. " * repetitions)
        prompt += "\nReply with exactly CONTEXT_OK."
        payload = {
            "model": "auto",
            "temperature": 0,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": prompt}],
        }
        status, headers, body, latency = request("/v1/chat/completions", payload, timeout=90)
        route = headers.get("X-Freellmpool-Provider", "not reported")
        if status in (200, 401, 403):
            data = json_body(body)
            meta = data.get("x_freellmpool", {})
            if isinstance(meta, dict) and isinstance(meta.get("provider"), str):
                route = meta["provider"]
        if status in (401, 403):
            context_rows.append((label, status, route))
            write_table("Context-size probes", ["Input size", "HTTP", "Route"], context_rows)
            print(f"STOP: context probe returned HTTP {status}; route is credentialed and does not qualify.")
            return 1
        context_rows.append((label, status, route))
    write_table("Context-size probes", ["Input size", "HTTP", "Route"], context_rows)
    print("PROBE_OK: at least one keyless route returned the exact marker." if marker_found_any
          else "PROBE_FAILED: no selected route returned its exact marker.")
    return 0 if marker_found_any else 1


if __name__ == "__main__":
    raise SystemExit(main())
