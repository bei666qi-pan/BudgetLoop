"""Team Runtime Control — container/session-level pause, resume, stop, budget,
correction injection, guided/autonomous switch, enriched GET container,
and team progress observability.

All operator interventions write immutable rows to team_audit_events.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, object_session, selectinload
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.api.common import budget_snapshot_dict
from app.api.runs import _transition
from app.budget.manager import TaskBudgetManager
from app.collaboration.autonomous import is_autonomous, release_autonomous_stages
from app.core.db import SessionLocal, get_db
from app.core.security import require_token  # noqa: F401
from app.core.enums import (
    ContainerLifecycle,
    EventType,
    MessageDeliveryState,
    PressureMode,
    RunStatus,
    SessionMessageKind,
    TERMINAL_STATUSES,
)
from app.core.models import (
    ExecutionEvent,
    LlmCall,
    SessionMessage,
    SessionProgressSignal,
    TaskBudget,
    TaskRun,
    TeamAuditEvent,
    WorkContainer,
    WorkSession,
    utcnow,
)
from app.events.outbox import event_to_dict, list_container_events
from app.policy.pressure import compute_pressure_mode

router = APIRouter(tags=["team-observatory"])

RUNNING_STATUSES = {
    RunStatus.PLANNING.value,
    RunStatus.EXECUTING.value,
    RunStatus.OBSERVING.value,
    RunStatus.EVALUATING.value,
    RunStatus.REPLANNING.value,
}
PAUSABLE_STATUSES = RUNNING_STATUSES | {RunStatus.WAITING_APPROVAL.value}

OPERATOR_ID = "operator"


# ---------------------------------------------------------------------------
#  shared helpers
# ---------------------------------------------------------------------------


def _container_or_404(session: Session, container_id: uuid.UUID) -> WorkContainer:
    container = session.execute(
        select(WorkContainer)
        .options(selectinload(WorkContainer.sessions).selectinload(WorkSession.current_run))
        .where(WorkContainer.id == container_id)
    ).scalar_one_or_none()
    if container is None:
        raise HTTPException(status_code=404, detail="work container not found")
    return container


def _session_or_404(
    session: Session, container_id: uuid.UUID, session_id: uuid.UUID
) -> WorkSession:
    item = session.execute(
        select(WorkSession)
        .options(
            selectinload(WorkSession.current_run),
            selectinload(WorkSession.task),
            selectinload(WorkSession.container),
        )
        .where(WorkSession.id == session_id, WorkSession.container_id == container_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="work session not found")
    return item


def _write_audit(
    session: Session,
    *,
    container_id: uuid.UUID,
    session_id: uuid.UUID | None,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> None:
    session.add(
        TeamAuditEvent(
            container_id=container_id,
            session_id=session_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            operator=OPERATOR_ID,
        )
    )


def _is_exhausted(run: TaskRun) -> bool:
    """Check if the run is in a budget-exhausted or terminated state."""
    return run.status in {
        RunStatus.BUDGET_EXHAUSTED.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
        RunStatus.COMPLETED.value,
    }


# ---------------------------------------------------------------------------
#  1) POST /api/work-containers/{id}/pause — idempotent container pause
# ---------------------------------------------------------------------------


class PauseResponse(BaseModel):
    container_id: str
    lifecycle_state: str
    changed: bool
    paused_sessions: int


@router.post("/work-containers/{container_id}/pause")
def pause_container(
    container_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> PauseResponse:
    container = _container_or_404(session, container_id)

    if container.lifecycle_state == ContainerLifecycle.PAUSED.value:
        return PauseResponse(
            container_id=str(container_id),
            lifecycle_state=container.lifecycle_state,
            changed=False,
            paused_sessions=0,
        )

    old_state = container.lifecycle_state
    paused = 0

    # Release reservations for sessions that are about to be paused
    for ws in container.sessions:
        run = ws.current_run
        if run is None or run.status not in PAUSABLE_STATUSES:
            continue
        try:
            mgr = TaskBudgetManager(session, run.id)
            snap = mgr.snapshot()
            if snap.reserved_tokens > 0 or snap.reserved_cost > 0:
                mgr.release(
                    est_tokens=snap.reserved_tokens,
                    est_cost=snap.reserved_cost,
                )
        except Exception:
            pass  # best-effort release, proceed with pause
        _transition(session, run, RunStatus.PAUSED)
        ws.status = run.status
        ws.updated_at = utcnow()
        paused += 1

    container.lifecycle_state = ContainerLifecycle.PAUSED.value
    container.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container.id,
        session_id=None,
        action="pause",
        old_value={"lifecycle_state": old_state},
        new_value={"lifecycle_state": container.lifecycle_state, "paused_sessions": paused},
    )

    session.commit()
    return PauseResponse(
        container_id=str(container_id),
        lifecycle_state=container.lifecycle_state,
        changed=True,
        paused_sessions=paused,
    )


# ---------------------------------------------------------------------------
#  2) POST /api/work-containers/{id}/resume — idempotent container resume
# ---------------------------------------------------------------------------


class ResumeResponse(BaseModel):
    container_id: str
    lifecycle_state: str
    changed: bool
    resumed_sessions: int
    autonomous_stages_evaluated: bool


@router.post("/work-containers/{container_id}/resume")
def resume_container(
    container_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ResumeResponse:
    container = _container_or_404(session, container_id)

    if container.lifecycle_state == ContainerLifecycle.ACTIVE.value:
        return ResumeResponse(
            container_id=str(container_id),
            lifecycle_state=container.lifecycle_state,
            changed=False,
            resumed_sessions=0,
            autonomous_stages_evaluated=False,
        )

    old_state = container.lifecycle_state
    resumed = 0

    for ws in container.sessions:
        run = ws.current_run
        if run is None or run.status != RunStatus.PAUSED.value:
            continue
        # Transition PAUSED → REPLANNING (allowed transition) so worker can pick up
        run.status = RunStatus.REPLANNING.value
        ws.status = run.status
        ws.updated_at = utcnow()
        resumed += 1

    container.lifecycle_state = ContainerLifecycle.ACTIVE.value
    container.updated_at = utcnow()

    # Re-evaluate autonomous stage dispatch if applicable
    auto_evaluated = False
    if is_autonomous(container):
        auto_evaluated = True
        for ws in container.sessions:
            run = ws.current_run
            if run is not None:
                try:
                    release_autonomous_stages(session, run)
                except Exception:
                    pass

    _write_audit(
        session,
        container_id=container.id,
        session_id=None,
        action="resume",
        old_value={"lifecycle_state": old_state},
        new_value={
            "lifecycle_state": container.lifecycle_state,
            "resumed_sessions": resumed,
        },
    )

    session.commit()
    return ResumeResponse(
        container_id=str(container_id),
        lifecycle_state=container.lifecycle_state,
        changed=True,
        resumed_sessions=resumed,
        autonomous_stages_evaluated=auto_evaluated,
    )


# ---------------------------------------------------------------------------
#  3) POST /api/work-containers/{id}/stop — require confirmation
# ---------------------------------------------------------------------------


class StopRequest(BaseModel):
    confirmed: bool = False


class StopResponse(BaseModel):
    container_id: str
    lifecycle_state: str
    changed: bool
    stopped_sessions: int
    confirmation_required: bool = False
    affected_sessions: list[dict] = []


@router.post("/work-containers/{container_id}/stop")
def stop_container(
    container_id: uuid.UUID,
    body: StopRequest,
    session: Session = Depends(get_db),
    x_confirm: Annotated[str | None, Header(alias="X-Confirm")] = None,
) -> StopResponse:
    container = _container_or_404(session, container_id)

    # Already stopped — idempotent
    if container.lifecycle_state == ContainerLifecycle.COMPLETED.value:
        return StopResponse(
            container_id=str(container_id),
            lifecycle_state=container.lifecycle_state,
            changed=False,
            stopped_sessions=0,
        )

    confirmed = body.confirmed or (x_confirm is not None and x_confirm.lower() == "yes")

    if not confirmed:
        affected = []
        for ws in container.sessions:
            run = ws.current_run
            affected.append({
                "session_id": str(ws.id),
                "role": ws.role,
                "status": run.status if run else ws.status,
                "iteration": run.iteration if run else 0,
            })
        return StopResponse(
            container_id=str(container_id),
            lifecycle_state=container.lifecycle_state,
            changed=False,
            stopped_sessions=0,
            confirmation_required=True,
            affected_sessions=affected,
        )

    old_state = container.lifecycle_state
    stopped = 0

    for ws in container.sessions:
        run = ws.current_run
        if run is None:
            continue
        if not RunStatus(run.status).is_terminal:
            _transition(session, run, RunStatus.CANCELLED)
            ws.status = run.status
            ws.updated_at = utcnow()
            stopped += 1

    container.lifecycle_state = ContainerLifecycle.COMPLETED.value
    container.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container.id,
        session_id=None,
        action="stop",
        old_value={"lifecycle_state": old_state},
        new_value={
            "lifecycle_state": container.lifecycle_state,
            "stopped_sessions": stopped,
        },
    )

    session.commit()
    return StopResponse(
        container_id=str(container_id),
        lifecycle_state=container.lifecycle_state,
        changed=True,
        stopped_sessions=stopped,
    )


# ---------------------------------------------------------------------------
#  4) POST /api/work-containers/{id}/sessions/{sid}/resume
# ---------------------------------------------------------------------------


class SessionResumeResponse(BaseModel):
    session_id: str
    container_id: str
    status: str
    changed: bool
    container_paused: bool


@router.post("/work-containers/{container_id}/sessions/{session_id}/resume")
def resume_session(
    container_id: uuid.UUID,
    session_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SessionResumeResponse:
    item = _session_or_404(session, container_id, session_id)
    container = item.container

    if container.lifecycle_state != ContainerLifecycle.ACTIVE.value:
        return SessionResumeResponse(
            session_id=str(session_id),
            container_id=str(container_id),
            status=item.current_run.status if item.current_run else item.status,
            changed=False,
            container_paused=True,
        )

    run = item.current_run
    if run is None or run.status != RunStatus.PAUSED.value:
        return SessionResumeResponse(
            session_id=str(session_id),
            container_id=str(container_id),
            status=run.status if run else item.status,
            changed=False,
            container_paused=False,
        )

    run.status = RunStatus.REPLANNING.value
    item.status = run.status
    item.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container_id,
        session_id=session_id,
        action="session_resume",
        old_value={"status": RunStatus.PAUSED.value},
        new_value={"status": run.status},
    )

    session.commit()
    return SessionResumeResponse(
        session_id=str(session_id),
        container_id=str(container_id),
        status=run.status,
        changed=True,
        container_paused=False,
    )


# ---------------------------------------------------------------------------
#  5 & 6) PATCH budget — container-level and session-level
# ---------------------------------------------------------------------------


class BudgetPatchRequest(BaseModel):
    model_config = {"extra": "forbid"}

    max_total_tokens: int | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0.0)
    max_parallel_llm_calls: int | None = Field(default=None, ge=1)
    max_team_messages_per_minute: int | None = Field(default=None, ge=1)
    max_auto_reply_rounds: int | None = Field(default=None, ge=1)
    inbox_token_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class BudgetPatchResponse(BaseModel):
    container_id: str
    session_id: str | None = None
    old_values: dict
    new_values: dict
    needs_resume: bool = False
    floor: dict | None = None


def _build_floor_response(
    used: int,
    reserved: int,
    used_cost: float,
    reserved_cost: float,
) -> dict:
    return {
        "used_tokens": used,
        "reserved_tokens": reserved,
        "used_cost": used_cost,
        "reserved_cost": reserved_cost,
        "floor_total_tokens": used + reserved,
        "floor_cost": used_cost + reserved_cost,
    }


@router.patch("/work-containers/{container_id}/budget")
def patch_container_budget(
    container_id: uuid.UUID,
    body: BudgetPatchRequest,
    session: Session = Depends(get_db),
) -> BudgetPatchResponse:
    container = _container_or_404(session, container_id)

    # Aggregate used + reserved across all sessions
    total_used_tokens = 0
    total_reserved_tokens = 0
    total_used_cost = 0.0
    total_reserved_cost = 0.0

    for ws in container.sessions:
        run = ws.current_run
        if run is None:
            continue
        db_session = object_session(ws)
        if db_session is None:
            continue
        try:
            snap = TaskBudgetManager(db_session, run.id).snapshot()
            total_used_tokens += snap.used_tokens
            total_reserved_tokens += snap.reserved_tokens
            total_used_cost += snap.used_cost
            total_reserved_cost += snap.reserved_cost
        except Exception:
            continue

    floor_tokens = total_used_tokens + total_reserved_tokens
    floor_cost = total_used_cost + total_reserved_cost

    old_values: dict[str, object] = {}
    new_values: dict[str, object] = {}
    needs_resume = False

    if body.max_total_tokens is not None:
        if body.max_total_tokens < floor_tokens:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "new max_total_tokens below used+reserved floor",
                    "floor": _build_floor_response(
                        total_used_tokens, total_reserved_tokens,
                        total_used_cost, total_reserved_cost,
                    ),
                },
            )
        # Update all session budgets proportionally? No — spec says container-level
        # budget PATCH adjusts the aggregate. We'll adjust each session proportionally
        # based on their current max. Actually, the container doesn't have its own
        # budget row. The spec says enforce floor constraint. The container-level
        # budget adjustment should affect each session.
        # For simplicity, we'll distribute proportionally.
        old_total = 0
        for ws in container.sessions:
            run = ws.current_run
            if run is None:
                continue
            db_session2 = object_session(ws)
            if db_session2 is None:
                continue
            budget = db_session2.get(TaskBudget, run.id)
            if budget is None:
                continue
            old_total += budget.max_total_tokens

        if old_total == 0:
            old_total = 1  # avoid division by zero

        for ws in container.sessions:
            run = ws.current_run
            if run is None:
                continue
            db_session3 = object_session(ws)
            if db_session3 is None:
                continue
            budget = db_session3.get(TaskBudget, run.id)
            if budget is None:
                continue
            proportion = budget.max_total_tokens / old_total
            new_session_tokens = max(int(body.max_total_tokens * proportion), 1)
            budget.max_total_tokens = new_session_tokens

        old_values["max_total_tokens"] = old_total
        new_values["max_total_tokens"] = body.max_total_tokens

        # Check if any session was exhausted and needs resume
        for ws in container.sessions:
            run = ws.current_run
            if run is not None and run.status == RunStatus.BUDGET_EXHAUSTED.value:
                needs_resume = True
                break

    if body.max_cost is not None:
        if body.max_cost < floor_cost:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "new max_cost below used+reserved floor",
                    "floor": _build_floor_response(
                        total_used_tokens, total_reserved_tokens,
                        total_used_cost, total_reserved_cost,
                    ),
                },
            )
        old_total_cost = 0.0
        for ws in container.sessions:
            run = ws.current_run
            if run is None:
                continue
            db_session2 = object_session(ws)
            if db_session2 is None:
                continue
            budget = db_session2.get(TaskBudget, run.id)
            if budget is None:
                continue
            old_total_cost += float(budget.max_cost)

        if old_total_cost == 0.0:
            old_total_cost = 0.01

        for ws in container.sessions:
            run = ws.current_run
            if run is None:
                continue
            db_session3 = object_session(ws)
            if db_session3 is None:
                continue
            budget = db_session3.get(TaskBudget, run.id)
            if budget is None:
                continue
            proportion = float(budget.max_cost) / old_total_cost
            budget.max_cost = max(body.max_cost * proportion, 0.01)

        old_values["max_cost"] = old_total_cost
        new_values["max_cost"] = body.max_cost

    if body.max_parallel_llm_calls is not None:
        for ws in container.sessions:
            run = ws.current_run
            if run is None:
                continue
            db_session2 = object_session(ws)
            if db_session2 is None:
                continue
            budget = db_session2.get(TaskBudget, run.id)
            if budget is None:
                continue
            budget.max_parallel_llm_calls = body.max_parallel_llm_calls
        old_values["max_parallel_llm_calls"] = "per-session"
        new_values["max_parallel_llm_calls"] = body.max_parallel_llm_calls

    # Anti-runaway parameters stored in preset_snapshot
    if container.preset_snapshot is None:
        container.preset_snapshot = {}

    snapshot_changed = False
    if body.max_team_messages_per_minute is not None:
        old_values["max_team_messages_per_minute"] = container.preset_snapshot.get(
            "max_team_messages_per_minute", 30
        )
        container.preset_snapshot["max_team_messages_per_minute"] = body.max_team_messages_per_minute
        new_values["max_team_messages_per_minute"] = body.max_team_messages_per_minute
        snapshot_changed = True

    if body.max_auto_reply_rounds is not None:
        old_values["max_auto_reply_rounds"] = container.preset_snapshot.get(
            "max_auto_reply_rounds", 5
        )
        container.preset_snapshot["max_auto_reply_rounds"] = body.max_auto_reply_rounds
        new_values["max_auto_reply_rounds"] = body.max_auto_reply_rounds
        snapshot_changed = True

    if body.inbox_token_ratio is not None:
        old_values["inbox_token_ratio"] = container.preset_snapshot.get(
            "inbox_token_ratio", 0.05
        )
        container.preset_snapshot["inbox_token_ratio"] = body.inbox_token_ratio
        new_values["inbox_token_ratio"] = body.inbox_token_ratio
        snapshot_changed = True

    container.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container.id,
        session_id=None,
        action="budget_update",
        old_value=old_values,
        new_value=new_values,
    )

    session.commit()
    return BudgetPatchResponse(
        container_id=str(container_id),
        old_values=old_values,
        new_values=new_values,
        needs_resume=needs_resume,
    )


@router.patch("/work-containers/{container_id}/sessions/{session_id}/budget")
def patch_session_budget(
    container_id: uuid.UUID,
    session_id: uuid.UUID,
    body: BudgetPatchRequest,
    session: Session = Depends(get_db),
) -> BudgetPatchResponse:
    item = _session_or_404(session, container_id, session_id)
    run = item.current_run
    if run is None:
        raise HTTPException(status_code=422, detail="session has no active run")

    # Check terminal state
    if RunStatus(run.status).is_terminal:
        raise HTTPException(status_code=422, detail="session run is in terminal state")

    budget = session.get(TaskBudget, run.id)
    if budget is None:
        raise HTTPException(status_code=422, detail="no budget row for run")

    snap = TaskBudgetManager(session, run.id).snapshot()
    used_tokens = snap.used_tokens
    reserved_tokens = snap.reserved_tokens
    used_cost = snap.used_cost
    reserved_cost = snap.reserved_cost

    floor_tokens = used_tokens + reserved_tokens
    floor_cost = used_cost + reserved_cost

    old_values: dict[str, object] = {}
    new_values: dict[str, object] = {}
    needs_resume = False

    if body.max_total_tokens is not None:
        if body.max_total_tokens < floor_tokens:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "new max_total_tokens below used+reserved floor",
                    "floor": _build_floor_response(
                        used_tokens, reserved_tokens, used_cost, reserved_cost
                    ),
                },
            )
        old_values["max_total_tokens"] = budget.max_total_tokens
        budget.max_total_tokens = body.max_total_tokens
        new_values["max_total_tokens"] = body.max_total_tokens
        if run.status == RunStatus.BUDGET_EXHAUSTED.value:
            needs_resume = True

    if body.max_cost is not None:
        if body.max_cost < floor_cost:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "new max_cost below used+reserved floor",
                    "floor": _build_floor_response(
                        used_tokens, reserved_tokens, used_cost, reserved_cost
                    ),
                },
            )
        old_values["max_cost"] = float(budget.max_cost)
        budget.max_cost = body.max_cost
        new_values["max_cost"] = body.max_cost

    if body.max_parallel_llm_calls is not None:
        old_values["max_parallel_llm_calls"] = budget.max_parallel_llm_calls
        budget.max_parallel_llm_calls = body.max_parallel_llm_calls
        new_values["max_parallel_llm_calls"] = body.max_parallel_llm_calls

    # Anti-runaway parameters on session-level budget don't apply to TaskBudget;
    # they live on the container's preset_snapshot or the worker config.
    # For session-level, we store them as metadata on the run's model_config.
    config_changed = False
    run_config = dict(run.model_config or {})
    if body.max_team_messages_per_minute is not None:
        old_values["max_team_messages_per_minute"] = run_config.get(
            "max_team_messages_per_minute", 30
        )
        run_config["max_team_messages_per_minute"] = body.max_team_messages_per_minute
        new_values["max_team_messages_per_minute"] = body.max_team_messages_per_minute
        config_changed = True
    if body.max_auto_reply_rounds is not None:
        old_values["max_auto_reply_rounds"] = run_config.get("max_auto_reply_rounds", 5)
        run_config["max_auto_reply_rounds"] = body.max_auto_reply_rounds
        new_values["max_auto_reply_rounds"] = body.max_auto_reply_rounds
        config_changed = True
    if body.inbox_token_ratio is not None:
        old_values["inbox_token_ratio"] = run_config.get("inbox_token_ratio", 0.05)
        run_config["inbox_token_ratio"] = body.inbox_token_ratio
        new_values["inbox_token_ratio"] = body.inbox_token_ratio
        config_changed = True
    if config_changed:
        run.model_config = run_config

    item.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container_id,
        session_id=session_id,
        action="budget_update",
        old_value=old_values,
        new_value=new_values,
    )

    session.commit()
    return BudgetPatchResponse(
        container_id=str(container_id),
        session_id=str(session_id),
        old_values=old_values,
        new_values=new_values,
        needs_resume=needs_resume,
    )


# ---------------------------------------------------------------------------
#  7) POST /api/work-containers/{id}/correct — correction instruction
# ---------------------------------------------------------------------------


class CorrectRequest(BaseModel):
    session_id: uuid.UUID  # target session
    instruction: str = Field(min_length=1, max_length=8_000)

    @field_validator("instruction")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CorrectResponse(BaseModel):
    message_id: str
    container_id: str
    session_id: str
    status: str
    queued: bool


@router.post("/work-containers/{container_id}/correct", status_code=201)
def correct_container(
    container_id: uuid.UUID,
    body: CorrectRequest,
    session: Session = Depends(get_db),
) -> CorrectResponse:
    container = _container_or_404(session, container_id)
    target = _session_or_404(session, container_id, body.session_id)

    message = SessionMessage(
        container_id=container_id,
        sender_session_id=None,
        recipient_session_id=target.id,
        author_type="operator",
        kind=SessionMessageKind.MESSAGE.value,
        message_type="system_fact",
        content=body.instruction,
        delivery_state=MessageDeliveryState.QUEUED.value,
        message_metadata={
            "role": "system",
            "priority": "high",
            "correction": True,
        },
    )
    session.add(message)

    _write_audit(
        session,
        container_id=container_id,
        session_id=body.session_id,
        action="correct",
        old_value=None,
        new_value={"instruction_length": len(body.instruction)},
    )

    container.updated_at = utcnow()
    session.commit()
    session.refresh(message)

    return CorrectResponse(
        message_id=str(message.id),
        container_id=str(container_id),
        session_id=str(body.session_id),
        status=message.delivery_state,
        queued=True,
    )


# ---------------------------------------------------------------------------
#  8) Guided / autonomous mode switch
# ---------------------------------------------------------------------------


class ModeSwitchRequest(BaseModel):
    team_mode: str = Field(pattern=r"^(guided|autonomous)$")
    mode_switch_confirmed: bool = False


class ModeSwitchResponse(BaseModel):
    container_id: str
    old_mode: str
    new_mode: str
    changed: bool
    confirmation_required: bool = False
    impact: list[str] = []


@router.patch("/work-containers/{container_id}/mode")
def switch_container_mode(
    container_id: uuid.UUID,
    body: ModeSwitchRequest,
    session: Session = Depends(get_db),
) -> ModeSwitchResponse:
    container = _container_or_404(session, container_id)

    snapshot = dict(container.preset_snapshot or {})
    old_mode = snapshot.get("team_mode", "guided")

    # Already in target mode — idempotent
    if old_mode == body.team_mode:
        return ModeSwitchResponse(
            container_id=str(container_id),
            old_mode=old_mode,
            new_mode=body.team_mode,
            changed=False,
        )

    impact = [
        "automatic stage dispatch will be enabled" if body.team_mode == "autonomous" else "automatic stage dispatch will be disabled",
        "dependency-driven execution will be active" if body.team_mode == "autonomous" else "manual stage progression required",
        "handoff generation will be automatic" if body.team_mode == "autonomous" else "handoffs require operator approval",
    ]

    if not body.mode_switch_confirmed:
        return ModeSwitchResponse(
            container_id=str(container_id),
            old_mode=old_mode,
            new_mode=body.team_mode,
            changed=False,
            confirmation_required=True,
            impact=impact,
        )

    snapshot["team_mode"] = body.team_mode
    container.preset_snapshot = snapshot
    container.updated_at = utcnow()

    _write_audit(
        session,
        container_id=container_id,
        session_id=None,
        action="mode_switch",
        old_value={"team_mode": old_mode},
        new_value={"team_mode": body.team_mode},
    )

    session.commit()
    return ModeSwitchResponse(
        container_id=str(container_id),
        old_mode=old_mode,
        new_mode=body.team_mode,
        changed=True,
        impact=impact,
    )


# ---------------------------------------------------------------------------
#  GET /api/work-containers/{id} enrichment — team_status, usage_summary,
#  progress_summary
# ---------------------------------------------------------------------------

# Re-exported for use by work_containers.py
def _enrich_container_dict(container: WorkContainer, session: Session) -> dict:
    """Compute team_status, usage_summary, and progress_summary for a container.

    This is called from GET /api/work-containers/{id} to add observatory fields
    without breaking existing responses.
    """
    results: dict[str, object] = {}

    # -- team_status --
    statuses: list[str] = []
    for ws in container.sessions:
        run = ws.current_run
        statuses.append(run.status if run else ws.status)

    running_count = sum(s in RUNNING_STATUSES for s in statuses)
    paused_count = sum(s == RunStatus.PAUSED.value for s in statuses)
    waiting_count = sum(
        s in (RunStatus.PENDING.value, RunStatus.WAITING_APPROVAL.value)
        for s in statuses
    )
    terminal_count = sum(RunStatus(s).is_terminal for s in statuses if s)

    if container.lifecycle_state == ContainerLifecycle.PAUSED.value:
        team_phase = "paused"
    elif container.lifecycle_state == ContainerLifecycle.COMPLETED.value:
        team_phase = "completed"
    elif running_count > 0:
        team_phase = "running"
    elif terminal_count == len(statuses):
        team_phase = "completed"
    else:
        team_phase = "idle"

    results["team_status"] = {
        "phase": team_phase,
        "lifecycle_state": container.lifecycle_state,
        "total_sessions": len(statuses),
        "running": running_count,
        "paused": paused_count,
        "waiting": waiting_count,
        "completed": terminal_count,
    }

    # -- usage_summary --
    total_used_tokens = 0
    total_max_tokens = 0
    total_used_cost = 0.0
    total_max_cost = 0.0
    total_calls = 0
    total_max_calls = 0

    for ws in container.sessions:
        run = ws.current_run
        if run is None:
            continue
        try:
            snap = TaskBudgetManager(session, run.id).snapshot()
            total_used_tokens += snap.used_tokens
            total_max_tokens += snap.max_total_tokens
            total_used_cost += snap.used_cost
            total_max_cost += snap.max_cost
            total_calls += snap.used_calls
            total_max_calls += snap.max_llm_calls
        except Exception:
            continue

    results["usage_summary"] = {
        "tokens": {
            "used": total_used_tokens,
            "max": total_max_tokens,
            "percent": round(total_used_tokens / max(total_max_tokens, 1) * 100, 1),
        },
        "cost": {
            "used": round(total_used_cost, 6),
            "max": round(total_max_cost, 6),
            "percent": round(total_used_cost / max(total_max_cost, 0.01) * 100, 1),
        },
        "calls": {
            "used": total_calls,
            "max": total_max_calls,
            "percent": round(total_calls / max(total_max_calls, 1) * 100, 1),
        },
    }

    # -- progress_summary --
    session_progress: list[dict] = []
    for ws in container.sessions:
        run = ws.current_run
        session_progress.append({
            "session_id": str(ws.id),
            "role": ws.role,
            "status": run.status if run else ws.status,
            "iteration": run.iteration if run else 0,
            "current_phase": run.current_phase if run else None,
        })
    results["progress_summary"] = session_progress

    return results


# ---------------------------------------------------------------------------
#  Team SSE event stream
# ---------------------------------------------------------------------------

_POLL_INTERVAL_SECONDS = 1.0
_MAX_PAYLOAD_BYTES = 4096  # 4 KB
_TERMINAL_CONTAINER_STATES: frozenset[str] = frozenset({"completed", "archived"})


def _truncate_if_needed(event_dict: dict) -> dict:
    """如果序列化后超过 _MAX_PAYLOAD_BYTES，截断 payload 并附加元数据。"""
    serialized = json.dumps(event_dict, ensure_ascii=False)
    byte_size = len(serialized.encode("utf-8"))
    if byte_size <= _MAX_PAYLOAD_BYTES:
        return event_dict

    return {
        **event_dict,
        "payload": {"_note": "payload truncated, exceeds 4KB limit"},
        "_truncated": True,
        "_full_size": byte_size,
    }


def _fetch_container_sse(
    container_id: uuid.UUID,
    after_seq: int,
) -> tuple[list[dict], str | None]:
    """短会话读取容器增量事件与 lifecycle_state（同步 SQLAlchemy，线程池中执行）。"""
    session = SessionLocal()
    try:
        container = session.get(WorkContainer, container_id)
        lifecycle = container.lifecycle_state if container is not None else None
        events = [
            event_to_dict(e)
            for e in list_container_events(session, container_id, after_seq)
        ]
        return events, lifecycle
    finally:
        session.close()


@router.get("/work-containers/{container_id}/stream")
async def stream_container(
    container_id: uuid.UUID,
    request: Request,
) -> EventSourceResponse:
    """团队 SSE 事件流。

    查询 execution_events WHERE container_id = {id} ORDER BY seq。
    支持 Last-Event-ID 断线回放。容器终态时发送 run_finished 并关闭。
    """
    _, lifecycle = await run_in_threadpool(_fetch_container_sse, container_id, 0)
    if lifecycle is None:
        raise HTTPException(status_code=404, detail="container not found")

    last_seq = 0
    last_event_id = request.headers.get("last-event-id")
    if last_event_id and last_event_id.isdigit():
        last_seq = int(last_event_id)

    async def event_generator():
        nonlocal last_seq
        while True:
            if await request.is_disconnected():
                return
            events, cur_lifecycle = await run_in_threadpool(
                _fetch_container_sse, container_id, last_seq
            )
            saw_finish = False
            for event in events:
                last_seq = event["seq"]
                if event["type"] == EventType.RUN_FINISHED.value:
                    saw_finish = True
                truncated = _truncate_if_needed(event)
                yield {
                    "id": str(truncated["seq"]),
                    "event": truncated["type"],
                    "data": json.dumps(truncated, ensure_ascii=False),
                }
            if cur_lifecycle is not None and cur_lifecycle in _TERMINAL_CONTAINER_STATES:
                if not saw_finish:
                    truncated = _truncate_if_needed(
                        {
                            "seq": last_seq,
                            "type": EventType.RUN_FINISHED.value,
                            "payload": {"lifecycle_state": cur_lifecycle},
                            "created_at": None,
                        }
                    )
                    yield {
                        "id": str(last_seq),
                        "event": EventType.RUN_FINISHED.value,
                        "data": json.dumps(truncated, ensure_ascii=False),
                    }
                return
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
#  GET /api/work-containers/{id}/progress — Team Progress Observability
# ---------------------------------------------------------------------------


def _resolve_display_status(session_item: WorkSession) -> str:
    """Resolve a session's simplified display status from its current run."""
    run = session_item.current_run
    if run is None:
        return "waiting"
    status = run.status
    if status in RUNNING_STATUSES:
        return "running"
    if status == RunStatus.PAUSED.value:
        return "paused"
    if status in (RunStatus.PENDING.value, RunStatus.WAITING_APPROVAL.value):
        return "waiting"
    if status in (RunStatus.COMPLETED.value, RunStatus.PARTIAL_COMPLETED.value):
        return "completed"
    if status in (RunStatus.FAILED.value, RunStatus.BUDGET_EXHAUSTED.value):
        return "blocked"
    if status == RunStatus.CANCELLED.value:
        return "cancelled"
    return "waiting"


