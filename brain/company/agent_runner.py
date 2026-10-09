"""Role-scoped execution for Brain's software-company workflow."""

import json
from typing import Any

from brain.company.llm_provider import OpenAICompatibleProvider
from brain.company.roles import ROLE_BY_KEY
from brain.company.workflow import validate_stage_entry


class AgentOutputError(ValueError):
    """Raised when a specialist returns malformed structured output."""


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse a strict JSON object; do not silently accept prose as a deliverable."""
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        if value.endswith("```"):
            value = value[:-3].strip()
        if value.startswith("json\n"):
            value = value[5:].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"Specialist output is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AgentOutputError("Specialist output must be a JSON object.")
    return parsed


class SpecialistAgentRunner:
    """Run one named specialist with explicit prerequisites and structured output."""

    def __init__(self, provider: OpenAICompatibleProvider):
        self.provider = provider

    async def run(
        self,
        role_key: str,
        user_request: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        validate_stage_entry(role_key, evidence)
        role = ROLE_BY_KEY[role_key]
        system_prompt = (
            "You are the " + role.title + " in a software company.\n"
            "Your responsibility: " + role.mission + "\n"
            "Use only supplied evidence. Distinguish facts, assumptions, and unknowns. "
            "Never claim that code was changed, tests were executed, a website was viewed, "
            "or a security check passed unless supplied tool evidence proves it.\n"
            "Return exactly one JSON object with keys: status, deliverables, findings, "
            "blockers, evidence_needed. status must be one of PASS, NEEDS_WORK, BLOCKED. "
            "deliverables must be an object. findings, blockers, evidence_needed must be arrays."
        )
        user_prompt = json.dumps(
            {
                "user_request": user_request,
                "role": role.key,
                "required_deliverables": list(role.deliverables),
                "available_evidence": evidence,
                "independence_rules": list(role.must_be_independent_of),
            },
            ensure_ascii=False,
            default=str,
        )
        raw = await self.provider.complete(system_prompt, user_prompt)
        result = _parse_json_object(raw)
        if result.get("status") not in {"PASS", "NEEDS_WORK", "BLOCKED"}:
            raise AgentOutputError("Specialist status must be PASS, NEEDS_WORK, or BLOCKED.")
        if not isinstance(result.get("deliverables"), dict):
            raise AgentOutputError("Specialist must return a deliverables object.")
        for key in ("findings", "blockers", "evidence_needed"):
            if not isinstance(result.get(key), list):
                raise AgentOutputError(f"Specialist field '{key}' must be an array.")
        result["role"] = role.key
        result["role_title"] = role.title
        return result
