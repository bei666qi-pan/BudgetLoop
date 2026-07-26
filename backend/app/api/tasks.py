"""任务与运行创建：POST /api/tasks、POST /api/tasks/{task_id}/runs、GET /api/tasks。"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.common import (
    DEFAULT_ACCEPTANCE_CRITERIA,
    budget_snapshot_dict,
    create_run,
    run_to_dict,
    task_to_dict,
)
from app.core.db import get_db
from app.core.enums import TERMINAL_STATUSES, RunStatus, Strategy, TaskTemplate
from app.core.models import Base, Task, TaskRun
from app.policy.workspace_access import (
    FolderAccess,
    normalize_project_dir,
    validate_workspace_access,
)
from app.worker import broker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


class BudgetSpec(BaseModel):
    max_total_tokens: int = Field(default=100_000, ge=1)
    max_wall_time_seconds: int = Field(default=1200, ge=1)
    max_active_runtime_seconds: int = Field(default=600, ge=1)
    max_llm_calls: int = Field(default=20, ge=1)
    max_cost: float = Field(default=5.0, gt=0)
    max_parallel_llm_calls: int = Field(default=2, ge=1)


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    workdir: str = Field(min_length=1, max_length=500)
    acceptance_criteria: str | None = None
    template: TaskTemplate = TaskTemplate.FIX_BUG
    require_approval: bool = True
    strategy: Strategy = Strategy.DYNAMIC
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    project_dir: str | None = Field(default=None, max_length=500)
    folder_access: FolderAccess = "isolated"

    @field_validator("project_dir")
    @classmethod
    def validate_project_dir(cls, value: str | None) -> str | None:
        return normalize_project_dir(value)

    @model_validator(mode="after")
    def full_access_requires_project_dir(self) -> CreateTaskRequest:
        validate_workspace_access(self.folder_access, self.project_dir)
        return self


class CreateRunRequest(BaseModel):
    """同一任务再跑一次的可选覆盖项。"""

    model_config = {"populate_by_name": True}

    strategy: Strategy | None = None
    budget: BudgetSpec | None = None
    model_cfg: dict | None = Field(default=None, alias="model_config")


def _enqueue_or_warn(run_id: uuid.UUID) -> str | None:
    """投递 worker 队列；broker 不可达不阻断创建，返回 warning。"""
    try:
        broker.enqueue_run(str(run_id))
        return None
    except Exception as exc:  # broker 不可达：任务保持 PENDING，等待重投
        logger.warning("enqueue_run failed for run %s: %s", run_id, exc)
        return f"run created but not enqueued: {exc}"


@router.post("/tasks", status_code=201)
def create_task(
    body: CreateTaskRequest,
    session: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict:
    if idempotency_key:
        existing = session.execute(
            select(Task).where(Task.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            latest = max(existing.runs, key=lambda r: r.attempt_no, default=None)
            return {"task_id": str(existing.id), "run_id": str(latest.id) if latest else None}

    task = Task(
        name=body.name,
        description=body.description,
        workdir=body.workdir,
        acceptance_criteria=body.acceptance_criteria or DEFAULT_ACCEPTANCE_CRITERIA,
        template=body.template.value,
        require_approval=body.require_approval,
        idempotency_key=idempotency_key,
    )
    session.add(task)
    session.flush()

    run = create_run(
        session,
        task,
        attempt_no=1,
        strategy=body.strategy,
        budget_fields=body.budget.model_dump(),
        model_config={
            "folder_access": body.folder_access,
            **({"project_dir": body.project_dir} if body.project_dir else {}),
        },
    )
    session.commit()

    result = {"task_id": str(task.id), "run_id": str(run.id)}
    warning = _enqueue_or_warn(run.id)
    if warning:
        result["warning"] = warning
    return result


@router.post("/tasks/{task_id}/runs", status_code=201)
def create_task_run(task_id: uuid.UUID, body: CreateRunRequest, session: Session = Depends(get_db)) -> dict:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    prev = max(task.runs, key=lambda r: r.attempt_no, default=None)
    attempt_no = (prev.attempt_no + 1) if prev else 1

    strategy = body.strategy or (Strategy(prev.strategy) if prev else Strategy.DYNAMIC)
    if body.budget is not None:
        budget_fields = body.budget.model_dump()
    elif prev is not None and prev.budget is not None:
        b = prev.budget
        budget_fields = {
            "max_total_tokens": b.max_total_tokens,
            "max_wall_time_seconds": b.max_wall_time_seconds,
            "max_active_runtime_seconds": b.max_active_runtime_seconds,
            "max_llm_calls": b.max_llm_calls,
            "max_cost": float(b.max_cost),
            "max_parallel_llm_calls": b.max_parallel_llm_calls,
        }
    else:
        budget_fields = BudgetSpec().model_dump()

    run = create_run(
        session,
        task,
        attempt_no=attempt_no,
        strategy=strategy,
        budget_fields=budget_fields,
        model_config=body.model_cfg,
    )
    session.commit()

    result = {"task_id": str(task.id), "run_id": str(run.id), "attempt_no": attempt_no}
    warning = _enqueue_or_warn(run.id)
    if warning:
        result["warning"] = warning
    return result


@router.get("/tasks")
def list_tasks(session: Session = Depends(get_db)) -> dict:
    tasks = list(session.execute(select(Task).order_by(Task.created_at.desc())).scalars())
    items = []
    for task in tasks:
        item = task_to_dict(task)
        item["created_at"] = task.created_at.isoformat() if task.created_at else None
        latest = max(task.runs, key=lambda r: r.attempt_no, default=None)
        if latest is not None:
            summary = run_to_dict(latest)
            if latest.budget is not None:
                snap = budget_snapshot_dict(session, latest.id)
                summary["used_tokens"] = snap["used_tokens"]
                summary["used_cost"] = snap["used_cost"]
            item["latest_run"] = summary
        else:
            item["latest_run"] = None
        items.append(item)
    return {"tasks": items}


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task_history(task_id: uuid.UUID, session: Session = Depends(get_db)) -> None:
    """Delete one terminal standalone task and its relational run history."""
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.work_session is not None:
        raise HTTPException(status_code=409, detail="Agent Team tasks cannot be deleted here")
    if any(RunStatus(run.status) not in TERMINAL_STATUSES for run in task.runs):
        raise HTTPException(status_code=409, detail="active task history cannot be deleted")

    run_ids = [run.id for run in task.runs]
    try:
        if run_ids:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name in {"tasks", "task_runs", "work_sessions"}:
                    continue
                if "run_id" in table.c:
                    session.execute(delete(table).where(table.c.run_id.in_(run_ids)))
            session.execute(delete(TaskRun).where(TaskRun.id.in_(run_ids)))
        session.execute(delete(Task).where(Task.id == task_id))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("task history deletion failed", extra={"task_id": str(task_id)})
        raise HTTPException(status_code=409, detail="task history could not be deleted") from None
