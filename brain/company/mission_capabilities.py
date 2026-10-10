"""Mission capability planning: determine the minimum capabilities before credential checks."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityPlan:
    mode: str
    required_capabilities: tuple[str, ...]
    rationale: str


_WRITE_ACTION = re.compile(
    r"\b(fix|implement|edit|modify|change|create|add|remove|delete|refactor|repair|"
    r"build|commit|push|deploy|merge|write|update|rewrite|patch|apply)\b",
    re.IGNORECASE,
)


def plan_capabilities(objective: str) -> CapabilityPlan:
    """Classify the requested operation before any permission preflight.

    Read-only is the safe default. Explicit mutation verbs require write capability.
    A mission requesting both inspection and changes is classified as mutating.
    """
    matches = sorted({match.group(0).casefold() for match in _WRITE_ACTION.finditer(objective or "")})
    if matches:
        return CapabilityPlan(
            mode="mutating",
            required_capabilities=("repository:read", "repository:write", "checks:run", "pull_request:create"),
            rationale=f"Explicit mutation intent detected: {', '.join(matches)}.",
        )
    return CapabilityPlan(
        mode="read_only",
        required_capabilities=("repository:read", "model:invoke"),
        rationale="No explicit repository mutation action was requested; read-only is the default.",
    )
