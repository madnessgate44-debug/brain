"""Mission capability planning: determine the minimum capabilities before credential checks."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityPlan:
    mode: str
    required_capabilities: tuple[str, ...]
    rationale: str


# Mutation is detected from affirmative verb-object requests. Bare mentions of
# "merge" or "deploy" are not enough: they commonly occur in audit constraints.
_MUTATION_INTENT = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|repair(?:s|ed|ing)?|refactor(?:s|ed|ing)?|"
    r"implement(?:s|ed|ing)?|edit(?:s|ed|ing)?|modify|modifies|modified|modifying|"
    r"change(?:s|d|ing)?|create(?:s|d|ing)?|add(?:s|ed|ing)?|remove(?:s|ed|ing)?|"
    r"delete(?:s|d|ing)?|update(?:s|d|ing)?|rewrite|rewrites|rewrote|rewriting|"
    r"patch(?:es|ed|ing)?|apply|applies|applied|applying|build|builds|built|building)"
    r"\s+(?:(?:the|all|any|these|those|identified|critical|top|following|new|existing|"
    r"target|repository|source|main|necessary|recommended|reported|remaining)\s+){0,3}"
    r"(?:files?|code|repository|feature|functionality|bug|issues?|defects?|errors?|"
    r"problems?|fixes?|changes?|patches?|branch|pull requests?|prs?|commits?|"
    r"implementation|app|application|them|it)\b"
    r"|\b(?:open|create)\s+(?:a\s+)?(?:pull request|pr|branch|commit|file)\b"
    r"|\b(?:commit|push)\s+(?:the\s+)?(?:changes?|files?|code|branch|commit)\b"
    r"|\b(?:deploy|merge)\s+(?:the\s+)?(?:app|application|changes?|branch|pull request|pr|release)\b"
    r"|\bmake\s+(?:the\s+)?changes?\b",
    re.IGNORECASE,
)

_NEGATED_CLAUSE = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|without)\b[^.!?\n]*(?:[.!?]|$)",
    re.IGNORECASE,
)


def plan_capabilities(objective: str) -> CapabilityPlan:
    """Classify affirmative mutation requests, ignoring negated constraint clauses.

    Read-only is the default. Negated lists are removed at sentence level, not
    merely when a line starts with "Do not", so audit prompts containing phrases
    such as "do not merge, deploy, or change settings" cannot trigger write mode.
    """
    objective_text = objective or ""
    objective_text = _NEGATED_CLAUSE.sub(" ", objective_text)
    matches = sorted({match.group(0).casefold() for match in _MUTATION_INTENT.finditer(objective_text)})
    if matches:
        return CapabilityPlan(
            mode="mutating",
            required_capabilities=("repository:read", "repository:write", "checks:run", "pull_request:create"),
            rationale=f"Affirmative mutation intent detected: {', '.join(matches)}.",
        )
    return CapabilityPlan(
        mode="read_only",
        required_capabilities=("repository:read", "model:invoke"),
        rationale="No affirmative repository mutation action was requested; read-only is the default.",
    )
