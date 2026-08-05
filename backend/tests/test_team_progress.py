"""Team progress observability tests — aggregate counts, per-session detail,
percentage logic, missing signal fallback, and no-LLM-call verification.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from app.api.team_observatory import (  # noqa: E402
    _build_session_progress,
    _parse_progress_percentage,
    _resolve_display_status,
)
from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.enums import RunStatus  # noqa: E402
from app.core.models import (  # noqa: E402
    ExecutionEvent,
    SessionProgressSignal,
    Task,
    TaskBudget,
    TaskPhase,
    TaskRun,
    WorkContainer,
    WorkSession,
    utcnow,
)
from app.main import app  # noqa: E402
from app.worker import broker  # noqa: E402
from tests.conftest import requires_docker  # noqa: E402

AUTH = {"Authorization": f"Bearer {settings.api_token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_container(db: Session, **overrides) -> WorkContainer:
    """Create a minimal WorkContainer in the database."""
    defaults = {
        "name": "测试团队容器",
        "project_goal": "验证团队进度聚合",
        "shared_context": "测试共享上下文",
        "base_workdir": "/workspace/test",
        "default_workspace_policy": "isolated",
    }
    defaults.update(overrides)
    container = WorkContainer(**defaults)
    db.add(container)
    db.flush()
    return container


def _make_session(
    db: Session,
    container: WorkContainer,
    role: str = "测试角色",
    status: str = "PENDING",
    current_phase: str | None = None,
    iteration: int = 0,
) -> tuple[WorkSession, TaskRun]:
    """Create a Task + TaskRun + TaskBudget + TaskPhases + WorkSession in one go."""
    task = Task(
        name=f"{container.name} · {role}",
        description=f"测试任务: {role}",
        workdir=container.base_workdir,
        template="small_feature",
    )
    db.add(task)
    db.flush()

    now = utcnow()
    run = TaskRun(
        task_id=task.id,
        attempt_no=1,
        strategy="dynamic",
        status=status,
        current_phase=current_phase,
        iteration=iteration,
        started_at=now if status in (
            "PLANNING", "EXECUTING", "OBSERVING", "EVALUATING", "REPLANNING"
        ) else None,
    )
    db.add(run)
    db.flush()

    budget = TaskBudget(run_id=run.id)
    db.add(budget)

    for phase_name in ("scan", "analyze", "modify", "verify", "repair", "summarize"):
        db.add(TaskPhase(run_id=run.id, phase=phase_name))

    session_item = WorkSession(
        container_id=container.id,
        role=role,
        goal=f"达成目标: {role}",
        task_id=task.id,
        current_run_id=run.id,
        status=status,
    )
    db.add(session_item)
    db.flush()
    return session_item, run


def _add_progress_signal(
    db: Session,
    session_item: WorkSession,
    run: TaskRun,
    *,
    milestone: str | None = None,
    summary: str | None = None,
    completed_items: list | dict | None = None,
    next_step: str | None = None,
    blocked: bool = False,
    blocker_reason: str | None = None,
    needs_operator: bool = False,
    evidence: str | None = None,
    iteration: int = 0,
    created_at: datetime | None = None,
) -> SessionProgressSignal:
    """Insert a progress signal record."""
    signal = SessionProgressSignal(
        session_id=session_item.id,
        run_id=run.id,
        summary=summary,
        milestone=milestone,
        completed_items=completed_items or [],
        next_step=next_step,
        blocked=blocked,
        blocker_reason=blocker_reason,
        needs_operator=needs_operator,
        evidence=evidence,
        iteration=iteration,
        created_at=created_at or utcnow(),
    )
    db.add(signal)
    db.flush()
    return signal


def _add_agent_message(
    db: Session,
    run: TaskRun,
    text: str,
    iteration: int = 0,
    created_at: datetime | None = None,
) -> ExecutionEvent:
    """Insert an agent_message execution event."""
    event = ExecutionEvent(
        run_id=run.id,
        type="agent_message",
        payload={"text": text, "iteration": iteration},
        created_at=created_at or utcnow(),
    )
    db.add(event)
    db.flush()
    return event


# ---------------------------------------------------------------------------
# Unit: _resolve_display_status
# ---------------------------------------------------------------------------


class TestResolveDisplayStatus:
    """Test display status resolution from RunStatus values."""

    def test_running_statuses(self):
        """PLANNING/EXECUTING/OBSERVING/EVALUATING/REPLANNING → running."""
        for raw in ("PLANNING", "EXECUTING", "OBSERVING", "EVALUATING", "REPLANNING"):
            ws = WorkSession(role="test", goal="test")
            ws.current_run = TaskRun(status=raw, model_config={})
            assert _resolve_display_status(ws) == "running", f"{raw} should be running"

    def test_paused(self):
        ws = WorkSession(role="test", goal="test")
        ws.current_run = TaskRun(status="PAUSED", model_config={})
        assert _resolve_display_status(ws) == "paused"

    def test_waiting_statuses(self):
        for raw in ("PENDING", "WAITING_APPROVAL"):
            ws = WorkSession(role="test", goal="test")
            ws.current_run = TaskRun(status=raw, model_config={})
            assert _resolve_display_status(ws) == "waiting", f"{raw} should be waiting"

    def test_completed_statuses(self):
        for raw in ("COMPLETED", "PARTIAL_COMPLETED"):
            ws = WorkSession(role="test", goal="test")
            ws.current_run = TaskRun(status=raw, model_config={})
            assert _resolve_display_status(ws) == "completed", f"{raw} should be completed"

    def test_blocked_statuses(self):
        for raw in ("FAILED", "BUDGET_EXHAUSTED"):
            ws = WorkSession(role="test", goal="test")
            ws.current_run = TaskRun(status=raw, model_config={})
            assert _resolve_display_status(ws) == "blocked", f"{raw} should be blocked"

    def test_cancelled(self):
        ws = WorkSession(role="test", goal="test")
        ws.current_run = TaskRun(status="CANCELLED", model_config={})
        assert _resolve_display_status(ws) == "cancelled"

    def test_no_run_defaults_to_waiting(self):
        ws = WorkSession(role="test", goal="test")
        ws.current_run = None
        assert _resolve_display_status(ws) == "waiting"


# ---------------------------------------------------------------------------
# Unit: _parse_progress_percentage
# ---------------------------------------------------------------------------


class TestParseProgressPercentage:
    """Test percentage extraction from progress signals."""

    def test_null_signal_returns_none(self):
        result = _parse_progress_percentage(None)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_null_completed_items_returns_none(self):
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=None,
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_empty_list_returns_none(self):
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=[],
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_list_with_milestone_x_y_pattern(self):
        """completed_items=['a','b','c'] + milestone='3/5 功能完成' → 60%."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=["item1", "item2", "item3"],
            milestone="3/5 功能完成",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 3
        assert result["total"] == 5
        assert result["percentage"] == 60

    def test_list_without_total_returns_no_percentage(self):
        """Items but no total → no percentage, just count."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=["a", "b"],
            milestone="完成两个任务",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 2
        assert result["total"] is None
        assert result["percentage"] is None

    def test_dict_with_items_and_total(self):
        """completed_items = {items: ['x','y'], total: 4} → 50%."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items={"items": ["x", "y"], "total": 4},
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 2
        assert result["total"] == 4
        assert result["percentage"] == 50

    def test_dict_with_completed_items_and_total_items(self):
        """Alternative key names: completed_items + total_items."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items={"completed_items": ["a", "b", "c", "d"], "total_items": 8},
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 4
        assert result["total"] == 8
        assert result["percentage"] == 50

    def test_dict_items_empty_returns_none(self):
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items={"items": [], "total": 5},
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_dict_without_total_uses_milestone_fallback(self):
        """Dict items without total, but milestone has '2/6' → parse total."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items={"items": ["a", "b"]},
            milestone="进度: 2/6 项完成",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 2
        assert result["total"] == 6
        assert result["percentage"] == 33

    def test_x_y_pattern_with_spaces(self):
        """Milestone '完成  4 /  8' still parses correctly."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=["a", "b", "c", "d"],
            milestone="完成  4 /  8",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 4
        assert result["total"] == 8
        assert result["percentage"] == 50

    def test_zero_total_does_not_compute_percentage(self):
        """If parsed total is 0, skip percentage."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=["a"],
            milestone="1/0",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result["completed"] == 1
        assert result["total"] == 0
        assert result["percentage"] is None

    def test_non_list_non_dict_completed_items(self):
        """Non-array/non-dict completed_items returns none."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items="not a list",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_heartbeat_like_empty_items_no_percentage(self):
        """Heartbeat-like signal: empty completed_items list → no percentage."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=[],
            milestone="heartbeat — still alive",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}, (
            f"Empty completed_items must not yield percentage: {result}"
        )

    def test_heartbeat_like_null_items_no_percentage(self):
        """Heartbeat-like signal: None completed_items → no percentage."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=None,
            milestone="phase_changed: scan → analyze",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}

    def test_items_without_known_total_no_percentage(self):
        """Completed items exist but total is unknown → count only, no percentage."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items=["task-a", "task-b", "task-c"],
            milestone="进度更新 — 持续工作中",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        # completed count is known but total is not → no percentage
        assert result["completed"] == 3
        assert result["total"] is None
        assert result["percentage"] is None, (
            f"Percentage must be None when total is unknown: {result}"
        )

    def test_dict_items_empty_no_percentage(self):
        """Dict-style completed_items with empty list → no percentage."""
        signal = SessionProgressSignal(
            session_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            completed_items={"items": [], "total": 10},
            milestone="heartbeat",
            iteration=0,
        )
        result = _parse_progress_percentage(signal)
        assert result == {"completed": None, "total": None, "percentage": None}


