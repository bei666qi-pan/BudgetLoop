"""运行聚合与生命周期控制：GET /api/runs/{id}、POST pause/cancel。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.common import budget_snapshot_dict, run_to_dict, task_to_dict
from app.core.db import get_db
from app.core.enums import EventType, RunStatus
from app.core.models import TaskRun, utcnow
from app.events.outbox import emit_event

router = APIRouter(tags=["runs"])


def _get_run_or_404(session: Session, run_id: uuid.UUID) -> TaskRun:
    run = session.get(TaskRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    run = _get_run_or_404(session, run_id)
    return {
        "run": run_to_dict(run),
        "task": task_to_dict(run.task),
        "budget": budget_snapshot_dict(session, run.id),
    }


def _transition(session: Session, run: TaskRun, target: RunStatus) -> dict:
    """幂等状态控制：终态不再变更；已是目标态直接返回。"""
    current = RunStatus(run.status)
    if current.is_terminal:
        return {"run_id": str(run.id), "status": run.status, "changed": False}
    if current == target:
        return {"run_id": str(run.id), "status": run.status, "changed": False}

    run.status = target.value
    if target.is_terminal:
        run.finished_at = utcnow()
    emit_event(
        session,
        run.id,
        EventType.STATE_CHANGED,
        {"from": current.value, "to": target.value},
    )
    session.commit()
    return {"run_id": str(run.id), "status": run.status, "changed": True}


@router.post("/runs/{run_id}/pause")
def pause_run(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    run = _get_run_or_404(session, run_id)
    return _transition(session, run, RunStatus.PAUSED)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    run = _get_run_or_404(session, run_id)
    return _transition(session, run, RunStatus.CANCELLED)
