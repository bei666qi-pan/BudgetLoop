"""Work-container coordination API.

The coordination layer is additive: each runnable session owns a normal Task and
TaskRun, while cross-session context moves only through explicit SessionMessage rows.
"""
from __future__ import annotations

import uuid
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.api.common import DEFAULT_ACCEPTANCE_CRITERIA, budget_snapshot_dict, create_run
from app.api.runs import _transition
from app.api.tasks import BudgetSpec, _enqueue_or_warn
from app.core.db import get_db
from app.core.enums import (
    ContainerLifecycle,
    MessageDeliveryState,
    RunStatus,
    SessionMessageKind,
    Strategy,
    TaskTemplate,
    WorkspacePolicy,
)
from app.core.models import (
    ExecutionEvent,
    SessionMessage,
    Task,
    TaskRun,
    WorkContainer,
    WorkSession,
    utcnow,
)
from app.execution_engines import DEFAULT_ENGINE_ID, engine_preflight, get_engine

router = APIRouter(tags=["work-containers"])

RUNNING_STATUSES = {
    RunStatus.PLANNING.value,
    RunStatus.EXECUTING.value,
    RunStatus.OBSERVING.value,
    RunStatus.EVALUATING.value,
    RunStatus.REPLANNING.value,
}
WAITING_STATUSES = {
    RunStatus.PENDING.value,
    RunStatus.WAITING_APPROVAL.value,
    RunStatus.PAUSED.value,
}
ATTENTION_STATUSES = {RunStatus.FAILED.value, RunStatus.BUDGET_EXHAUSTED.value}


class CreateWorkContainerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=200)
    project_goal: str = Field(min_length=1, max_length=10_000)
    shared_context: str = Field(default="", max_length=30_000)
    base_workdir: str = Field(min_length=1, max_length=500)
    default_workspace_policy: WorkspacePolicy = WorkspacePolicy.ISOLATED

    @field_validator("name", "project_goal")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("base_workdir")
    @classmethod
    def absolute_workdir(cls, value: str) -> str:
        value = value.strip()
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("must be an absolute normalized workspace path")
        return str(path)


class UpdateWorkContainerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_goal: str | None = Field(default=None, min_length=1, max_length=10_000)
    shared_context: str | None = Field(default=None, max_length=30_000)
    lifecycle_state: ContainerLifecycle | None = None
    default_workspace_policy: WorkspacePolicy | None = None


class CreateWorkSessionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    role: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=10_000)
    private_context: str = Field(default="", max_length=30_000)
    acceptance_criteria: str | None = Field(default=None, max_length=20_000)
    template: TaskTemplate = TaskTemplate.SMALL_FEATURE
    require_approval: bool = True
    strategy: Strategy = Strategy.DYNAMIC
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    worktree_enabled: bool | None = None
    execution_engine: str = Field(default=DEFAULT_ENGINE_ID, min_length=1, max_length=50)

    @field_validator("role", "goal")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CreateSessionMessageRequest(BaseModel):
    model_config = {"extra": "forbid"}

    sender_session_id: uuid.UUID | None = None
    kind: SessionMessageKind = SessionMessageKind.MESSAGE
    content: str = Field(min_length=1, max_length=8_000)
    metadata: dict = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


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


def _runtime_status(item: WorkSession) -> str:
    return item.current_run.status if item.current_run is not None else item.status


