#!/usr/bin/env python3
"""Shadow's key pool (WATCHER.md §14). Labels and status only — never values.

The pool holds every free Gemini route Shadow may use. A route is (key label, model).
Shadow walks the pool on quota/rate errors, so one exhausted key never stops the job.
Values live only in the environment (secrets store); this module reports labels.
"""
from __future__ import annotations

import os

# Key labels, in preference order. Values come from the environment at call time.
KEY_LABELS = ["OHGeminiAPI"] + [f"GEMINI_POOL_{i}" for i in range(1, 8)]

# Models in tier order: fastest/cheapest first, strongest last.
MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
]


def _load_pool_file() -> None:
    """Load pool keys from a local file outside the repo (never committed).

    Secrets created mid-session are not injected into the running session, so the
    pool is read from a 0600 file that lives outside the repo. Values are never logged.
    """
    path = os.environ.get("SHADOW_POOL_FILE", "/workspace/shadow-pool.env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            k, _, v = line[len("export "):].partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def available_keys() -> list[tuple[str, str]]:
    """(label, value) for every key present. Values never logged."""
    _load_pool_file()
    out = []
    for label in KEY_LABELS:
        v = os.environ.get(label)
        if v:
            out.append((label, v))
    return out


def routes() -> list[tuple[str, str, str]]:
    """(key_label, key_value, model) for every usable route, keys outermost.

    Key-outermost means we exhaust all models on key 1 before moving to key 2 —
    each key has its own quota, so this maximises calls before any key is idle.
    """
    ks = available_keys()
    return [(lab, val, m) for lab, val in ks for m in MODELS]