# ---------------------------------------------------------------------------
# Integration: client fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(pg_session, monkeypatch):
    """TestClient fixture — redirects get_db to pg_session, mocks broker."""

    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    enqueued: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: enqueued.append(run_id))
    with TestClient(app) as c:
        yield c, enqueued
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Integration: GET /api/work-containers/{id}/progress
# ---------------------------------------------------------------------------


class TestTeamProgressEndpoint:
    """Integration tests for the team progress observability endpoint."""

    @requires_docker
    def test_404_for_unknown_container(self, client, pg_session):
        c, _ = client
        fake_id = uuid.uuid4()
        resp = c.get(f"/api/work-containers/{fake_id}/progress", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "work container not found"

    @requires_docker
    def test_401_without_auth(self, client, pg_session):
        c, _ = client
        container = _make_container(pg_session)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress")
        assert resp.status_code == 401

    @requires_docker
    def test_empty_container_returns_zero_counts(self, client, pg_session):
        c, _ = client
        container = _make_container(pg_session)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()

        assert body["container_id"] == str(container.id)
        summary = body["team_summary"]
        assert summary == {
            "running": 0,
            "waiting": 0,
            "paused": 0,
            "blocked": 0,
            "completed": 0,
            "total": 0,
            "active_stage": None,
        }
        assert body["sessions"] == []
        assert body["recent_milestones"] == []
        assert body["next_focus"] == []

    @requires_docker
    def test_team_aggregate_counts(self, client, pg_session):
        """Verify running/waiting/paused/blocked/completed are counted correctly."""
        c, _ = client
        container = _make_container(pg_session)

        # 2 running, 1 waiting, 1 paused, 1 blocked, 1 completed
        _make_session(pg_session, container, role="后端实现", status="EXECUTING", current_phase="modify")
        _make_session(pg_session, container, role="前端开发", status="PLANNING", current_phase="scan")
        _make_session(pg_session, container, role="测试编写", status="PENDING")
        _make_session(pg_session, container, role="代码审查", status="PAUSED")
        _make_session(pg_session, container, role="失败任务", status="FAILED")
        _make_session(pg_session, container, role="已完成", status="COMPLETED")
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        summary = resp.json()["team_summary"]

        assert summary["running"] == 2
        assert summary["waiting"] == 1
        assert summary["paused"] == 1
        assert summary["blocked"] == 1
        assert summary["completed"] == 1
        assert summary["total"] == 6
        # Most common phase among running: modify (1), scan (1) — both 1, first wins
        assert summary["active_stage"] in ("modify", "scan")

    @requires_docker
    def test_active_stage_most_common_phase(self, client, pg_session):
        """Active stage = most frequent phase among running sessions."""
        c, _ = client
        container = _make_container(pg_session)

        _make_session(pg_session, container, role="A", status="EXECUTING", current_phase="modify")
        _make_session(pg_session, container, role="B", status="EXECUTING", current_phase="modify")
        _make_session(pg_session, container, role="C", status="EXECUTING", current_phase="verify")
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.json()["team_summary"]["active_stage"] == "modify"

    @requires_docker
    def test_per_session_detail(self, client, pg_session):
        """Verify per-session progress detail includes all required fields."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(
            pg_session, container, role="后端实现", status="EXECUTING",
            current_phase="modify", iteration=5,
        )

        signal = _add_progress_signal(
            pg_session, ws, run,
            milestone="数据模型完成",
            summary="完成ORM模型和迁移",
            completed_items=["models.py", "migration.sql", "tests"],
            next_step="实现API路由",
            blocked=False,
            needs_operator=False,
            evidence="models.py L392",
            iteration=3,
        )
        _add_agent_message(pg_session, run, text="正在修改 models.py", iteration=3)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) == 1

        sp = sessions[0]
        assert sp["session_id"] == str(ws.id)
        assert sp["role"] == "后端实现"
        assert sp["status"] == "running"
        assert sp["phase"] == "modify"
        assert sp["current_action"] == "正在修改 models.py"
        assert sp["last_activity"] is not None
        assert sp["milestone"] == "数据模型完成"
        assert sp["summary"] == "完成ORM模型和迁移"
        assert sp["next_step"] == "实现API路由"
        assert sp["blocked"] is False
        assert sp["blocker_reason"] is None
        assert sp["needs_operator"] is False
        assert sp["evidence"] == "models.py L392"
        assert sp["iteration"] == 3
        assert sp["progress"]["completed"] == 3

    @requires_docker
    def test_missing_signal_fallback(self, client, pg_session):
        """Sessions without progress signals → null/zero fallback (not error)."""
        c, _ = client
        container = _make_container(pg_session)
        _make_session(pg_session, container, role="无信号角色", status="EXECUTING", current_phase="scan")
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        sp = resp.json()["sessions"][0]

        # All progress fields should be None/False/0 when no signal exists
        assert sp["milestone"] is None
        assert sp["summary"] is None
        assert sp["next_step"] is None
        assert sp["blocked"] is False
        assert sp["blocker_reason"] is None
        assert sp["needs_operator"] is False
        assert sp["evidence"] is None
        assert sp["progress"] == {"completed": None, "total": None, "percentage": None}

    @requires_docker
    def test_blocked_session_flag(self, client, pg_session):
        """Blocked flag from progress signal is reflected correctly."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="阻塞任务", status="EXECUTING")
        _add_progress_signal(
            pg_session, ws, run,
            blocked=True,
            blocker_reason="等待后端API完成",
            next_step="待依赖就绪后继续",
        )
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["blocked"] is True
        assert sp["blocker_reason"] == "等待后端API完成"
        assert sp["next_step"] == "待依赖就绪后继续"

    @requires_docker
    def test_needs_operator_flag(self, client, pg_session):
        """Needs operator flag is surfaced."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="需操作员", status="EXECUTING")
        _add_progress_signal(pg_session, ws, run, needs_operator=True)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["needs_operator"] is True

    @requires_docker
    def test_recent_milestones_top_10(self, client, pg_session):
        """Recent milestones: up to 10 most recent across all sessions."""
        c, _ = client
        container = _make_container(pg_session)

        # Create 3 sessions with different milestones
        for i, (role, milestone) in enumerate([
            ("后端", "数据模型完成"),
            ("前端", "组件创建完成"),
            ("测试", "测试用例编写中"),
        ]):
            ws, run = _make_session(pg_session, container, role=role, status="EXECUTING")
            _add_progress_signal(
                pg_session, ws, run,
                milestone=milestone,
                created_at=datetime(2026, 8, 1, 10, i, 0, tzinfo=timezone.utc),
            )
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        milestones = resp.json()["recent_milestones"]
        assert len(milestones) == 3
        # Most recent first
        assert milestones[0]["milestone"] == "测试用例编写中"
        assert milestones[-1]["milestone"] == "数据模型完成"

    @requires_docker
    def test_next_focus_blocked_first(self, client, pg_session):
        """Next focus: blocked sessions listed before others."""
        c, _ = client
        container = _make_container(pg_session)

        # Blocked session
        ws1, run1 = _make_session(pg_session, container, role="阻塞任务", status="EXECUTING")
        _add_progress_signal(
            pg_session, ws1, run1,
            blocked=True, blocker_reason="等待依赖",
            next_step="等待后端API",
        )
        # Normal session
        ws2, run2 = _make_session(pg_session, container, role="正常运行", status="EXECUTING")
        _add_progress_signal(
            pg_session, ws2, run2,
            next_step="继续开发",
        )
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        next_focus = resp.json()["next_focus"]
        assert len(next_focus) >= 2
        # Blocked session should come first
        assert next_focus[0]["blocked"] is True
        assert next_focus[0]["role"] == "阻塞任务"

    @requires_docker
    def test_no_llm_calls_made(self, client, pg_session):
        """Verify the progress endpoint makes zero LLM calls — pure DB query."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="测试", status="EXECUTING")
        _add_progress_signal(pg_session, ws, run, milestone="测试里程碑")
        pg_session.commit()

        # Patch litellm at multiple possible import paths to ensure no LLM call
        with patch("app.api.team_observatory.utcnow", wraps=utcnow) as mock_utcnow:
            resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
            assert resp.status_code == 200

        # The endpoint should work without any LLM infrastructure
        body = resp.json()
        assert body["team_summary"]["total"] == 1
        assert len(body["recent_milestones"]) == 1

    @requires_docker
    def test_no_llm_call_import_or_reference(self, client, pg_session):
        """The team_observatory progress endpoint has no LLM API or SDK imports."""
        import inspect
        import app.api.team_observatory as to_mod

        source = inspect.getsource(to_mod).lower()
        # Only check for actual LLM API/SDK patterns, not model names like LlmCall
        llm_sdk_patterns = ["litellm", "openai.", "anthropic.", "chat.completions",
                            "langchain", "autogen"]
        for pattern in llm_sdk_patterns:
            assert pattern not in source, f"Found LLM SDK reference '{pattern}' in team_observatory"

    @requires_docker
    def test_percentage_with_x_y_milestone(self, client, pg_session):
        """Integration: percentage computed from completed_items + x/y milestone."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="进度任务", status="EXECUTING")
        _add_progress_signal(
            pg_session, ws, run,
            milestone="完成 3/5 项任务",
            completed_items=["任务A", "任务B", "任务C"],
        )
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["progress"]["completed"] == 3
        assert sp["progress"]["total"] == 5
        assert sp["progress"]["percentage"] == 60

    @requires_docker
    def test_percentage_dict_with_explicit_total(self, client, pg_session):
        """Integration: percentage from dict with items + total."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="字典进度", status="EXECUTING")
        _add_progress_signal(
            pg_session, ws, run,
            completed_items={"items": ["A", "B", "C", "D"], "total": 10},
        )
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["progress"]["completed"] == 4
        assert sp["progress"]["total"] == 10
        assert sp["progress"]["percentage"] == 40

    @requires_docker
    def test_latest_agent_message_is_most_recent(self, client, pg_session):
        """current_action should come from the most recent agent_message event."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="消息测试", status="EXECUTING")

        t1 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 8, 1, 10, 0, 5, tzinfo=timezone.utc)
        _add_agent_message(pg_session, run, text="旧消息", created_at=t1)
        _add_agent_message(pg_session, run, text="新消息", created_at=t2)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["current_action"] == "新消息"

    @requires_docker
    def test_last_activity_uses_most_recent_source(self, client, pg_session):
        """last_activity = max(updated_at, signal created_at, agent_msg created_at)."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="活动测试", status="EXECUTING")

        t_session = datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
        t_signal = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        t_msg = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)

        ws.updated_at = t_session
        _add_progress_signal(pg_session, ws, run, milestone="M", created_at=t_signal)
        _add_agent_message(pg_session, run, text="最新消息", created_at=t_msg)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        # Should be the agent message time (most recent)
        assert sp["last_activity"] == "2026-08-01T10:00:00+00:00"

    @requires_docker
    def test_iteration_from_signal_takes_precedence(self, client, pg_session):
        """iteration field prefers signal.iteration over run.iteration."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="迭代测试", status="EXECUTING", iteration=10)
        _add_progress_signal(pg_session, ws, run, iteration=7)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["iteration"] == 7

    @requires_docker
    def test_iteration_fallback_to_run(self, client, pg_session):
        """No signal → iteration falls back to run.iteration."""
        c, _ = client
        container = _make_container(pg_session)
        _make_session(pg_session, container, role="无信号", status="EXECUTING", iteration=42)
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        sp = resp.json()["sessions"][0]
        assert sp["iteration"] == 42

    @requires_docker
    def test_blocked_budget_exhausted_counted_as_blocked(self, client, pg_session):
        """BUDGET_EXHAUSTED run status → display status 'blocked'."""
        c, _ = client
        container = _make_container(pg_session)
        _make_session(pg_session, container, role="预算耗尽", status="BUDGET_EXHAUSTED")
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        summary = resp.json()["team_summary"]
        assert summary["blocked"] == 1
        assert summary["running"] == 0


    @requires_docker
    def test_tool_call_event_does_not_produce_progress(self, client, pg_session):
        """A tool_call ExecutionEvent alone does NOT produce a progress signal;
        only explicit [PROGRESS] declarations (SessionProgressSignal rows) count."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(
            pg_session, container, role="工具调用角色", status="EXECUTING",
            current_phase="modify", iteration=1,
        )

        # Add a tool_call event — NOT an agent_message
        tool_event = ExecutionEvent(
            run_id=run.id,
            type="tool_call",
            payload={"tool": "read_file", "args": {"path": "/src/main.py"}, "iteration": 1},
        )
        pg_session.add(tool_event)

        # No SessionProgressSignal is created — only the tool_call event exists
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        sp = resp.json()["sessions"][0]

        # tool_call event should NOT set current_action (only agent_message does)
        assert sp["current_action"] is None, (
            f"tool_call event must not leak into current_action: {sp['current_action']}"
        )

        # No progress signal → all progress fields are null/fallback
        assert sp["milestone"] is None
        assert sp["summary"] is None
        assert sp["progress"] == {"completed": None, "total": None, "percentage": None}, (
            f"tool_call event must not produce progress: {sp['progress']}"
        )

    @requires_docker
    def test_heartbeat_event_does_not_produce_progress(self, client, pg_session):
        """A heartbeat/phase_changed ExecutionEvent alone does NOT produce
        a progress signal."""
        c, _ = client
        container = _make_container(pg_session)
        ws, run = _make_session(
            pg_session, container, role="心跳角色", status="EXECUTING",
            current_phase="scan", iteration=2,
        )

        # Add a heartbeat event
        hb_event = ExecutionEvent(
            run_id=run.id,
            type="heartbeat",
            payload={"phase": "scan", "iteration": 2, "active_runtime_ms": 5000},
        )
        pg_session.add(hb_event)

        # Add a phase_changed event
        pc_event = ExecutionEvent(
            run_id=run.id,
            type="phase_changed",
            payload={"from": "scan", "to": "analyze", "iteration": 2},
        )
        pg_session.add(pc_event)

        # No SessionProgressSignal exists
        pg_session.commit()

        resp = c.get(f"/api/work-containers/{container.id}/progress", headers=AUTH)
        assert resp.status_code == 200
        sp = resp.json()["sessions"][0]

        # heartbeat/phase_changed events must not leak into current_action
        assert sp["current_action"] is None, (
            f"heartbeat/phase_changed must not leak: {sp['current_action']}"
        )

        # No progress signal → all null
        assert sp["milestone"] is None
        assert sp["summary"] is None
        assert sp["progress"] == {"completed": None, "total": None, "percentage": None}, (
            f"heartbeat/phase_changed must not produce progress: {sp['progress']}"
        )


