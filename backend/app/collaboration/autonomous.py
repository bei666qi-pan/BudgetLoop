"""Durable, permission-neutral stage release for autonomous preset teams."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import MessageDeliveryState, RunStatus, SessionMessageKind
from app.core.models import ExecutionEvent, SessionMessage, TaskRun, WorkContainer, WorkSession, utcnow


def is_autonomous(container: WorkContainer) -> bool:
    return bool((container.preset_snapshot or {}).get("team_mode") == "autonomous")


def _stage_roles(snapshot: dict) -> dict[str, list[str]]:
    return {
        str(wave.get("stage")): [str(key) for key in wave.get("roles", [])]
        for wave in (snapshot.get("activation_plan") or {}).get("activation_waves", [])
    }


def _dependencies(snapshot: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for edge in (snapshot.get("activation_plan") or {}).get("required_handoffs", []):
        result.setdefault(str(edge.get("to_stage")), set()).add(str(edge.get("from_stage")))
    return result


def _role_sessions(container: WorkContainer) -> dict[str, WorkSession]:
    applied = (container.preset_snapshot or {}).get("applied_roles", [])
    by_session_id = {str(item.id): item for item in container.sessions}
    return {
        str(item["key"]): by_session_id[str(item["session_id"])]
        for item in applied
        if isinstance(item, dict) and item.get("key") and str(item.get("session_id")) in by_session_id
    }


def eligible_autonomous_runs(container: WorkContainer) -> list[TaskRun]:
    """Return PENDING roles whose entire prerequisite stages completed."""
    if not is_autonomous(container):
        return []
    snapshot = container.preset_snapshot or {}
    roles_by_stage = _stage_roles(snapshot)
    dependencies = _dependencies(snapshot)
    sessions = _role_sessions(container)

    def stage_complete(stage: str) -> bool:
        roles = roles_by_stage.get(stage, [])
        return bool(roles) and all(
            sessions.get(role) is not None
            and sessions[role].current_run is not None
            and sessions[role].current_run.status == RunStatus.COMPLETED.value
            for role in roles
        )

    ready: list[TaskRun] = []
    for stage, roles in roles_by_stage.items():
        if not all(stage_complete(source) for source in dependencies.get(stage, set())):
            continue
        for role in roles:
            item = sessions.get(role)
            if item and item.current_run and item.current_run.status == RunStatus.PENDING.value:
                ready.append(item.current_run)
    return ready


def _latest_public_output(session: Session, run_id: uuid.UUID, fallback: str) -> str:
    event = session.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.run_id == run_id, ExecutionEvent.type == "agent_message")
        .order_by(ExecutionEvent.seq.desc())
        .limit(1)
    ).scalar_one_or_none()
    text = str((event.payload or {}).get("text") or "").strip() if event else ""
    return text[:4_000] or fallback


def release_autonomous_stages(session: Session, run: TaskRun) -> list[uuid.UUID]:
    """Persist automatic handoffs and return newly eligible runs exactly once.

    The caller commits before enqueueing. Only successful source completion can
    release a stage; pending/failed sources retain the existing attention path.
    """
    owner = session.execute(
        select(WorkSession).where(WorkSession.current_run_id == run.id)
    ).scalar_one_or_none()
    if owner is None or run.status != RunStatus.COMPLETED.value:
        return []
    container = session.get(WorkContainer, owner.container_id)
    if container is None or not is_autonomous(container):
        return []

    # Load current runs so completion gates are evaluated from durable state.
    container = session.execute(select(WorkContainer).where(WorkContainer.id == container.id)).scalar_one()
    session.refresh(container, attribute_names=["sessions"])
    snapshot = dict(container.preset_snapshot or {})
    roles_by_stage = _stage_roles(snapshot)
    dependencies = _dependencies(snapshot)
    sessions = _role_sessions(container)
    source_role = next((key for key, item in sessions.items() if item.id == owner.id), None)
    if source_role is None:
        return []
    source_stage = next((stage for stage, roles in roles_by_stage.items() if source_role in roles), None)
    if source_stage is None:
        return []

    def stage_complete(stage: str) -> bool:
        roles = roles_by_stage.get(stage, [])
        return bool(roles) and all(
            sessions.get(role) is not None
            and sessions[role].current_run is not None
            and sessions[role].current_run.status == RunStatus.COMPLETED.value
            for role in roles
        )

    released = set((snapshot.get("dispatch") or {}).get("autonomous_released_stages") or [])
    ready_run_ids: list[uuid.UUID] = []
    for target_stage, sources in dependencies.items():
        if source_stage not in sources or target_stage in released:
            continue
        if not all(stage_complete(stage) for stage in sources):
            continue
        source_sessions = [
            sessions[role] for stage in sources for role in roles_by_stage.get(stage, []) if role in sessions
        ]
        for source in source_sessions:
            source_run = source.current_run
            if source_run is None:
                continue
            output = _latest_public_output(
                session,
                source_run.id,
                f"{source.role} 已完成其自主阶段；请结合项目目标继续后续工作。",
            )
            for target_role in roles_by_stage.get(target_stage, []):
                recipient = sessions.get(target_role)
                if recipient is None or recipient.current_run is None:
                    continue
                key = f"autonomous:{source_run.id}:{recipient.current_run.id}"
                exists = session.execute(
                    select(SessionMessage.id).where(
                        SessionMessage.container_id == container.id,
                        SessionMessage.idempotency_key == key,
                    )
                ).scalar_one_or_none()
                if exists is None:
                    session.add(
                        SessionMessage(
                            container_id=container.id,
                            sender_session_id=source.id,
                            recipient_session_id=recipient.id,
                            author_type="agent",
                            kind=SessionMessageKind.HANDOFF.value,
                            content=f"自主 Handoff（{source.role}）\n\n{output}",
                            delivery_state=MessageDeliveryState.QUEUED.value,
                            idempotency_key=key,
                            message_metadata={
                                "autonomous": True,
                                "source_run_id": str(source_run.id),
                                "target_stage": target_stage,
                            },
                        )
                    )
        released.add(target_stage)
        for target_role in roles_by_stage.get(target_stage, []):
            recipient = sessions.get(target_role)
            if (
                recipient
                and recipient.current_run
                and recipient.current_run.status == RunStatus.PENDING.value
            ):
                ready_run_ids.append(recipient.current_run.id)

    if released:
        dispatch = dict(snapshot.get("dispatch") or {})
        dispatch["autonomous_released_stages"] = sorted(released)
        dispatch["last_requested_at"] = utcnow().isoformat()
        snapshot["dispatch"] = dispatch
        container.preset_snapshot = snapshot
        container.updated_at = utcnow()
    return ready_run_ids
