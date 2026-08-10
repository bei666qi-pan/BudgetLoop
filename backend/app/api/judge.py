"""Public judge state and idempotent recovery endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import SessionMessage, TaskRun, WorkContainer
from app.budget.manager import BudgetRejected
from app.worker import broker
from app.judge.service import evaluate_judge_round, judge_state

router = APIRouter(tags=["judge"])


class JudgeResumeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    evidence: dict[str, Any] = Field(default_factory=dict)


class DeterministicGateResult(BaseModel):
    id: str
    gate_name: str
    passed: bool
    evidence: dict[str, Any]
    failure_reason: str | None = None


class JudgeFinding(BaseModel):
    id: str
    responsible_session_id: str | None = None
    severity: str
    summary: str
    evidence_refs: list[Any] = Field(default_factory=list)
    feedback: str | None = None


class JudgeVerdict(BaseModel):
    verdict: Literal["approve", "rework", "blocked"]
    summary: str = ""
    findings: list[JudgeFinding] = Field(default_factory=list)
    next_step: str = ""


class JudgePolicy(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    gates: list[dict[str, Any]]
    evaluation_model_config: dict[str, Any] = Field(alias="model_config")
    safety_limits: dict[str, Any]


class JudgeRound(BaseModel):
    id: str
    sequence: int
    status: str
    phase: str
    verdict: Literal["approve", "rework", "blocked"] | None = None
    summary: str | None = None
    evidence_refs: list[Any] = Field(default_factory=list)
    model_verdict: dict[str, Any] | None = None
    feedback_message_ids: list[str] = Field(default_factory=list)
    pending_session_ids: list[str] = Field(default_factory=list)
    gates: list[DeterministicGateResult] = Field(default_factory=list)
    findings: list[JudgeFinding] = Field(default_factory=list)
    created_at: str
    updated_at: str


class JudgeState(BaseModel):
    enabled: bool
    reason: str | None = None
    session: dict[str, Any] | None = None
    policy: JudgePolicy | None = None
    state: str | None = None
    current_round: JudgeRound | None = None
    rounds: list[JudgeRound] = Field(default_factory=list)
    pending_reply_session_ids: list[str] = Field(default_factory=list)


def _container(session: Session, container_id: uuid.UUID) -> WorkContainer:
    item = session.get(WorkContainer, container_id)
    if item is None:
        raise HTTPException(status_code=404, detail="work container not found")
    return item


@router.get("/work-containers/{container_id}/judge", response_model=JudgeState)
def get_judge(container_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    item = _container(session, container_id)
    result = judge_state(session, item)
    session.commit()
    return result


@router.post("/work-containers/{container_id}/judge/resume")
def resume_judge(
    container_id: uuid.UUID,
    body: JudgeResumeRequest,
    session: Session = Depends(get_db),
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=100)
    ] = None,
) -> dict:
    item = _container(session, container_id)
    try:
        round_ = evaluate_judge_round(session, item, body.evidence, request_key=idempotency_key)
    except BudgetRejected as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=exc.reason) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    for message_id in round_.feedback_message_ids or []:
        message = session.get(SessionMessage, uuid.UUID(str(message_id)))
        run_id = (message.message_metadata or {}).get("activation_run_id") if message else None
        run = session.get(TaskRun, uuid.UUID(str(run_id))) if run_id else None
        if run is not None and run.status == "PENDING":
            broker.enqueue_run(str(run.id))
    return judge_state(session, item)