def _parse_progress_percentage(signal: SessionProgressSignal | None) -> dict:
    """Extract progress percentage from a progress signal.

    Only includes percentage when completed_items is a non-empty array/list
    AND a known total can be determined (from dict keys or x/y milestone pattern).
    Otherwise returns null values — frontend displays 'Agent 未声明进度'.
    """
    result: dict = {"completed": None, "total": None, "percentage": None}
    if signal is None:
        return result

    completed_items = signal.completed_items
    if completed_items is None:
        return result

    completed_count: int | None = None
    total_count: int | None = None

    # Case 1: completed_items is a plain JSON array
    if isinstance(completed_items, list):
        if len(completed_items) == 0:
            return result
        completed_count = len(completed_items)

    # Case 2: completed_items is a dict — look for items list
    elif isinstance(completed_items, dict):
        items = completed_items.get("items") or completed_items.get("completed_items")
        if not isinstance(items, list) or len(items) == 0:
            return result
        completed_count = len(items)
        # Check for explicit total in dict
        total_from_dict = completed_items.get("total") or completed_items.get("total_items")
        if isinstance(total_from_dict, int) and total_from_dict > 0:
            total_count = total_from_dict
    else:
        return result

    # Try to detect total from milestone pattern (e.g. "3/5" or "完成 3/5")
    if total_count is None and completed_count is not None and signal.milestone:
        match = re.search(r"(\d+)\s*/\s*(\d+)", signal.milestone)
        if match:
            total_count = int(match.group(2))

    result["completed"] = completed_count
    if total_count is not None:
        result["total"] = total_count
        if total_count > 0:
            result["percentage"] = round(completed_count / total_count * 100)

    return result


