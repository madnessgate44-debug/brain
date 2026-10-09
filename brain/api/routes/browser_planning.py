"""Authenticated natural-language browser planning endpoint."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from brain.company.llm_provider import ModelProviderError, ProviderConfigurationError
from brain.company.settings import get_setting
from brain.runtime.workers.browser_planner import BrowserPlanner, BrowserPlanningError

router = APIRouter(prefix="/browser", tags=["browser"])


class BrowserPlanRequest(BaseModel):
    """A natural-language objective to translate into a proposed browser plan."""

    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=1, max_length=10_000)


@router.post("/plan")
async def plan_browser_task(
    data: BrowserPlanRequest,
    api_key: str | None = Header(default=None, alias="X-Brain-API-Key"),
):
    """Plan actions only; this endpoint never starts a browser mission."""
    expected_key = get_setting("BRAIN_CONTROL_API_KEY")
    if not expected_key or len(expected_key) < 24:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser planning is disabled until BRAIN_CONTROL_API_KEY is configured securely.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Brain control key.",
        )
    try:
        plan = await BrowserPlanner().plan(data.objective)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except BrowserPlanningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        **plan,
        "next_step": (
            "Review these exact actions. Submit them to POST /browser/tasks with "
            "owner_approved=true only after explicitly approving any external changes."
        ),
    }