# ---------------------------------------------------------------------------
# Unit: _build_session_progress with partial data
# ---------------------------------------------------------------------------


class TestBuildSessionProgress:
    """Unit tests for _build_session_progress edge cases."""

    def test_session_no_run_none(self):
        """Session with current_run=None (no run loaded) returns waiting status."""
        ws = WorkSession(role="test", goal="test")
        # No run assigned at all
        assert _resolve_display_status(ws) == "waiting"

    @requires_docker
    def test_build_progress_with_valid_run(self, pg_session):
        """_build_session_progress with a valid run returns correct fields."""
        container = _make_container(pg_session)
        ws, run = _make_session(pg_session, container, role="构建测试", status="EXECUTING",
                                 current_phase="modify", iteration=3)
        pg_session.commit()

        # Re-query to get eager-loaded relationships
        from sqlalchemy.orm import joinedload
        container2 = pg_session.execute(
            __import__("sqlalchemy").select(WorkContainer)
            .options(joinedload(WorkContainer.sessions).joinedload(WorkSession.current_run))
            .where(WorkContainer.id == container.id)
        ).unique().scalar_one()

        sp = _build_session_progress(container2.sessions[0], pg_session)
        assert sp["status"] == "running"
        assert sp["role"] == "构建测试"
        assert sp["phase"] == "modify"
        assert sp["iteration"] == 3

    @requires_docker
    def test_status_counts_exclude_cancelled_from_blocked(self, pg_session):
        """CANCELLED is not counted as blocked."""
        container = _make_container(pg_session)
        _make_session(pg_session, container, role="已取消", status="CANCELLED")
        pg_session.commit()

        # Re-query to get sessions with current_run loaded
        from sqlalchemy.orm import joinedload
        container2 = pg_session.execute(
            __import__("sqlalchemy").select(WorkContainer)
            .options(joinedload(WorkContainer.sessions).joinedload(WorkSession.current_run))
            .where(WorkContainer.id == container.id)
        ).unique().scalar_one()

        sp = _build_session_progress(container2.sessions[0], pg_session)
        assert sp["status"] == "cancelled"