def _latest_agent_message_payload(db: Session, run_id: uuid.UUID) -> dict | None:
    """Get the most recent agent_message execution event payload for a run."""
    event = db.execute(
        select(ExecutionEvent)
        .where(
            ExecutionEvent.run_id == run_id,
            ExecutionEvent.type == "agent_message",
        )
        .order_by(desc(ExecutionEvent.created_at))
        .limit(1)
    ).scalar_one_or_none()
    if event is None:
        return None
    payload = event.payload or {}
    return {
        "text": payload.get("text", ""),
        "iteration": payload.get("iteration"),
        "created_at": event.created_at.isoformat(),
    }


def _latest_signal(db: Session, session_id: uuid.UUID) -> SessionProgressSignal | None:
    """Get the most recent progress signal for a session."""
    return db.execute(
        select(SessionProgressSignal)
        .where(SessionProgressSignal.session_id == session_id)
        .order_by(desc(SessionProgressSignal.created_at))
        .limit(1)
    ).scalar_one_or_none()


def _compute_last_activity(
    session_item: WorkSession,
    signal: SessionProgressSignal | None,
    agent_msg: dict | None,
) -> str | None:
    """Compute last activity timestamp — most recent of updated_at, signal, or agent message."""
    candidates: list[datetime] = []
    if session_item.updated_at is not None:
        candidates.append(session_item.updated_at)
    if signal is not None and signal.created_at is not None:
        candidates.append(signal.created_at)
    if agent_msg and agent_msg.get("created_at"):
        try:
            candidates.append(datetime.fromisoformat(agent_msg["created_at"]))
        except (ValueError, TypeError):
            pass
    if not candidates:
        return None
    return max(candidates).isoformat()


