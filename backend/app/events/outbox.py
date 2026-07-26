"""SSE outbox：execution_events 的写入与读取。

事件必须随业务变更在同一事务内写入（调用方负责 commit），
保证状态变更与事件不会丢失/乱序。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.models import ExecutionEvent


def emit_event(
    session: Session,
    run_id: uuid.UUID | str,
    type: EventType | str,  # noqa: A002 - 与表字段同名
    payload: dict | None = None,
) -> ExecutionEvent:
    """同事务写入一条事件并 flush（拿到 seq），由调用方 commit。"""
    event = ExecutionEvent(
        run_id=uuid.UUID(str(run_id)),
        type=type.value if isinstance(type, EventType) else str(type),
        payload=payload or {},
    )
    session.add(event)
    session.flush()
    return event


def list_events(
    session: Session,
    run_id: uuid.UUID | str,
    after_seq: int = 0,
    limit: int = 500,
) -> list[ExecutionEvent]:
    """按 seq 升序返回 run 的事件（seq > after_seq），用于回放与轮询。"""
    stmt = (
        select(ExecutionEvent)
        .where(ExecutionEvent.run_id == uuid.UUID(str(run_id)), ExecutionEvent.seq > after_seq)
        .order_by(ExecutionEvent.seq)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def event_to_dict(event: ExecutionEvent) -> dict:
    return {
        "seq": event.seq,
        "type": event.type,
        "payload": event.payload,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
