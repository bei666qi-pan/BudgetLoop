"""SSE 实时流：GET /api/runs/{run_id}/stream。

轮询 PostgreSQL execution_events（每 1s），`id: <seq>` 供 Last-Event-ID 断线回放；
run 进入终态且事件推送完毕后发送 run_finished 并关闭流。
"""
from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.core.db import SessionLocal
from app.core.enums import EventType, RunStatus
from app.core.models import TaskRun
from app.events.outbox import event_to_dict, list_events

router = APIRouter(tags=["stream"])

_POLL_INTERVAL_SECONDS = 1.0


def _fetch(run_id: uuid.UUID, after_seq: int) -> tuple[list[dict], str | None]:
    """短会话读取增量事件与 run 状态（同步 SQLAlchemy，线程池中执行）。"""
    session = SessionLocal()
    try:
        run = session.get(TaskRun, run_id)
        status = run.status if run is not None else None
        events = [event_to_dict(e) for e in list_events(session, run_id, after_seq)]
        return events, status
    finally:
        session.close()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, request: Request) -> EventSourceResponse:
    _, status = await run_in_threadpool(_fetch, run_id, 0)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")

    last_seq = 0
    last_event_id = request.headers.get("last-event-id")
    if last_event_id and last_event_id.isdigit():
        last_seq = int(last_event_id)

    async def event_generator():
        nonlocal last_seq
        while True:
            if await request.is_disconnected():
                return
            events, status = await run_in_threadpool(_fetch, run_id, last_seq)
            saw_finish = False
            for event in events:
                last_seq = event["seq"]
                if event["type"] == EventType.RUN_FINISHED.value:
                    saw_finish = True
                yield {
                    "id": str(event["seq"]),
                    "event": event["type"],
                    "data": json.dumps(event, ensure_ascii=False),
                }
            if status is not None and RunStatus(status).is_terminal:
                if not saw_finish:
                    yield {
                        "id": str(last_seq),
                        "event": EventType.RUN_FINISHED.value,
                        "data": json.dumps(
                            {"type": EventType.RUN_FINISHED.value, "payload": {"status": status}},
                            ensure_ascii=False,
                        ),
                    }
                return
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())
