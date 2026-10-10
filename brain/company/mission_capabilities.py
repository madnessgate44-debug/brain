"""Mission capability planning: determine the minimum capabilities before credential checks."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityPlan:
    mode: str
    required_capabilities: tuple[str, ...]
    rationale: str


_MUTATION_INTENT = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|repair(?:s|ed|ing)?|refactor(?:s|ed|ing)?|"
    r"implement(?:s|ed|ing)?|edit(?:s|ed|ing)?|modify|modifies|modified|modifying|"
    r"change(?:s|d|ing)?|create(?:s|d|ing)?|add(?:s|ed|ing)?|remove(?:s|d|ing)?|"
    r"delete(?:s|d|ing)?|update(?:s|d|ing)?|rewrite|rewrites|rewrote|rewriting|"
    r"patch(?:es|ed|ing)?|apply|applies|applied|applying|build|builds|built|building)"
    r"\s+(?:(?:the|all|any|these|those|identified|critical|top|following|new|existing|"
    r"target|repository|source|main|necessary|recommended)\s+){0,3}"
    r"(?:files?|code|repository|feature|functionality|bug|issues?|defects?|errors?|"
    r"problems?|fixes?|changes?|patches?|branch|pull requests?|prs?|commits?|"
    r"implementation|app|application|them|it)\b"
    r"|\b(?:open|create)\s+(?:a\s+)?(?:pull request|pr|branch|commit|file)\b"
    r"|\b(?:commit|push)\s+(?:the\s+)?(?:changes?|files?|code|branch|commit)\b"
    r"|\b(?:deploy|merge)\b"
    r"|\bmake\s+(?:the\s+)?changes?\b",
    re.IGNORECASE,
)


def plan_capabilities(objective: str) -> CapabilityPlan:
    """Classify requested operations before credential checks.

    The classifier detects affirmative repository mutation intent, not mere mentions
    of words such as "build", "commit", or "write" in audit coverage requirements.
    Negated constraint lines are removed before intent detection. Read-only is the
    default when no affirmative mutation operation is identified.
    """
    objective_text = objective or ""
    objective_text = "\n".join(
        line for line in objective_text.splitlines()
        if not re.match(r"^\s*(?:[-*]\s*)?(?:do not|don't|never|must not)\b", line, re.IGNORECASE)
    )
    objective_text = re.sub(
        r"\b(?:do not|don't|never|no need to)\s+(?:[a-z]+\s+){0,2}"
        r"(?:fix|repair|refactor|implement|edit|modify|change|create|add|remove|delete|"
        r"update|rewrite|patch|apply|build|commit|push|deploy|merge|write)\b",
        " ",
        objective_text,
        flags=re.IGNORECASE,
    )
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
