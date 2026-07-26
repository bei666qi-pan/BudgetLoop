"""观测数据：llm-calls / tool-calls / budget / events / report / report/export。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import budget_snapshot_dict
from app.core.db import get_db
from app.core.enums import EventType
from app.core.models import FinalReport, LlmCall, TaskPhase, TaskRun, ToolCall
from app.events.outbox import event_to_dict, list_events

router = APIRouter(tags=["observations"])


def _serialize(obj: Any) -> dict:
    """把 ORM 行转成 JSON 友好的 dict（UUID/datetime/Decimal 转字符串/数值）。"""
    out = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.name)
        if isinstance(v, uuid.UUID):
            v = str(v)
        elif isinstance(v, datetime):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = float(v)
        out[col.name] = v
    return out


def _require_run(session: Session, run_id: uuid.UUID) -> TaskRun:
    run = session.get(TaskRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/llm-calls")
def get_llm_calls(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    _require_run(session, run_id)
    rows = session.execute(
        select(LlmCall).where(LlmCall.run_id == run_id).order_by(LlmCall.started_at.asc().nulls_last(), LlmCall.id)
    ).scalars()
    return {"llm_calls": [_serialize(r) for r in rows]}


@router.get("/runs/{run_id}/tool-calls")
def get_tool_calls(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    _require_run(session, run_id)
    rows = session.execute(
        select(ToolCall).where(ToolCall.run_id == run_id).order_by(ToolCall.started_at.asc().nulls_last(), ToolCall.id)
    ).scalars()
    return {"tool_calls": [_serialize(r) for r in rows]}


@router.get("/runs/{run_id}/budget")
def get_budget(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    _require_run(session, run_id)
    phases = session.execute(
        select(TaskPhase).where(TaskPhase.run_id == run_id).order_by(TaskPhase.id)
    ).scalars()
    reallocations = [
        event_to_dict(e)
        for e in list_events(session, run_id, after_seq=0, limit=10_000)
        if e.type == EventType.BUDGET_REALLOCATED.value
    ]
    return {
        "budget": budget_snapshot_dict(session, run_id),
        "phases": [_serialize(p) for p in phases],
        "reallocations": reallocations,
    }


@router.get("/runs/{run_id}/events")
def get_events(
    run_id: uuid.UUID,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_db),
) -> dict:
    _require_run(session, run_id)
    return {"events": [event_to_dict(e) for e in list_events(session, run_id, after_seq, limit)]}


def _report_to_dict(report: FinalReport) -> dict:
    return _serialize(report)


def _get_report_or_404(session: Session, run_id: uuid.UUID) -> FinalReport:
    _require_run(session, run_id)
    report = session.get(FinalReport, run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.get("/runs/{run_id}/report")
def get_report(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return _report_to_dict(_get_report_or_404(session, run_id))


@router.get("/runs/{run_id}/report/export")
def export_report(
    run_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|md)$"),  # noqa: A002 - 契约参数名
    session: Session = Depends(get_db),
) -> Response:
    report = _get_report_or_404(session, run_id)
    if format == "md":
        return Response(
            content=report.report_md or "",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="report-{run_id}.md"'},
        )
    return Response(
        content=json.dumps(_report_to_dict(report), ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="report-{run_id}.json"'},
    )
