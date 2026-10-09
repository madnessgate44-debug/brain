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


def _validate_specialist_output(raw: str, role: Any) -> dict[str, Any]:
    """Parse and validate the complete specialist contract without accepting partial output."""
    result = _parse_json_object(raw)
    if result.get("status") not in {"PASS", "NEEDS_WORK", "BLOCKED"}:
        raise AgentOutputError("Specialist status must be PASS, NEEDS_WORK, or BLOCKED.")
    if not isinstance(result.get("deliverables"), dict):
        raise AgentOutputError("Specialist must return a deliverables object.")
    missing_deliverables = [
        key for key in role.deliverables if key not in result["deliverables"]
    ]
    if missing_deliverables:
        raise AgentOutputError(
            "Specialist omitted required deliverables: " + ", ".join(missing_deliverables)
        )
    for key in ("findings", "blockers", "evidence_needed"):
        if not isinstance(result.get(key), list):
            raise AgentOutputError(f"Specialist field '{key}' must be an array.")
    return result


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
        role_contract = ""
        if role_key == "developer":
            role_contract = (
                "\nImplementation contract: deliverables.change_set must be an object with "
                "a short 'summary' string and a 'files' array. Each array item must contain "
                "a safe repository-relative 'path' and complete UTF-8 text 'content'. "
                "Return 1–30 files, each at most 200 KB. Do not claim to have applied changes; "
                "the repository tool will commit them on an isolated branch.\n"
            )
        elif role_key == "qa_engineer":
            role_contract = (
                "\\nUse the supplied test_results from the real check runner. Do not invent "
                "test runs or mark unexecuted checks as passing.\n"
            )
        if role_key in {"ux_designer", "customer_advocate"}:
            role_contract += (
                "\\nScope applicability rule: adapt deliverables to the explicit request. "
                "For backend-only work or a request that explicitly excludes UI changes, do not "
                "block because visual mockups, screen redesign, or a visual design system are "
                "out of scope. Provide backend interaction journeys and API/response-state "
                "specifications in the required fields; mark purely visual details as not "
                "applicable with a short reason. Do not request user confirmation for a clear "
                "scope boundary. Raise a blocker only for a real unresolved product requirement.\\n"
            )
        system_prompt = (
            "You are the " + role.title + " in a software company.\\n"
            "Your responsibility: " + role.mission + "\n"
            "Use only supplied evidence. Distinguish facts, assumptions, and unknowns. "
            "Never claim that code was changed, tests were executed, a website was viewed, "
            "or a security check passed unless supplied tool evidence proves it.\n"
            "Return exactly one JSON object with keys: status, deliverables, findings, "
            "blockers, evidence_needed. status must be one of PASS, NEEDS_WORK, BLOCKED. "
            "deliverables must be an object containing every required deliverable key: "
            + ", ".join(role.deliverables)
            + ". findings, blockers, evidence_needed must be arrays."
            + role_contract
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
        try:
            result = _validate_specialist_output(raw, role)
        except AgentOutputError as first_error:
            # One bounded repair attempt handles transient formatting/schema mistakes.
            # Never silently extract JSON from prose or retry indefinitely.
            repair_system_prompt = (
                system_prompt
                + "\\nYour previous response failed strict validation: "
                + str(first_error)
                + ". Return one corrected JSON object only. Preserve the required schema; "
                + "do not add markdown fences or explanatory prose."
            )
            repair_user_prompt = json.dumps(
                {
                    "role": role.key,
                    "required_deliverables": list(role.deliverables),
                    "required_top_level_keys": [
                        "status", "deliverables", "findings", "blockers", "evidence_needed"
                    ],
                    "invalid_response_excerpt": raw[:12000],
                    "validation_error": str(first_error),
                    "original_request": user_prompt,
                },
                ensure_ascii=False,
                default=str,
            )
            repaired_raw = await self.provider.complete(
                repair_system_prompt, repair_user_prompt
            )
            try:
                result = _validate_specialist_output(repaired_raw, role)
            except AgentOutputError as second_error:
                raise AgentOutputError(
                    f"{role.key} output failed strict validation after one repair attempt: "
                    f"{second_error}"
                ) from second_error
        result["role"] = role.key
        result["role_title"] = role.title
        return result