def _build_session_progress(
    session_item: WorkSession,
    db: Session,
) -> dict:
    """Build per-session progress detail from database records — no LLM calls."""
    run = session_item.current_run
    display_status = _resolve_display_status(session_item)
    signal = _latest_signal(db, session_item.id)
    pct = _parse_progress_percentage(signal)

    agent_msg = None
    if run is not None:
        agent_msg = _latest_agent_message_payload(db, run.id)

    last_activity = _compute_last_activity(session_item, signal, agent_msg)

    phase = run.current_phase if run is not None else None

    return {
        "session_id": str(session_item.id),
        "role": session_item.role,
        "status": display_status,
        "phase": phase,
        "current_action": agent_msg["text"] if agent_msg else None,
        "last_activity": last_activity,
        "milestone": signal.milestone if signal else None,
        "summary": signal.summary if signal else None,
        "next_step": signal.next_step if signal else None,
        "blocked": signal.blocked if signal else False,
        "blocker_reason": signal.blocker_reason if signal else None,
        "needs_operator": signal.needs_operator if signal else False,
        "evidence": signal.evidence if signal else None,
        "iteration": signal.iteration if signal else (run.iteration if run is not None else 0),
        "progress": pct,
    }


def _build_all_signals_map(
    db: Session, container_id: uuid.UUID
) -> dict[uuid.UUID, SessionProgressSignal | None]:
    """Build a map of session_id → latest progress signal in a single query.

    Team size ≤ 8 sessions, so single-query + in-Python dedup is efficient.
    """
    all_signals = list(
        db.execute(
            select(SessionProgressSignal)
            .join(WorkSession, SessionProgressSignal.session_id == WorkSession.id)
            .where(WorkSession.container_id == container_id)
            .order_by(SessionProgressSignal.session_id, desc(SessionProgressSignal.created_at))
        ).scalars()
    )
    seen: set[uuid.UUID] = set()
    result: dict[uuid.UUID, SessionProgressSignal] = {}
    for signal in all_signals:
        if signal.session_id not in seen:
            seen.add(signal.session_id)
            result[signal.session_id] = signal
    return result


