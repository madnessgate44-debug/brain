"""Safe, durable escalation requests for blocked software-company workflows.

Escalation payloads contain blocker metadata, never credential values or raw provider
responses. A deployment secret manager remains the only supported place for secrets.
"""

from typing import Any


class WorkflowEscalationRequired(RuntimeError):
    """A workflow needs an operator to restore a missing capability or configuration."""

    def __init__(
        self,
        code: str,
        summary: str,
        *,
        missing_settings: tuple[str, ...] = (),
        suggested_action: str = "Review the blocker and restore the required capability.",
        retryable: bool = True,
    ):
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.missing_settings = tuple(
            name for name in missing_settings
            if name and name.replace("_", "").isalnum()
        )
        self.suggested_action = suggested_action
        self.retryable = retryable

    def to_request(self, mission_id: str) -> dict[str, Any]:
        """Return a safe request suitable for mission events and artifacts."""
        return {
            "schema_version": 1,
            "mission_id": mission_id,
            "status": "OPEN",
            "blocker_code": self.code,
            "summary": self.summary,
            "missing_settings": list(self.missing_settings),
            "suggested_action": self.suggested_action,
            "retryable": self.retryable,
            "secret_values_included": False,
            "resolution": (
                "Configure required values in the deployment/runtime secret manager, "
                "then resume or restart the paused mission."
            ),
        }
