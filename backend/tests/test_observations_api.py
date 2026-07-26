"""观测端点测试：_serialize, _require_run, llm-calls, tool-calls, budget, events, report, export。"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from app.api.observations import (  # noqa: E402
    _get_report_or_404,
    _report_to_dict,
    _require_run,
    _serialize,
)
from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.enums import EventType  # noqa: E402
from app.core.models import (  # noqa: E402
    ExecutionEvent,
    FinalReport,
    LlmCall,
    ToolCall,
    TaskRun,
)
from app.events.outbox import emit_event  # noqa: E402
from app.main import app  # noqa: E402
from app.worker import broker  # noqa: E402
from tests.conftest import requires_docker  # noqa: E402

AUTH = {"Authorization": f"Bearer {settings.api_token}"}


# ---------------------------------------------------------------------------
# unit tests: _serialize
# ---------------------------------------------------------------------------


def _make_llm_call(**overrides) -> LlmCall:
    """在内存中创建一个 LlmCall 实例（未持久化），供 _serialize 单元测试使用。"""
    defaults = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "call_id": "test-call-001",
        "iteration": 1,
        "phase": "modify",
        "call_kind": "agent",
        "agent_name": "test-agent",
        "model": "gpt-4o",
        "provider": "openai",
        "started_at": datetime(2025, 7, 20, 10, 0, 0, tzinfo=timezone.utc),
        "ended_at": datetime(2025, 7, 20, 10, 0, 5, tzinfo=timezone.utc),
        "duration_ms": 5000,
        "ttft_ms": 200,
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "reasoning_tokens": 50,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 1250,
        "token_source": "litellm",
        "estimated_cost": 0.015,
        "finish_reason": "stop",
        "request_status": "success",
        "retry_count": 0,
        "response_id": "resp-123",
        "input_summary": "fix bug",
        "output_summary": "done",
        "artifact_ref": "/artifacts/abc",
        "decision": "apply patch",
        "effective": True,
        "progress_score": 0.85,
        "inefficiency_reason": None,
    }
    defaults.update(overrides)
    return LlmCall(**defaults)


class TestSerialize:
    """_serialize 纯单元测试 — 不依赖数据库。"""

    def test_converts_uuid_to_string(self):
        call = _make_llm_call()
        result = _serialize(call)
        assert isinstance(result["id"], str)
        assert isinstance(result["run_id"], str)
        uuid.UUID(result["id"])  # 可解析
        uuid.UUID(result["run_id"])  # 可解析

    def test_converts_datetime_to_isoformat(self):
        call = _make_llm_call()
        result = _serialize(call)
        assert result["started_at"] == "2025-07-20T10:00:00+00:00"
        assert result["ended_at"] == "2025-07-20T10:00:05+00:00"

    def test_converts_decimal_to_float(self):
        call = _make_llm_call()
        # estimated_cost 在模型中是 Numeric(12,8)，SA 映射为 float，但可为 Decimal
        # 构造时直接传 Decimal 验证转换
        call.estimated_cost = Decimal("0.01500000")
        result = _serialize(call)
        assert isinstance(result["estimated_cost"], float)
        assert result["estimated_cost"] == 0.015

    def test_preserves_regular_fields(self):
        call = _make_llm_call()
        result = _serialize(call)
        assert result["iteration"] == 1
        assert result["phase"] == "modify"
        assert result["call_kind"] == "agent"
        assert result["agent_name"] == "test-agent"
        assert result["model"] == "gpt-4o"
        assert result["provider"] == "openai"
        assert result["prompt_tokens"] == 1000
        assert result["completion_tokens"] == 200
        assert result["progress_score"] == 0.85

    def test_handles_none_values(self):
        call = _make_llm_call(ended_at=None, estimated_cost=None, progress_score=None)
        result = _serialize(call)
        assert result["ended_at"] is None
        assert result["estimated_cost"] is None
        assert result["progress_score"] is None
        # started_at 仍然存在且转换
        assert result["started_at"] == "2025-07-20T10:00:00+00:00"

    def test_returns_all_columns(self):
        call = _make_llm_call()
        result = _serialize(call)
        expected_columns = {c.name for c in call.__table__.columns}
        assert set(result.keys()) == expected_columns


# ---------------------------------------------------------------------------
# unit tests: _require_run
# ---------------------------------------------------------------------------


class TestRequireRun:
    """_require_run 纯单元测试 — mock Session.get。"""

    def test_returns_run_when_found(self):
        mock_session = MagicMock(spec=Session)
        fake_run = MagicMock(spec=TaskRun)
        run_id = uuid.uuid4()
        mock_session.get.return_value = fake_run

        result = _require_run(mock_session, run_id)
        assert result is fake_run
        mock_session.get.assert_called_once_with(TaskRun, run_id)

    def test_raises_404_when_not_found(self):
        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None
        run_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc:
            _require_run(mock_session, run_id)
        assert exc.value.status_code == 404
        assert exc.value.detail == "run not found"


# ---------------------------------------------------------------------------
# unit tests: _get_report_or_404
# ---------------------------------------------------------------------------


class TestGetReportOr404:
    """_get_report_or_404 纯单元测试 — mock Session.get。"""

    def test_returns_report_when_both_found(self):
        mock_session = MagicMock(spec=Session)
        fake_run = MagicMock(spec=TaskRun)
        fake_report = MagicMock(spec=FinalReport)
        run_id = uuid.uuid4()
        # get 第一次被 _require_run 调用 (TaskRun)，第二次被 _get_report_or_404 调用 (FinalReport)
        mock_session.get.side_effect = [fake_run, fake_report]

        result = _get_report_or_404(mock_session, run_id)
        assert result is fake_report
        assert mock_session.get.call_count == 2

    def test_raises_404_when_run_not_found(self):
        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None
        run_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc:
            _get_report_or_404(mock_session, run_id)
        assert exc.value.status_code == 404
        assert exc.value.detail == "run not found"
        # 只调了一次 get（_require_run 阶段就抛异常了）
        assert mock_session.get.call_count == 1

    def test_raises_404_when_report_not_found(self):
        mock_session = MagicMock(spec=Session)
        fake_run = MagicMock(spec=TaskRun)
        run_id = uuid.uuid4()
        mock_session.get.side_effect = [fake_run, None]

        with pytest.raises(HTTPException) as exc:
            _get_report_or_404(mock_session, run_id)
        assert exc.value.status_code == 404
        assert exc.value.detail == "report not found"


# ---------------------------------------------------------------------------
# unit tests: _report_to_dict
# ---------------------------------------------------------------------------


class TestReportToDict:
    """_report_to_dict 纯单元测试。"""

    def test_serializes_full_report(self):
        report = FinalReport(
            run_id=uuid.uuid4(),
            status="completed",
            acceptance_result={"passed": True, "checks": 3},
            files_changed={"added": 1, "modified": 2},
            diff_summary="diff content here",
            totals={"tokens": 5000, "cost": 0.05},
            strategy_switches=[{"from": "fixed", "to": "dynamic"}],
            open_issues=[{"severity": "low", "desc": "minor"}],
            suggestions=["add more tests"],
            report_md="# Final Report\n\nAll tests pass.",
            artifact_ref="/artifacts/report-001",
        )
        result = _report_to_dict(report)
        assert isinstance(result["run_id"], str)
        assert result["status"] == "completed"
        assert result["acceptance_result"] == {"passed": True, "checks": 3}
        assert result["files_changed"] == {"added": 1, "modified": 2}
        assert result["diff_summary"] == "diff content here"
        assert result["totals"] == {"tokens": 5000, "cost": 0.05}
        assert result["report_md"] == "# Final Report\n\nAll tests pass."


# ---------------------------------------------------------------------------
# integration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(pg_session, monkeypatch):
    """TestClient fixture：将 get_db 依赖重定向到 pg_session，mock broker。"""

    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    enqueued: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: enqueued.append(run_id))
    with TestClient(app) as c:
        yield c, enqueued
    app.dependency_overrides.clear()


def _create_task(client: TestClient, key: str | None = None, **overrides) -> dict:
    """创建任务 + 运行并返回 {task_id, run_id}。"""
    body = {
        "name": "观测端点测试任务",
        "description": "用于观测端点集成测试",
        "workdir": "/workspace/test",
    }
    body.update(overrides)
    headers = dict(AUTH)
    if key:
        headers["Idempotency-Key"] = key
    resp = client.post("/api/tasks", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/llm-calls
# ---------------------------------------------------------------------------


class TestGetLlmCalls:
    @requires_docker
    def test_empty_list(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = data["run_id"]

        resp = c.get(f"/api/runs/{run_id}/llm-calls", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"llm_calls": []}

    @requires_docker
    def test_multiple_calls_sorted_by_started_at(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        t1 = datetime(2025, 7, 20, 10, 0, 10, tzinfo=timezone.utc)
        t2 = datetime(2025, 7, 20, 10, 0, 5, tzinfo=timezone.utc)
        t3 = datetime(2025, 7, 20, 10, 0, 0, tzinfo=timezone.utc)

        # 插入三条 LLM 调用，started_at 乱序
        c1 = LlmCall(run_id=run_id, call_id="call-c", started_at=t1, model="gpt-4o")
        c2 = LlmCall(run_id=run_id, call_id="call-b", started_at=t2, model="gpt-4o")
        c3 = LlmCall(run_id=run_id, call_id="call-a", started_at=t3, model="gpt-4o")
        pg_session.add_all([c1, c2, c3])
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/llm-calls", headers=AUTH)
        assert resp.status_code == 200
        calls = resp.json()["llm_calls"]
        assert len(calls) == 3
        # 按 started_at 升序：t3(call-a) < t2(call-b) < t1(call-c)
        assert calls[0]["call_id"] == "call-a"
        assert calls[1]["call_id"] == "call-b"
        assert calls[2]["call_id"] == "call-c"

    @requires_docker
    def test_call_has_serialized_fields(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        call = LlmCall(
            run_id=run_id,
            call_id="call-serialized",
            started_at=datetime(2025, 7, 20, 12, 0, 0, tzinfo=timezone.utc),
            model="gpt-4o",
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            token_source="litellm",
        )
        pg_session.add(call)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/llm-calls", headers=AUTH)
        assert resp.status_code == 200
        result = resp.json()["llm_calls"][0]
        # UUID 转字符串
        assert isinstance(result["id"], str)
        assert isinstance(result["run_id"], str)
        # datetime 转 isoformat
        assert result["started_at"] == "2025-07-20T12:00:00+00:00"
        # 普通字段
        assert result["model"] == "gpt-4o"
        assert result["prompt_tokens"] == 500
        assert result["total_tokens"] == 600

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/llm-calls", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/tool-calls
# ---------------------------------------------------------------------------


class TestGetToolCalls:
    @requires_docker
    def test_empty_list(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = data["run_id"]

        resp = c.get(f"/api/runs/{run_id}/tool-calls", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"tool_calls": []}

    @requires_docker
    def test_multiple_calls_sorted_by_started_at(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        t1 = datetime(2025, 7, 20, 14, 0, 10, tzinfo=timezone.utc)
        t2 = datetime(2025, 7, 20, 14, 0, 0, tzinfo=timezone.utc)

        tc1 = ToolCall(run_id=run_id, tool="bash", started_at=t1, args_summary="cmd1")
        tc2 = ToolCall(run_id=run_id, tool="edit", started_at=t2, args_summary="cmd2")
        pg_session.add_all([tc1, tc2])
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/tool-calls", headers=AUTH)
        assert resp.status_code == 200
        calls = resp.json()["tool_calls"]
        assert len(calls) == 2
        # 按 started_at 升序：t2 < t1
        assert calls[0]["tool"] == "edit"
        assert calls[1]["tool"] == "bash"

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/tool-calls", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/budget
# ---------------------------------------------------------------------------


class TestGetBudget:
    @requires_docker
    def test_budget_snapshot_phases_and_reallocations(self, client, pg_session):
        c, _ = client
        data = _create_task(c, budget={"max_total_tokens": 8000, "max_llm_calls": 5, "max_cost": 3.0})
        run_id = data["run_id"]

        resp = c.get(f"/api/runs/{run_id}/budget", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()

        # budget snapshot
        assert "budget" in body
        assert body["budget"]["max_total_tokens"] == 8000
        assert body["budget"]["remaining_calls"] == 5

        # phases
        assert "phases" in body
        assert len(body["phases"]) == 6
        phase_names = {p["phase"] for p in body["phases"]}
        assert phase_names == {"scan", "analyze", "modify", "verify", "repair", "summarize"}

        # reallocations 初始为空
        assert body["reallocations"] == []

    @requires_docker
    def test_includes_reallocation_events(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        # 写入一条 BUDGET_REALLOCATED 事件
        emit_event(
            pg_session,
            run_id,
            EventType.BUDGET_REALLOCATED,
            {"from_phase": "scan", "to_phase": "modify", "tokens": 200},
        )
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/budget", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["reallocations"]) >= 1
        realloc = body["reallocations"][0]
        assert realloc["type"] == EventType.BUDGET_REALLOCATED.value
        assert realloc["payload"]["from_phase"] == "scan"

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/budget", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/events
# ---------------------------------------------------------------------------


class TestGetEvents:
    @requires_docker
    def test_returns_run_started_event_by_default(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = data["run_id"]

        resp = c.get(f"/api/runs/{run_id}/events", headers=AUTH)
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) >= 1
        assert events[0]["type"] == "run_started"

    @requires_docker
    def test_after_seq_filter(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = data["run_id"]

        # 获取初始事件的 seq
        events = c.get(f"/api/runs/{run_id}/events", headers=AUTH).json()["events"]
        first_seq = events[0]["seq"]

        # 用初始 seq 查询，应返回空
        resp = c.get(f"/api/runs/{run_id}/events", params={"after_seq": first_seq}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["events"] == []

        # 暂停运行产生新事件
        c.post(f"/api/runs/{run_id}/pause", headers=AUTH)
        resp = c.get(f"/api/runs/{run_id}/events", params={"after_seq": first_seq}, headers=AUTH)
        assert resp.status_code == 200
        new_events = resp.json()["events"]
        assert len(new_events) >= 1
        assert new_events[0]["type"] == "state_changed"
        assert new_events[0]["seq"] > first_seq

    @requires_docker
    def test_limit_parameter(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        # 写入多条事件
        for i in range(5):
            emit_event(pg_session, run_id, EventType.WARNING, {"msg": f"warn-{i}"})
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/events", params={"limit": 2}, headers=AUTH)
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 2

    @requires_docker
    def test_default_limit_is_500(self, client, pg_session):
        c, _ = client
        data = _create_task(c)

        # 无 limit 参数时应返回 ≤500 条
        resp = c.get(f"/api/runs/{data['run_id']}/events", headers=AUTH)
        assert resp.status_code == 200
        # 至少有一条 event（run_started）
        assert len(resp.json()["events"]) >= 1

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/events", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/report
# ---------------------------------------------------------------------------


class TestGetReport:
    @requires_docker
    def test_returns_report_dict(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        report = FinalReport(
            run_id=run_id,
            status="completed",
            acceptance_result={"passed": True},
            files_changed={"modified": ["app/main.py"]},
            totals={"tokens": 3200, "cost": 0.03, "calls": 4, "time": 120},
            report_md="# Final Report\nAll good!",
        )
        pg_session.add(report)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/report", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["run_id"], str)
        assert body["status"] == "completed"
        assert body["acceptance_result"] == {"passed": True}
        assert body["files_changed"] == {"modified": ["app/main.py"]}
        assert body["totals"]["tokens"] == 3200
        assert body["report_md"] == "# Final Report\nAll good!"

    @requires_docker
    def test_report_not_found_returns_404(self, client, pg_session):
        c, _ = client
        data = _create_task(c)

        resp = c.get(f"/api/runs/{data['run_id']}/report", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "report not found"

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/report", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"


# ---------------------------------------------------------------------------
# integration: GET /runs/{run_id}/report/export
# ---------------------------------------------------------------------------


class TestExportReport:
    @requires_docker
    def test_json_format(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        report = FinalReport(
            run_id=run_id,
            status="completed",
            acceptance_result={"passed": True},
            totals={"tokens": 1000},
            report_md="# Report",
        )
        pg_session.add(report)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/report/export", params={"format": "json"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert f'report-{data["run_id"]}.json' in resp.headers["content-disposition"]

        import json

        body = json.loads(resp.content)
        assert body["status"] == "completed"
        assert body["totals"]["tokens"] == 1000

    @requires_docker
    def test_md_format(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        report = FinalReport(
            run_id=run_id,
            status="completed",
            acceptance_result={},
            totals={},
            report_md="# Final Report\n\n## Summary\n\nAll done.",
        )
        pg_session.add(report)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/report/export", params={"format": "md"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.headers["content-type"].split(";", 1)[0] == "text/markdown"
        assert f'report-{data["run_id"]}.md' in resp.headers["content-disposition"]
        assert "# Final Report" in resp.text

    @requires_docker
    def test_md_format_empty_report_md(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        report = FinalReport(
            run_id=run_id,
            status="completed",
            acceptance_result={},
            totals={},
            report_md=None,  # NULL report_md
        )
        pg_session.add(report)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/report/export", params={"format": "md"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.content == b""

    @requires_docker
    def test_default_format_is_json(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        report = FinalReport(run_id=run_id, status="completed", totals={"tokens": 500})
        pg_session.add(report)
        pg_session.commit()

        # 不传 format 参数，应默认 json
        resp = c.get(f"/api/runs/{data['run_id']}/report/export", headers=AUTH)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"

    @requires_docker
    def test_report_not_found_returns_404(self, client, pg_session):
        c, _ = client
        data = _create_task(c)

        resp = c.get(f"/api/runs/{data['run_id']}/report/export", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "report not found"

    @requires_docker
    def test_run_not_found_returns_404(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/runs/{fake_id}/report/export", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "run not found"

    @requires_docker
    def test_invalid_format_returns_422(self, client, pg_session):
        c, _ = client
        data = _create_task(c)
        run_id = uuid.UUID(data["run_id"])

        # 先创建一个 report，确保 run 存在
        report = FinalReport(run_id=run_id, status="completed", totals={})
        pg_session.add(report)
        pg_session.commit()

        resp = c.get(f"/api/runs/{data['run_id']}/report/export", params={"format": "xml"}, headers=AUTH)
        assert resp.status_code == 422