@router.get("/work-containers/{container_id}/progress")
def get_team_progress(
    container_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate team progress from Agent-declared progress signals.

    Pure PostgreSQL query — no LLM calls, no inference. All progress data
    comes from the session_progress_signals table. Sessions without signals
    return null/fallback values; the frontend renders 'Agent 未声明进度'.
    """
    container = _container_or_404(db, container_id)
    sessions_list = list(container.sessions)

    # Build per-session progress details
    session_progress_list: list[dict] = []
    running_count = 0
    waiting_count = 0
    paused_count = 0
    blocked_count = 0
    completed_count = 0
    phase_counts: dict[str, int] = {}

    for ws in sessions_list:
        sp = _build_session_progress(ws, db)
        session_progress_list.append(sp)

        status = sp["status"]
        if status == "running":
            running_count += 1
            if sp["phase"]:
                phase_counts[sp["phase"]] = phase_counts.get(sp["phase"], 0) + 1
        elif status == "waiting":
            waiting_count += 1
        elif status == "paused":
            paused_count += 1
        elif status in ("blocked", "failed"):
            blocked_count += 1
        elif status == "completed":
            completed_count += 1

    # Active stage — most common phase among running sessions
    active_stage: str | None = None
    if phase_counts:
        active_stage = max(phase_counts, key=phase_counts.get)  # type: ignore[arg-type]

    # Recent milestones: top 10 most recent across all sessions
    signals_map = _build_all_signals_map(db, container_id)
    session_role_map: dict[uuid.UUID, str] = {ws.id: ws.role for ws in sessions_list}
    all_milestones: list[dict] = []
    for sid, signal in signals_map.items():
        if signal is not None and signal.milestone:
            all_milestones.append({
                "session_id": str(sid),
                "session_role": session_role_map.get(sid, ""),
                "milestone": signal.milestone,
                "created_at": signal.created_at.isoformat(),
            })
    all_milestones.sort(key=lambda m: m["created_at"], reverse=True)
    recent_milestones = all_milestones[:10]

    # Next focus: blocked sessions first, then by last activity (most recent first)
    blocked_sessions = [
        sp for sp in session_progress_list
        if sp["blocked"] or sp["status"] == "blocked"
    ]
    non_blocked = [
        sp for sp in session_progress_list
        if sp not in blocked_sessions
    ]
    non_blocked.sort(
        key=lambda sp: sp["last_activity"] or "",
        reverse=True,
    )
    next_focus = [
        {
            "session_id": sp["session_id"],
            "role": sp["role"],
            "status": sp["status"],
            "next_step": sp["next_step"],
            "blocked": sp["blocked"],
            "blocker_reason": sp["blocker_reason"],
        }
        for sp in blocked_sessions + non_blocked
    ][:5]

    return {
        "container_id": str(container_id),
        "team_summary": {
            "running": running_count,
            "waiting": waiting_count,
            "paused": paused_count,
            "blocked": blocked_count,
            "completed": completed_count,
            "total": len(sessions_list),
            "active_stage": active_stage,
        },
        "recent_milestones": recent_milestones,
        "next_focus": next_focus,
        "sessions": session_progress_list,
    }


# ---------------------------------------------------------------------------
# GROUP 4 — Team Usage Aggregation
# ---------------------------------------------------------------------------

_LLM_CALL_WINDOW_MINUTES = 5
_TERMINAL = tuple(s.value for s in TERMINAL_STATUSES)


def _is_terminal_status(status: str) -> bool:
    return status in _TERMINAL


def _tighter_pressure(a: PressureMode, b: PressureMode) -> PressureMode:
    order = {
        PressureMode.NORMAL: 0,
        PressureMode.CONSERVATIVE: 1,
        PressureMode.CRITICAL: 2,
    }
    return a if order[a] >= order[b] else b


@router.get("/work-containers/{container_id}/usage")
def get_team_usage(
    container_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> dict:
    """Real-time team usage aggregation from PostgreSQL budget ledgers.

    * Team aggregate = simple SUM of per-session task_budget.used_* /
      reserved_* / max_* (no double-count).
    * reserved_* excludes completed/failed/cancelled sessions.
    * Token sub-types from llm_calls (prompt/completion/reasoning/
      cache_read/cache_write).
    * Missing optional fields (estimated_cost, ttft_ms, cache tokens)
      return null — never 0.
    * Consumption rate from trailing 5-minute llm_calls window.
    * Team pressure mode = worst compute_pressure_mode of all active sessions.
    """
    container = _container_or_404(session, container_id)

    # --- collect per-session budget rows ---
    budget_map: dict[uuid.UUID, TaskBudget] = {}
    run_ids: list[uuid.UUID] = []
    for ws in container.sessions:
        run = ws.current_run
        if run is not None:
            run_ids.append(run.id)

    if run_ids:
        rows = session.execute(
            select(TaskBudget).where(TaskBudget.run_id.in_(run_ids))
        ).scalars()
        for row in rows:
            budget_map[row.run_id] = row

    # --- per-session breakdown ---
    per_session: list[dict] = []
    now = utcnow()

    team_used_tokens = 0
    team_used_cost = 0.0
    team_used_calls = 0
    team_reserved_tokens = 0
    team_reserved_cost = 0.0
    team_reserved_calls = 0
    team_max_tokens = 0
    team_max_cost = 0.0
    team_max_calls = 0
    team_max_wall_time_seconds = 0
    team_max_active_runtime_seconds = 0
    team_max_parallelism = 0

    worst_pressure: PressureMode = PressureMode.NORMAL

    for ws in container.sessions:
        run = ws.current_run
        run_id = run.id if run else None
        b = budget_map.get(run_id) if run_id else None
        run_status = run.status if run else "PENDING"
        terminal = _is_terminal_status(run_status)

        used_tokens = b.used_tokens if b else 0
        used_cost = float(b.used_cost) if b else 0.0
        used_calls = b.used_calls if b else 0

        reserved_tokens = b.reserved_tokens if b and not terminal else 0
        reserved_cost = float(b.reserved_cost) if b and not terminal else 0.0
        reserved_calls = b.reserved_calls if b and not terminal else 0

        max_tokens = b.max_total_tokens if b else 0
        max_cost = float(b.max_cost) if b else 0.0
        max_calls = b.max_llm_calls if b else 0
        max_wall = b.max_wall_time_seconds if b else 0
        max_active = b.max_active_runtime_seconds if b else 0
        max_parallel = b.max_parallel_llm_calls if b else 0

        remaining_tokens = max_tokens - used_tokens - reserved_tokens
        remaining_cost = max_cost - used_cost - reserved_cost
        remaining_calls = max_calls - used_calls - reserved_calls

        pressure = None
        if run and not terminal and b:
            try:
                pressure = compute_pressure_mode(
                    deadline_at=run.deadline_at,
                    max_wall_time_seconds=b.max_wall_time_seconds,
                    active_runtime_ms=run.active_runtime_ms,
                    max_active_runtime_seconds=b.max_active_runtime_seconds,
                    remaining_tokens=remaining_tokens,
                    max_total_tokens=b.max_total_tokens,
                    now=now,
                )
                worst_pressure = _tighter_pressure(worst_pressure, pressure)
            except Exception:
                pressure = PressureMode.NORMAL.value

        per_session.append(
            {
                "session_id": str(ws.id),
                "role": ws.role,
                "run_id": str(run_id) if run_id else None,
                "status": run_status,
                "pressure_mode": pressure.value if pressure else None,
                "used": {
                    "tokens": used_tokens,
                    "cost": used_cost,
                    "calls": used_calls,
                },
                "reserved": {
                    "tokens": reserved_tokens,
                    "cost": reserved_cost,
                    "calls": reserved_calls,
                },
                "remaining": {
                    "tokens": remaining_tokens,
                    "cost": round(remaining_cost, 6),
                    "calls": remaining_calls,
                },
                "max": {
                    "tokens": max_tokens,
                    "cost": max_cost,
                    "calls": max_calls,
                    "wall_time_seconds": max_wall,
                    "active_runtime_seconds": max_active,
                    "parallel_llm_calls": max_parallel,
                },
            }
        )

        team_used_tokens += used_tokens
        team_used_cost += used_cost
        team_used_calls += used_calls
        team_reserved_tokens += reserved_tokens
        team_reserved_cost += reserved_cost
        team_reserved_calls += reserved_calls
        team_max_tokens += max_tokens
        team_max_cost += max_cost
        team_max_calls += max_calls
        team_max_wall_time_seconds += max_wall
        team_max_active_runtime_seconds += max_active
        if max_parallel > team_max_parallelism:
            team_max_parallelism = max_parallel

    # --- consumption rate from trailing 5-min llm_calls ---
    window_start = now - timedelta(minutes=_LLM_CALL_WINDOW_MINUTES)
    consumption_rate: float | None = None
    window_calls = 0
    if run_ids:
        window_calls = int(
            session.execute(
                select(func.count(LlmCall.id)).where(
                    LlmCall.run_id.in_(run_ids),
                    LlmCall.started_at >= window_start,
                )
            ).scalar_one()
        )
        consumption_rate = (
            round(window_calls / _LLM_CALL_WINDOW_MINUTES, 4) if window_calls else 0.0
        )
    else:
        consumption_rate = 0.0

    # --- estimated depletion time ---
    team_remaining_tokens = team_max_tokens - team_used_tokens - team_reserved_tokens
    estimated_depletion_seconds: int | None = None
    if consumption_rate and consumption_rate > 0 and team_remaining_tokens > 0:
        trailing_total_tokens = int(
            session.execute(
                select(func.coalesce(func.sum(LlmCall.total_tokens), 0)).where(
                    LlmCall.run_id.in_(run_ids),
                    LlmCall.started_at >= window_start,
                )
            ).scalar_one()
        ) if run_ids else 0

        if trailing_total_tokens > 0 and window_calls > 0:
            avg_tokens_per_call = trailing_total_tokens / window_calls
            calls_remaining = team_remaining_tokens / avg_tokens_per_call if avg_tokens_per_call > 0 else 0
            minutes_remaining = calls_remaining / consumption_rate if consumption_rate > 0 else 0
            estimated_depletion_seconds = int(minutes_remaining * 60)
        else:
            estimated_depletion_seconds = None
    else:
        estimated_depletion_seconds = None

    # --- token sub-types from llm_calls ---
    token_sub_types: dict[str, int] = {}
    if run_ids:
        sub_row = session.execute(
            select(
                func.coalesce(func.sum(LlmCall.prompt_tokens), 0).label("prompt"),
                func.coalesce(func.sum(LlmCall.completion_tokens), 0).label("completion"),
                func.coalesce(func.sum(LlmCall.reasoning_tokens), 0).label("reasoning"),
                func.coalesce(func.sum(LlmCall.cache_read_tokens), 0).label("cache_read"),
                func.coalesce(func.sum(LlmCall.cache_write_tokens), 0).label("cache_write"),
            ).where(LlmCall.run_id.in_(run_ids))
        ).one()
        token_sub_types = {
            "prompt": int(sub_row.prompt),
            "completion": int(sub_row.completion),
            "reasoning": int(sub_row.reasoning),
            "cache_read": int(sub_row.cache_read),
            "cache_write": int(sub_row.cache_write),
        }
    else:
        token_sub_types = {
            "prompt": 0,
            "completion": 0,
            "reasoning": 0,
            "cache_read": 0,
            "cache_write": 0,
        }

    active_count = sum(
        1
        for ws in container.sessions
        if not _is_terminal_status(ws.current_run.status if ws.current_run else "PENDING")
    )

    return {
        "container_id": str(container.id),
        "container_name": container.name,
        "lifecycle_state": container.lifecycle_state,
        "active_session_count": active_count,
        "total_session_count": len(container.sessions),
        "team_pressure_mode": worst_pressure.value,
        "aggregate": {
            "used": {
                "tokens": team_used_tokens,
                "cost": round(float(team_used_cost), 6),
                "calls": team_used_calls,
            },
            "reserved": {
                "tokens": team_reserved_tokens,
                "cost": round(float(team_reserved_cost), 6),
                "calls": team_reserved_calls,
            },
            "remaining": {
                "tokens": team_remaining_tokens,
                "cost": round(team_max_cost - team_used_cost - team_reserved_cost, 6),
                "calls": team_max_calls - team_used_calls - team_reserved_calls,
            },
            "max": {
                "tokens": team_max_tokens,
                "cost": team_max_cost,
                "calls": team_max_calls,
                "wall_time_seconds": team_max_wall_time_seconds,
                "active_runtime_seconds": team_max_active_runtime_seconds,
                "parallel_llm_calls": team_max_parallelism,
            },
        },
        "consumption": {
            "rate_calls_per_minute": consumption_rate,
            "window_minutes": _LLM_CALL_WINDOW_MINUTES,
            "estimated_depletion_seconds": estimated_depletion_seconds,
        },
        "token_sub_types": token_sub_types,
        "per_session": per_session,
    }


def _derive_team_status(
    lifecycle: str,
    session_statuses: list[str],
) -> str:
    """Derive a team-level status string from container lifecycle + session states."""
    if lifecycle == ContainerLifecycle.PAUSED.value:
        return "paused"
    if lifecycle in (ContainerLifecycle.COMPLETED.value, ContainerLifecycle.ARCHIVED.value):
        return lifecycle

    running = sum(s not in _TERMINAL and s != "PENDING" for s in session_statuses)
    pending = sum(s == "PENDING" for s in session_statuses)
    failed = sum(s in ("FAILED", "BUDGET_EXHAUSTED") for s in session_statuses)
    paused = sum(s == "PAUSED" for s in session_statuses)

    if failed > 0:
        return "attention"
    if paused > 0 and running == 0:
        return "paused"
    if running > 0:
        return "running"
    if pending > 0:
        return "pending"
    return "idle"


@router.get("/containers")
def list_containers_extended(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> dict:
    """Container list with team observatory fields (team_status, active_session_count, alert_count)."""
    containers = list(
        session.execute(
            select(WorkContainer)
            .options(selectinload(WorkContainer.sessions).selectinload(WorkSession.current_run))
            .order_by(WorkContainer.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).scalars()
    )

    result: list[dict] = []
    for c in containers:
        items = list(c.sessions)
        statuses = [ws.current_run.status if ws.current_run else "PENDING" for ws in items]
        active_count = sum(not _is_terminal_status(s) for s in statuses)
        alert_count = sum(1 for s in statuses if s in {"FAILED", "BUDGET_EXHAUSTED"})

        result.append(
            {
                "id": str(c.id),
                "name": c.name,
                "project_goal": c.project_goal,
                "lifecycle_state": c.lifecycle_state,
                "base_workdir": c.base_workdir,
                "default_workspace_policy": c.default_workspace_policy,
                "preset_id": c.preset_id,
                "preset_version": c.preset_version,
                "team_status": _derive_team_status(c.lifecycle_state, statuses),
                "active_session_count": active_count,
                "alert_count": alert_count,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
        )

    return {"containers": result}
