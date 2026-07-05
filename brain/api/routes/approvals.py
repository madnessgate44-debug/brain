"""Approval API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from brain.schemas.approval import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalResponseCreate,
)
from brain.services.approval_service import ApprovalService
from brain.api.deps import get_approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/missions/{mission_id}/approvals", response_model=ApprovalRequestResponse)
async def create_approval_request(
    mission_id: str,
    data: ApprovalRequestCreate,
    service: ApprovalService = Depends(get_approval_service),
):
    """Create an approval request for a mission."""
    try:
        approval = await service.create_approval_request(mission_id, data)
        return approval
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{approval_id}/respond", response_model=ApprovalRequestResponse)
async def respond_to_approval(
    approval_id: str,
    data: ApprovalResponseCreate,
    service: ApprovalService = Depends(get_approval_service),
):
    """Respond to an approval request."""
    try:
        approval = await service.respond_to_approval(approval_id, data)
        return approval
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))