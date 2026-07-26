"""人工审批决策：POST /api/approvals/{approval_id}/decide。"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import ApprovalStatus, EventType
from app.core.models import Approval, utcnow
from app.events.outbox import emit_event

router = APIRouter(tags=["approvals"])

_ACTION_TO_STATUS = {
    "approve": ApprovalStatus.APPROVED,
    "reject": ApprovalStatus.REJECTED,
    "modify": ApprovalStatus.MODIFIED,
}


class DecideRequest(BaseModel):
    action: Literal["approve", "reject", "modify"]
    note: str | None = None


def _to_dict(approval: Approval) -> dict:
    return {
        "id": str(approval.id),
        "run_id": str(approval.run_id),
        "action_type": approval.action_type,
        "status": approval.status,
        "decision_note": approval.decision_note,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: uuid.UUID, body: DecideRequest, session: Session = Depends(get_db)
) -> dict:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")

    # 幂等：已决策直接返回当前状态
    if approval.status != ApprovalStatus.PENDING.value:
        return {**_to_dict(approval), "changed": False}

    approval.status = _ACTION_TO_STATUS[body.action].value
    approval.decision_note = body.note
    approval.decided_at = utcnow()
    emit_event(
        session,
        approval.run_id,
        EventType.APPROVAL_DECIDED,
        {"approval_id": str(approval.id), "action": body.action, "note": body.note},
    )
    session.commit()
    return {**_to_dict(approval), "changed": True}