def _session_dict(item: WorkSession, *, include_private: bool = False) -> dict:
    run = item.current_run
    value: dict[str, object] = {
        "id": str(item.id),
        "container_id": str(item.container_id),
        "role": item.role,
        "goal": item.goal,
        "status": _runtime_status(item),
        "task_id": str(item.task_id),
        "current_run_id": str(item.current_run_id),
        "conversation_id": str(run.conversation_id or item.conversation_id)
        if (run and run.conversation_id) or item.conversation_id
        else None,
        "iteration": run.iteration if run else 0,
        "worktree_enabled": item.worktree_enabled,
        "worktree_branch": item.worktree_branch,
        "worktree_path": item.worktree_path,
        "workspace_status": item.workspace_status,
        "workspace_error": item.workspace_error,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
    if include_private:
        value["private_context"] = item.private_context
        db = object_session(item)
        value["budget"] = budget_snapshot_dict(db, run.id) if run and db is not None else None
    return value


def _counts(items: list[WorkSession]) -> dict:
    statuses = [_runtime_status(item) for item in items]
    return {
        "sessions": len(items),
        "running": sum(status in RUNNING_STATUSES for status in statuses),
        "waiting": sum(status in WAITING_STATUSES for status in statuses),
        "attention": sum(status in ATTENTION_STATUSES for status in statuses),
    }


def _container_dict(container: WorkContainer, *, include_context: bool = True) -> dict:
    items = list(container.sessions)
    value = {
        "id": str(container.id),
        "name": container.name,
        "project_goal": container.project_goal,
        "lifecycle_state": container.lifecycle_state,
        "base_workdir": container.base_workdir,
        "default_workspace_policy": container.default_workspace_policy,
        "preset_id": container.preset_id,
        "preset_version": container.preset_version,
        "counts": _counts(items),
        "sessions": [_session_dict(item) for item in items],
        "created_at": container.created_at.isoformat(),
        "updated_at": container.updated_at.isoformat(),
    }
    if include_context:
        value["shared_context"] = container.shared_context
        value["preset_snapshot"] = container.preset_snapshot
    return value


def _message_dict(message: SessionMessage) -> dict:
    return {
        "id": str(message.id),
        "container_id": str(message.container_id),
        "sender_session_id": str(message.sender_session_id) if message.sender_session_id else None,
        "sender_role": message.sender_session.role if message.sender_session else "操作员",
        "recipient_session_id": str(message.recipient_session_id),
        "recipient_role": message.recipient_session.role if message.recipient_session else None,
        "author_type": message.author_type,
        "kind": message.kind,
        "content": message.content,
        "delivery_state": message.delivery_state,
        "metadata": message.message_metadata or {},
        "created_at": message.created_at.isoformat(),
        "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
    }


@router.get("/work-containers")
def list_work_containers(
    lifecycle: ContainerLifecycle | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> dict:
    query = select(WorkContainer).options(
        selectinload(WorkContainer.sessions).selectinload(WorkSession.current_run)
    )
    if lifecycle is not None:
        query = query.where(WorkContainer.lifecycle_state == lifecycle.value)
    containers = list(
        session.execute(query.order_by(WorkContainer.updated_at.desc()).offset(offset).limit(limit)).scalars()
    )
    return {"containers": [_container_dict(item, include_context=False) for item in containers]}


@router.post("/work-containers", status_code=201)
def create_work_container(
    body: CreateWorkContainerRequest, session: Session = Depends(get_db)
) -> dict:
    container = WorkContainer(
        name=body.name,
        project_goal=body.project_goal,
        shared_context=body.shared_context,
        base_workdir=body.base_workdir,
        default_workspace_policy=body.default_workspace_policy.value,
    )
    session.add(container)
    session.commit()
    session.refresh(container)
    return _container_dict(container)


@router.get("/work-containers/{container_id}")
def get_work_container(container_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return _container_dict(_container_or_404(session, container_id))


@router.patch("/work-containers/{container_id}")
def update_work_container(
    container_id: uuid.UUID,
    body: UpdateWorkContainerRequest,
    session: Session = Depends(get_db),
) -> dict:
    container = _container_or_404(session, container_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if isinstance(value, (ContainerLifecycle, WorkspacePolicy)):
            value = value.value
        if field in {"name", "project_goal"} and isinstance(value, str):
            value = value.strip()
            if not value:
                raise HTTPException(status_code=422, detail=f"{field} must not be blank")
        setattr(container, field, value)
    container.updated_at = utcnow()
    session.commit()
    return _container_dict(container)


@router.post("/work-containers/{container_id}/sessions", status_code=201)
def create_work_session(
    container_id: uuid.UUID,
    body: CreateWorkSessionRequest,
    session: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict:
    container = _container_or_404(session, container_id)
    if container.lifecycle_state != ContainerLifecycle.ACTIVE.value:
        raise HTTPException(status_code=409, detail="work container is not active")
    if get_engine(body.execution_engine) is None:
        raise HTTPException(status_code=422, detail="unknown execution engine")
    engine_status = engine_preflight(body.execution_engine)
    if not engine_status.runtime_available:
        raise HTTPException(status_code=409, detail=engine_status.reason)
    if idempotency_key:
        existing = session.execute(
            select(WorkSession).where(
                WorkSession.container_id == container_id,
                WorkSession.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"session": _session_dict(existing, include_private=True), "created": False}

    item, run = _create_work_session_records(
        session,
        container,
        body,
        idempotency_key=idempotency_key,
    )
    container.updated_at = utcnow()
    session.commit()

    result = {"session": _session_dict(item, include_private=True), "created": True}
    warning = _enqueue_or_warn(run.id)
    if warning:
        result["warning"] = warning
    return result


def _create_work_session_records(
    session: Session,
    container: WorkContainer,
    body: CreateWorkSessionRequest,
    *,
    idempotency_key: str | None,
    model_config_overrides: dict | None = None,
) -> tuple[WorkSession, TaskRun]:
    """Create a Task/Run/WorkSession graph inside the caller's transaction."""
    task = Task(
        name=f"{container.name} · {body.role}",
        description=(
            f"项目目标：{container.project_goal}\n\n"
            f"Session 角色：{body.role}\nSession 目标：{body.goal}\n\n"
            f"项目共享上下文：\n{container.shared_context or '（无）'}\n\n"
            f"Session 私有上下文：\n{body.private_context or '（无）'}"
        ),
        workdir=container.base_workdir,
        acceptance_criteria=body.acceptance_criteria or DEFAULT_ACCEPTANCE_CRITERIA,
        template=body.template.value,
        require_approval=body.require_approval,
        idempotency_key=f"work-session:{container.id}:{idempotency_key}" if idempotency_key else None,
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
            "execution_engine": body.execution_engine,
            **(model_config_overrides or {}),
        },
    )
    worktree_enabled = (
        body.worktree_enabled
        if body.worktree_enabled is not None
        else container.default_workspace_policy == WorkspacePolicy.WORKTREE.value
    )
    item = WorkSession(
        container_id=container.id,
        role=body.role,
        goal=body.goal,
        private_context=body.private_context,
        task_id=task.id,
        current_run_id=run.id,
        worktree_enabled=worktree_enabled,
        idempotency_key=idempotency_key,
    )
    session.add(item)
    session.flush()
    return item, run


def _transcript(session: Session, item: WorkSession) -> list[dict]:
    messages = list(
        session.execute(
            select(SessionMessage)
            .options(
                selectinload(SessionMessage.sender_session),
                selectinload(SessionMessage.recipient_session),
            )
            .where(
                SessionMessage.container_id == item.container_id,
                or_(
                    SessionMessage.sender_session_id == item.id,
                    SessionMessage.recipient_session_id == item.id,
                ),
            )
            .order_by(SessionMessage.created_at)
            .limit(200)
        ).scalars()
    )
    transcript: list[dict] = [
        {**_message_dict(message), "entry_type": "handoff" if message.kind == "handoff" else "message"}
        for message in messages
    ]
    events = list(
        session.execute(
            select(ExecutionEvent)
            .where(
                ExecutionEvent.run_id == item.current_run_id,
                ExecutionEvent.type == "agent_message",
            )
            .order_by(ExecutionEvent.seq)
            .limit(200)
        ).scalars()
    )
    for event in events:
        transcript.append(
            {
                "id": f"event-{event.seq}",
                "entry_type": "agent_output",
                "author_type": "agent",
                "sender_session_id": str(item.id),
                "sender_role": item.role,
                "recipient_session_id": None,
                "recipient_role": None,
                "content": str((event.payload or {}).get("text") or ""),
                "delivery_state": "recorded",
                "metadata": {"iteration": (event.payload or {}).get("iteration")},
                "created_at": event.created_at.isoformat(),
                "delivered_at": None,
            }
        )
    transcript.sort(key=lambda value: (value["created_at"], value["id"]))
    return transcript


@router.get("/work-containers/{container_id}/sessions/{session_id}")
def get_work_session(
    container_id: uuid.UUID, session_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict:
    item = _session_or_404(session, container_id, session_id)
    return {"session": _session_dict(item, include_private=True), "transcript": _transcript(session, item)}


@router.post("/work-containers/{container_id}/sessions/{session_id}/messages", status_code=201)
def create_session_message(
    container_id: uuid.UUID,
    session_id: uuid.UUID,
    body: CreateSessionMessageRequest,
    session: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict:
    recipient = _session_or_404(session, container_id, session_id)
    if idempotency_key:
        existing = session.execute(
            select(SessionMessage)
            .options(
                selectinload(SessionMessage.sender_session),
                selectinload(SessionMessage.recipient_session),
            )
            .where(
                SessionMessage.container_id == container_id,
                SessionMessage.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"message": _message_dict(existing), "created": False}

    sender = None
    if body.sender_session_id is not None:
        sender = _session_or_404(session, container_id, body.sender_session_id)
        if sender.id == recipient.id:
            raise HTTPException(status_code=422, detail="sender and recipient sessions must differ")
    message = SessionMessage(
        container_id=container_id,
        sender_session_id=sender.id if sender else None,
        recipient_session_id=recipient.id,
        author_type="session" if sender else "operator",
        kind=body.kind.value,
        content=body.content,
        delivery_state=MessageDeliveryState.QUEUED.value,
        idempotency_key=idempotency_key,
        message_metadata=body.metadata,
    )
    session.add(message)
    recipient.container.updated_at = utcnow()
    session.commit()
    session.refresh(message)
    return {"message": _message_dict(message), "created": True}


@router.post("/work-containers/{container_id}/sessions/{session_id}/pause")
def pause_work_session(
    container_id: uuid.UUID, session_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict:
    item = _session_or_404(session, container_id, session_id)
    result = _transition(session, item.current_run, RunStatus.PAUSED)
    item.status = result["status"]
    item.updated_at = utcnow()
    session.commit()
    return {**result, "session_id": str(item.id)}
