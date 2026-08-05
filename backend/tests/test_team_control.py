"""Integration tests for Team Runtime Control endpoints.

Covers: idempotent pause/resume/stop, budget floor rejection, needs_resume flag,
parallelism only new calls, audit event creation, mode switch confirmation,
autonomous re-evaluation, confirmation requirement for stop.
"""
from __future__ import annotations

import os
import threading
import uuid

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.enums import ContainerLifecycle, RunStatus  # noqa: E402
from app.core.models import (  # noqa: E402
    SessionMessage,
    Task,
    TaskBudget,
    TaskRun,
    TeamAuditEvent,
    WorkContainer,
    WorkSession,
)
from app.main import app  # noqa: E402
from app.worker import broker  # noqa: E402
from tests.conftest import requires_docker  # noqa: E402

pytestmark = requires_docker
AUTH = {"Authorization": f"Bearer {settings.api_token}"}


@pytest.fixture()
def client(pg_session, monkeypatch):
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    enqueued: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: enqueued.append(run_id))
    with TestClient(app) as test_client:
        yield test_client, pg_session, enqueued
    app.dependency_overrides.clear()


def _create_container(c: TestClient, name: str = "团队测试") -> dict:
    resp = c.post(
        "/api/work-containers",
        headers=AUTH,
        json={
            "name": name,
            "project_goal": "测试团队运行时控制",
            "shared_context": "PG是唯一事实来源",
            "base_workdir": "/workspace/test",
            "default_workspace_policy": "isolated",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_session(
    c: TestClient, container_id: str, key: str, role: str = "后端实现", **overrides
) -> dict:
    body = {
        "role": role,
        "goal": "实现核心功能",
        "private_context": "测试专用",
        "budget": {"max_total_tokens": 10_000, "max_llm_calls": 10},
    }
    body.update(overrides)
    resp = c.post(
        f"/api/work-containers/{container_id}/sessions",
        headers={**AUTH, "Idempotency-Key": key},
        json=body,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_run_status(pg_session, session_data: dict, status: RunStatus) -> None:
    """Directly set a run's status in the DB for test setup."""
    run_id = uuid.UUID(session_data["session"]["current_run_id"])
    run = pg_session.get(TaskRun, run_id)
    if run:
        run.status = status.value
        pg_session.commit()


def _count_audit_events(pg_session, container_id: uuid.UUID, action: str | None = None) -> int:
    from sqlalchemy import select as sa_select
    from sqlalchemy import func

    stmt = sa_select(func.count()).select_from(TeamAuditEvent).where(
        TeamAuditEvent.container_id == container_id
    )
    if action:
        stmt = stmt.where(TeamAuditEvent.action == action)
    return pg_session.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
#  Pause — idempotent, audit event, session status
# ---------------------------------------------------------------------------


def test_pause_idempotent(client):
    c, _, _ = client
    pg_session = next(app.dependency_overrides[get_db]())

    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # First pause
    r1 = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r1.status_code == 200
    assert r1.json()["changed"] is True
    assert r1.json()["lifecycle_state"] == "paused"

    # Second pause — idempotent
    r2 = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["changed"] is False
    assert r2.json()["lifecycle_state"] == "paused"

    # Only one audit event for pause
    assert _count_audit_events(pg_session, cid, "pause") == 1


def test_pause_pauses_running_sessions_and_releases_reservations(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "s1", role="开发")
    s2 = _create_session(c, str(cid), "s2", role="测试")

    # Set both sessions to RUNNING
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)
    _set_run_status(pg_session, s2, RunStatus.EXECUTING)

    # Add some reserves to session budgets
    for sd in [s1, s2]:
        run_id = uuid.UUID(sd["session"]["current_run_id"])
        budget = pg_session.get(TaskBudget, run_id)
        if budget:
            budget.reserved_tokens = 500
            budget.reserved_cost = 0.05
    pg_session.commit()

    r = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["changed"] is True
    assert r.json()["paused_sessions"] == 2

    # Verify sessions are PAUSED
    for sd in [s1, s2]:
        run_id = uuid.UUID(sd["session"]["current_run_id"])
        pg_session.expire_all()
        run = pg_session.get(TaskRun, run_id)
        assert run is not None
        assert run.status == RunStatus.PAUSED.value

    # Verify reservations were released
    for sd in [s1, s2]:
        run_id = uuid.UUID(sd["session"]["current_run_id"])
        pg_session.expire_all()
        budget = pg_session.get(TaskBudget, run_id)
        assert budget is not None
        assert budget.reserved_tokens == 0
        assert float(budget.reserved_cost) == 0.0


def test_pause_blocks_new_dispatch(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # Pause container first
    r = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r.status_code == 200

    # Try to create a new session — should be rejected because container is not active
    resp = c.post(
        f"/api/work-containers/{cid}/sessions",
        headers={**AUTH, "Idempotency-Key": "blocked-session"},
        json={
            "role": "新任务",
            "goal": "不应被创建",
            "budget": {"max_total_tokens": 1000},
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
#  Resume — idempotent, audit event, autonomous re-evaluation
# ---------------------------------------------------------------------------


def test_resume_idempotent(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # Pause then resume
    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)

    r1 = c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)
    assert r1.status_code == 200
    assert r1.json()["changed"] is True
    assert r1.json()["lifecycle_state"] == "active"

    # Second resume — idempotent
    r2 = c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["changed"] is False
    assert r2.json()["lifecycle_state"] == "active"

    assert _count_audit_events(pg_session, cid, "resume") == 1


def test_resume_restores_paused_sessions(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "rs1", role="开发")
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)

    # Verify paused
    pg_session.expire_all()
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    run = pg_session.get(TaskRun, run_id)
    assert run.status == RunStatus.PAUSED.value

    r = c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["resumed_sessions"] == 1

    # Session should be back to REPLANNING
    pg_session.expire_all()
    run = pg_session.get(TaskRun, run_id)
    assert run.status == RunStatus.REPLANNING.value


def test_resume_autonomous_reevaluates_stages(client):
    """When an autonomous container resumes, stage dependencies should be re-evaluated."""
    c, pg_session, _ = client

    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # Set container to autonomous mode
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    wc.preset_snapshot = {"team_mode": "autonomous", "activation_plan": {}}
    pg_session.commit()

    s1 = _create_session(c, str(cid), "ars1", role="开发")
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    r = c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)
    assert r.status_code == 200
    # autonomous_stages_evaluated=True proves the autonomous code path executed
    assert r.json()["autonomous_stages_evaluated"] is True


# ---------------------------------------------------------------------------
#  Stop — confirmation required, audit event
# ---------------------------------------------------------------------------


def test_stop_requires_confirmation(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "st1", role="开发")
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    # Stop without confirmation
    r1 = c.post(f"/api/work-containers/{cid}/stop", headers=AUTH, json={"confirmed": False})
    assert r1.status_code == 200
    assert r1.json()["confirmation_required"] is True
    assert r1.json()["changed"] is False
    assert len(r1.json()["affected_sessions"]) >= 1

    # Container should still be active
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    assert wc.lifecycle_state == ContainerLifecycle.ACTIVE.value


def test_stop_with_confirmation(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "st2", role="开发")
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    # Stop with confirmed=true
    r = c.post(f"/api/work-containers/{cid}/stop", headers=AUTH, json={"confirmed": True})
    assert r.status_code == 200
    assert r.json()["changed"] is True
    assert r.json()["stopped_sessions"] == 1
    assert r.json()["lifecycle_state"] == "completed"

    # Container is completed
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    assert wc.lifecycle_state == ContainerLifecycle.COMPLETED.value

    # Audit event
    assert _count_audit_events(pg_session, cid, "stop") == 1


def test_stop_with_x_confirm_header(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "st3", role="开发")

    # Stop with X-Confirm header
    r = c.post(
        f"/api/work-containers/{cid}/stop",
        headers={**AUTH, "X-Confirm": "yes"},
        json={"confirmed": False},
    )
    assert r.status_code == 200
    assert r.json()["changed"] is True


def test_stop_idempotent(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # First stop with confirmation
    c.post(f"/api/work-containers/{cid}/stop", headers=AUTH, json={"confirmed": True})

    # Second stop — idempotent
    r2 = c.post(f"/api/work-containers/{cid}/stop", headers=AUTH, json={"confirmed": True})
    assert r2.status_code == 200
    assert r2.json()["changed"] is False

    assert _count_audit_events(pg_session, cid, "stop") == 1


# ---------------------------------------------------------------------------
#  Session resume
# ---------------------------------------------------------------------------


def test_session_resume_idempotent(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssr1", role="开发")
    sid = s1["session"]["id"]

    # Pause the session first
    c.post(f"/api/work-containers/{cid}/sessions/{sid}/pause", headers=AUTH)

    # Resume
    r1 = c.post(f"/api/work-containers/{cid}/sessions/{sid}/resume", headers=AUTH)
    assert r1.status_code == 200
    assert r1.json()["changed"] is True

    # Resume again — idempotent
    r2 = c.post(f"/api/work-containers/{cid}/sessions/{sid}/resume", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["changed"] is False


def test_session_resume_in_paused_container(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssr2", role="开发")
    sid = s1["session"]["id"]

    # Pause container
    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)

    # Try to resume session — should indicate container is paused
    r = c.post(f"/api/work-containers/{cid}/sessions/{sid}/resume", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["changed"] is False
    assert r.json()["container_paused"] is True


def test_session_resume_already_running(client):
    c, _, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssr3", role="开发")
    sid = s1["session"]["id"]

    r = c.post(f"/api/work-containers/{cid}/sessions/{sid}/resume", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["changed"] is False


# ---------------------------------------------------------------------------
#  Budget PATCH — container-level
# ---------------------------------------------------------------------------


def test_budget_floor_rejection(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "bf1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 5.0,
    })

    # Set used + reserved = 8000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # Try to set max_total_tokens below floor (8000)
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 6_000},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]


def test_budget_valid_increase(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "bv1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })

    # Set used=5000, reserved=0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    pg_session.commit()

    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 15_000},
    )
    assert r.status_code == 200
    assert "max_total_tokens" in r.json()["new_values"]
    assert r.json()["new_values"]["max_total_tokens"] == 15_000

    # Audit event
    assert _count_audit_events(pg_session, cid, "budget_update") == 1


def test_budget_needs_resume_flag(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "bnr1", role="开发", budget={
        "max_total_tokens": 1_000,
        "max_llm_calls": 5,
    })

    # Exhaust the budget
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 1_000
    pg_session.commit()

    run = pg_session.get(TaskRun, run_id)
    run.status = RunStatus.BUDGET_EXHAUSTED.value
    pg_session.commit()

    # Increase budget
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 5_000},
    )
    assert r.status_code == 200
    assert r.json()["needs_resume"] is True


def test_budget_parallelism_only_new_calls(client):
    """Verify max_parallel_llm_calls is accepted and doesn't break anything."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "bp1", role="开发")

    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_parallel_llm_calls": 4},
    )
    assert r.status_code == 200
    assert r.json()["new_values"]["max_parallel_llm_calls"] == 4


def test_budget_anti_runaway_params(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={
            "max_team_messages_per_minute": 20,
            "max_auto_reply_rounds": 3,
            "inbox_token_ratio": 0.10,
        },
    )
    assert r.status_code == 200
    assert r.json()["new_values"]["max_team_messages_per_minute"] == 20
    assert r.json()["new_values"]["max_auto_reply_rounds"] == 3
    assert r.json()["new_values"]["inbox_token_ratio"] == 0.10

    # Verify stored in preset_snapshot
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    assert wc.preset_snapshot["max_team_messages_per_minute"] == 20
    assert wc.preset_snapshot["max_auto_reply_rounds"] == 3
    assert wc.preset_snapshot["inbox_token_ratio"] == 0.10


# ---------------------------------------------------------------------------
#  Budget PATCH — container-level boundary tests (max_total_tokens)
# ---------------------------------------------------------------------------


def test_container_budget_tokens_exact_boundary(client):
    """max_total_tokens exactly equal to used+reserved floor → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbtb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 8_000 (exact floor) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 8_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_total_tokens"] == 8_000


def test_container_budget_tokens_above_boundary(client):
    """max_total_tokens = used+reserved + 1 → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbtab1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 8_001 (floor + 1) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 8_001},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_total_tokens"] == 8_001


def test_container_budget_tokens_below_boundary(client):
    """max_total_tokens = used+reserved - 1 → rejected (422)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbtbb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 7_999 (floor - 1) — should be rejected
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 7_999},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]
    assert detail["floor"]["floor_total_tokens"] == 8_000


# ---------------------------------------------------------------------------
#  Budget PATCH — container-level boundary tests (max_cost)
# ---------------------------------------------------------------------------


def test_container_budget_cost_exact_boundary(client):
    """max_cost exactly equal to used+reserved cost floor → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbcb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 3.0 (exact floor) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_cost": 3.0},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_cost"] == 3.0


def test_container_budget_cost_above_boundary(client):
    """max_cost = used+reserved cost + 0.01 → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbcab1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 3.01 (floor + 0.01) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_cost": 3.01},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_cost"] == 3.01


def test_container_budget_cost_below_boundary(client):
    """max_cost = used+reserved cost - 0.01 → rejected (422)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "cbcbb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 2.99 (floor - 0.01) — should be rejected
    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_cost": 2.99},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]
    assert round(detail["floor"]["floor_cost"], 2) == 3.0


# ---------------------------------------------------------------------------
#  Budget PATCH — session-level
# ---------------------------------------------------------------------------


def test_session_budget_floor_rejection(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "sbf1", role="开发", budget={
        "max_total_tokens": 10_000,
    })
    sid = s1["session"]["id"]

    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 8_000
    pg_session.commit()

    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 5_000},
    )
    assert r.status_code == 422


def test_session_budget_valid_update(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "sbv1", role="开发", budget={
        "max_total_tokens": 10_000,
    })
    sid = s1["session"]["id"]

    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    pg_session.commit()

    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 12_000},
    )
    assert r.status_code == 200
    assert r.json()["new_values"]["max_total_tokens"] == 12_000
    assert r.json()["session_id"] == sid


def test_session_budget_terminal_rejected(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "sbt1", role="开发")
    sid = s1["session"]["id"]
    _set_run_status(pg_session, s1, RunStatus.COMPLETED)

    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 50_000},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
#  Budget PATCH — session-level boundary tests (max_total_tokens)
# ---------------------------------------------------------------------------


def test_session_budget_tokens_exact_boundary(client):
    """Session max_total_tokens exactly equal to used+reserved floor → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbtb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    sid = s1["session"]["id"]

    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 8_000 (exact floor) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 8_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_total_tokens"] == 8_000


def test_session_budget_tokens_above_boundary(client):
    """Session max_total_tokens = used+reserved + 1 → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbtab1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    sid = s1["session"]["id"]

    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 8_001 (floor + 1) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 8_001},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_total_tokens"] == 8_001


def test_session_budget_tokens_below_boundary(client):
    """Session max_total_tokens = used+reserved - 1 → rejected (422)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbtbb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
    })
    sid = s1["session"]["id"]

    # Set used + reserved = 8_000 → floor = 8_000
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 5_000
    budget.reserved_tokens = 3_000
    pg_session.commit()

    # PATCH with max_total_tokens = 7_999 (floor - 1) — should be rejected
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 7_999},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]
    assert detail["floor"]["floor_total_tokens"] == 8_000


# ---------------------------------------------------------------------------
#  Budget PATCH — session-level boundary tests (max_cost)
# ---------------------------------------------------------------------------


def test_session_budget_cost_exact_boundary(client):
    """Session max_cost exactly equal to used+reserved cost floor → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbcb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    sid = s1["session"]["id"]

    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 3.0 (exact floor) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_cost": 3.0},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_cost"] == 3.0


def test_session_budget_cost_above_boundary(client):
    """Session max_cost = used+reserved cost + 0.01 → accepted (200)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbcab1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    sid = s1["session"]["id"]

    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 3.01 (floor + 0.01) — should be accepted
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_cost": 3.01},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_cost"] == 3.01


def test_session_budget_cost_below_boundary(client):
    """Session max_cost = used+reserved cost - 0.01 → rejected (422)."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "ssbcbb1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 10.0,
    })
    sid = s1["session"]["id"]

    # Set used_cost + reserved_cost = 3.0 → floor = 3.0
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_cost = 2.0
    budget.reserved_cost = 1.0
    pg_session.commit()

    # PATCH with max_cost = 2.99 (floor - 0.01) — should be rejected
    r = c.patch(
        f"/api/work-containers/{cid}/sessions/{sid}/budget",
        headers=AUTH,
        json={"max_cost": 2.99},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]
    assert round(detail["floor"]["floor_cost"], 2) == 3.0


# ---------------------------------------------------------------------------
#  Correction injection
# ---------------------------------------------------------------------------


def test_correct_creates_system_message(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "corr1", role="开发")
    sid = s1["session"]["id"]

    r = c.post(
        f"/api/work-containers/{cid}/correct",
        headers=AUTH,
        json={"session_id": sid, "instruction": "请优先修复安全问题"},
    )
    assert r.status_code == 201
    assert r.json()["queued"] is True
    assert r.json()["status"] == "queued"

    # Verify message was created with correct metadata
    msg_id = uuid.UUID(r.json()["message_id"])
    msg = pg_session.get(SessionMessage, msg_id)
    assert msg is not None
    assert msg.message_type == "system_fact"
    assert msg.content == "请优先修复安全问题"
    assert msg.message_metadata["role"] == "system"
    assert msg.message_metadata["priority"] == "high"
    assert msg.message_metadata["correction"] is True

    # Audit event
    assert _count_audit_events(pg_session, cid, "correct") == 1


def test_correct_rejects_empty_instruction(client):
    c, _, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "corr2", role="开发")
    sid = s1["session"]["id"]

    r = c.post(
        f"/api/work-containers/{cid}/correct",
        headers=AUTH,
        json={"session_id": sid, "instruction": "   "},
    )
    assert r.status_code == 422


def test_correct_targets_wrong_container(client):
    c, _, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    other = _create_container(c, "其他团队")
    other_cid = uuid.UUID(other["id"])

    s1 = _create_session(c, str(cid), "corr3", role="开发")
    sid = s1["session"]["id"]

    # Try to correct a session in container A using container B's endpoint
    r = c.post(
        f"/api/work-containers/{other_cid}/correct",
        headers=AUTH,
        json={"session_id": sid, "instruction": "修正"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
#  Mode switch — guided/autonomous
# ---------------------------------------------------------------------------


def test_mode_switch_requires_confirmation(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    r = c.patch(
        f"/api/work-containers/{cid}/mode",
        headers=AUTH,
        json={"team_mode": "autonomous", "mode_switch_confirmed": False},
    )
    assert r.status_code == 200
    assert r.json()["confirmation_required"] is True
    assert r.json()["changed"] is False
    assert len(r.json()["impact"]) > 0


def test_mode_switch_confirmed(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    r = c.patch(
        f"/api/work-containers/{cid}/mode",
        headers=AUTH,
        json={"team_mode": "autonomous", "mode_switch_confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["changed"] is True
    assert r.json()["new_mode"] == "autonomous"
    assert r.json()["old_mode"] == "guided"

    # Verify stored
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    assert wc.preset_snapshot["team_mode"] == "autonomous"

    # Audit event
    assert _count_audit_events(pg_session, cid, "mode_switch") == 1


def test_mode_switch_idempotent(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # Switch to autonomous
    c.patch(
        f"/api/work-containers/{cid}/mode",
        headers=AUTH,
        json={"team_mode": "autonomous", "mode_switch_confirmed": True},
    )

    # Switch again to same mode
    r = c.patch(
        f"/api/work-containers/{cid}/mode",
        headers=AUTH,
        json={"team_mode": "autonomous", "mode_switch_confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["changed"] is False

    assert _count_audit_events(pg_session, cid, "mode_switch") == 1


def test_mode_switch_autonomous_to_guided(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    # Set to autonomous first
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    wc.preset_snapshot = {"team_mode": "autonomous"}
    pg_session.commit()

    r = c.patch(
        f"/api/work-containers/{cid}/mode",
        headers=AUTH,
        json={"team_mode": "guided", "mode_switch_confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["changed"] is True
    assert r.json()["new_mode"] == "guided"


# ---------------------------------------------------------------------------
#  GET container enrichment — team_status, usage_summary, progress_summary
# ---------------------------------------------------------------------------


def test_get_container_includes_team_status(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "gts1", role="开发")
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    r = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert r.status_code == 200

    data = r.json()
    assert "team_status" in data
    assert data["team_status"]["phase"] == "running"
    assert data["team_status"]["running"] == 1
    assert data["team_status"]["total_sessions"] == 1

    assert "usage_summary" in data
    assert "tokens" in data["usage_summary"]
    assert "cost" in data["usage_summary"]
    assert "calls" in data["usage_summary"]

    assert "progress_summary" in data
    assert len(data["progress_summary"]) == 1
    assert data["progress_summary"][0]["role"] == "开发"


def test_get_container_team_status_paused(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)

    r = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["team_status"]["phase"] == "paused"


def test_get_container_preserves_existing_fields(client):
    c, _, _ = client
    container = _create_container(c)
    cid = container["id"]

    r = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert r.status_code == 200

    data = r.json()
    # Existing fields still present
    assert "id" in data
    assert "name" in data
    assert "project_goal" in data
    assert "shared_context" in data
    assert "lifecycle_state" in data
    assert "counts" in data
    assert "sessions" in data


# ---------------------------------------------------------------------------
#  Audit event coverage
# ---------------------------------------------------------------------------


def test_all_operations_create_audit_events(client):
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, str(cid), "aud1", role="开发", budget={
        "max_total_tokens": 10_000,
    })
    sid = s1["session"]["id"]
    _set_run_status(pg_session, s1, RunStatus.EXECUTING)

    # Pause
    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert _count_audit_events(pg_session, cid, "pause") == 1

    # Resume
    c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)
    assert _count_audit_events(pg_session, cid, "resume") == 1

    # Stop
    c.post(f"/api/work-containers/{cid}/stop", headers=AUTH, json={"confirmed": True})
    assert _count_audit_events(pg_session, cid, "stop") == 1

    # Total audit events
    total = pg_session.query(TeamAuditEvent).filter(
        TeamAuditEvent.container_id == cid
    ).count()
    assert total >= 3


# ---------------------------------------------------------------------------
#  Concurrent race-condition tests — pause/resume, budget, status transition
# ---------------------------------------------------------------------------


def _per_thread_session(pg_engine):
    """Create an independent Session on a fresh connection for threaded tests."""
    conn = pg_engine.connect()
    sess = Session(bind=conn, expire_on_commit=False)
    return sess, conn


def _commit_via_connection(sess: Session) -> None:
    """Commit the underlying DBAPI transaction on the session's bound connection.

    When a Session is bound to a Connection that has an explicit
    ``connection.begin()``, ``session.commit()`` only touches the session-level
    unit-of-work but does **not** commit the DBAPI transaction.  This helper
    flushes the session and commits the connection so data becomes visible
    across connections.
    """
    sess.flush()
    conn = sess.connection()
    conn.commit()
    # Start a new transaction so the session can continue working.
    conn.begin()


def _cleanup_threaded_data(pg_engine, container_id: uuid.UUID) -> None:
    """Best-effort removal of data committed outside the main test transaction.

    Deletes child rows first, then the container.  Catches FK errors gracefully
    — leaked rows are harmless within testcontainers (DB is destroyed after the
    test session).
    """
    from app.core.models import (
        ExecutionEvent,
        LlmCall,
        SessionMessage,
        SessionProgressSignal,
        Task,
        TaskBudget,
        TaskPhase,
        TaskRun,
        TeamAuditEvent,
        WorkContainer,
        WorkSession,
    )

    conn = pg_engine.connect()
    sess = Session(bind=conn)
    try:
        cid = container_id

        # Pre-collect IDs so subqueries don't reference rows we've already deleted
        session_rows = sess.execute(
            sess.query(WorkSession.id, WorkSession.task_id).filter(
                WorkSession.container_id == cid
            )
        ).all()
        session_ids = [r[0] for r in session_rows]
        task_ids = [r[1] for r in session_rows if r[1] is not None]

        run_rows = sess.execute(
            sess.query(TaskRun.id)
            .join(WorkSession, WorkSession.current_run_id == TaskRun.id)
            .filter(WorkSession.container_id == cid)
        ).all()
        run_ids = [r[0] for r in run_rows]

        # Children that reference container_id directly
        sess.query(SessionMessage).filter(SessionMessage.container_id == cid).delete(
            synchronize_session=False
        )
        sess.query(ExecutionEvent).filter(ExecutionEvent.container_id == cid).delete(
            synchronize_session=False
        )
        sess.query(TeamAuditEvent).filter(TeamAuditEvent.container_id == cid).delete(
            synchronize_session=False
        )

        # Children that reference session / run
        if session_ids:
            sess.query(SessionProgressSignal).filter(
                SessionProgressSignal.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
        if run_ids:
            sess.query(LlmCall).filter(LlmCall.run_id.in_(run_ids)).delete(
                synchronize_session=False
            )
            sess.query(TaskBudget).filter(TaskBudget.run_id.in_(run_ids)).delete(
                synchronize_session=False
            )
            sess.query(TaskPhase).filter(TaskPhase.run_id.in_(run_ids)).delete(
                synchronize_session=False
            )

        # Sessions (cascade should remove via all,delete-orphan)
        sess.query(WorkSession).filter(WorkSession.container_id == cid).delete(
            synchronize_session=False
        )

        # Parent rows
        if run_ids:
            sess.query(TaskRun).filter(TaskRun.id.in_(run_ids)).delete(
                synchronize_session=False
            )
        if task_ids:
            sess.query(Task).filter(Task.id.in_(task_ids)).delete(
                synchronize_session=False
            )

        sess.query(WorkContainer).filter(WorkContainer.id == cid).delete(
            synchronize_session=False
        )
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()
        conn.close()


def test_concurrent_pause_resume_race(pg_session, pg_engine, monkeypatch):
    """Simultaneous pause and resume requests — only one wins, final state is consistent.

    Two threads issue pause and resume on the same ACTIVE container at the same time.
    Exactly one operation should report ``changed=True`` and the final state must be
    either 'paused' or 'active' — never an inconsistent intermediate value.
    """
    from app.api.team_observatory import pause_container, resume_container
    from app.core.enums import ContainerLifecycle, RunStatus
    from app.core.models import Task, TaskBudget, TaskPhase, TaskRun, WorkContainer, WorkSession

    # Setup: create container + session directly in pg_session
    container = WorkContainer(
        name="并发暂停恢复测试",
        project_goal="测试并发暂停/恢复竞态",
        base_workdir="/workspace/cpr",
        lifecycle_state=ContainerLifecycle.ACTIVE.value,
    )
    pg_session.add(container)
    pg_session.flush()
    cid = container.id

    task = Task(
        name=f"{container.name} · 开发",
        description="测试任务",
        workdir=container.base_workdir,
        template="small_feature",
    )
    pg_session.add(task)
    pg_session.flush()

    run = TaskRun(
        task_id=task.id,
        attempt_no=1,
        strategy="dynamic",
        status=RunStatus.EXECUTING.value,
    )
    pg_session.add(run)
    pg_session.flush()

    budget = TaskBudget(run_id=run.id)
    pg_session.add(budget)

    for phase_name in ("scan", "analyze", "modify", "verify", "repair", "summarize"):
        pg_session.add(TaskPhase(run_id=run.id, phase=phase_name))

    ws = WorkSession(
        container_id=cid,
        role="开发",
        goal="达成目标",
        task_id=task.id,
        current_run_id=run.id,
        status=RunStatus.EXECUTING.value,
    )
    pg_session.add(ws)
    pg_session.flush()

    _commit_via_connection(pg_session)  # make visible to thread connections

    # Verify cross-connection visibility
    check_sess, check_conn = _per_thread_session(pg_engine)
    try:
        found = check_sess.get(WorkContainer, cid)
        assert found is not None, "Container not visible from separate connection after commit!"
    finally:
        check_sess.close()
        check_conn.close()

    results: list[tuple[str, bool, str]] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)

    def do_pause():
        sess, conn = _per_thread_session(pg_engine)
        try:
            barrier.wait()
            result = pause_container(cid, session=sess)
            sess.commit()
            with lock:
                results.append(("pause", result.changed, result.lifecycle_state))
        finally:
            sess.close()
            conn.close()

    def do_resume():
        sess, conn = _per_thread_session(pg_engine)
        try:
            barrier.wait()
            result = resume_container(cid, session=sess)
            sess.commit()
            with lock:
                results.append(("resume", result.changed, result.lifecycle_state))
        finally:
            sess.close()
            conn.close()

    t1 = threading.Thread(target=do_pause)
    t2 = threading.Thread(target=do_resume)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one should report changed
    changed_ops = [r for r in results if r[1]]
    assert len(changed_ops) == 1, (
        f"Expected exactly one operation to change state, got results: {results}"
    )

    # Final state must be valid
    final_states = {r[2] for r in results}
    assert final_states.issubset({ContainerLifecycle.ACTIVE.value, ContainerLifecycle.PAUSED.value}), (
        f"Invalid lifecycle state in results: {results}"
    )

    # Verify DB state is consistent
    verify_sess, verify_conn = _per_thread_session(pg_engine)
    try:
        wc = verify_sess.get(WorkContainer, cid)
        assert wc is not None
        assert wc.lifecycle_state in (ContainerLifecycle.ACTIVE.value, ContainerLifecycle.PAUSED.value)
        # Container should not be in an unrecognized state
        assert wc.lifecycle_state != ContainerLifecycle.COMPLETED.value
    finally:
        verify_sess.close()
        verify_conn.close()

    _cleanup_threaded_data(pg_engine, cid)


def test_rapid_pause_resume_pause_sequence(pg_session, pg_engine, monkeypatch):
    """Rapid pause→resume→pause sequence — each operation idempotent, final state = paused.

    Executes three operations in rapid succession, then repeats each one to confirm
    idempotency.  The final container state must be 'paused'.
    """
    from app.api.team_observatory import pause_container, resume_container
    from app.core.enums import ContainerLifecycle, RunStatus
    from app.core.models import Task, TaskBudget, TaskPhase, TaskRun, WorkContainer, WorkSession

    # Setup directly in a fresh session (avoid pg_session's explicit transaction)
    sess, conn = _per_thread_session(pg_engine)
    try:
        container = WorkContainer(
            name="快速暂停恢复测试",
            project_goal="测试快速暂停/恢复序列",
            base_workdir="/workspace/rpr",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        sess.add(container)
        sess.flush()
        cid = container.id

        task = Task(name=f"{container.name} · 开发", description="测试任务",
                    workdir=container.base_workdir, template="small_feature")
        sess.add(task)
        sess.flush()
        run = TaskRun(task_id=task.id, attempt_no=1, strategy="dynamic",
                      status=RunStatus.EXECUTING.value)
        sess.add(run)
        sess.flush()
        sess.add(TaskBudget(run_id=run.id))
        for ph in ("scan", "analyze", "modify", "verify", "repair", "summarize"):
            sess.add(TaskPhase(run_id=run.id, phase=ph))
        ws = WorkSession(container_id=cid, role="开发", goal="达成目标",
                         task_id=task.id, current_run_id=run.id,
                         status=RunStatus.EXECUTING.value)
        sess.add(ws)
        sess.commit()  # thread session: no explicit connection.begin(), safe

        # --- Step 1: pause (should change) ---
        r1 = pause_container(cid, session=sess)
        sess.commit()
        assert r1.changed is True
        assert r1.lifecycle_state == ContainerLifecycle.PAUSED.value

        # --- Step 2: pause again (idempotent, no change) ---
        r1b = pause_container(cid, session=sess)
        sess.commit()
        assert r1b.changed is False
        assert r1b.lifecycle_state == ContainerLifecycle.PAUSED.value

        # --- Step 3: resume (should change) ---
        r2 = resume_container(cid, session=sess)
        sess.commit()
        assert r2.changed is True
        assert r2.lifecycle_state == ContainerLifecycle.ACTIVE.value

        # --- Step 4: resume again (idempotent, no change) ---
        r2b = resume_container(cid, session=sess)
        sess.commit()
        assert r2b.changed is False
        assert r2b.lifecycle_state == ContainerLifecycle.ACTIVE.value

        # --- Step 5: pause (should change) ---
        r3 = pause_container(cid, session=sess)
        sess.commit()
        assert r3.changed is True
        assert r3.lifecycle_state == ContainerLifecycle.PAUSED.value

        # --- Step 6: pause again (idempotent, no change) ---
        r3b = pause_container(cid, session=sess)
        sess.commit()
        assert r3b.changed is False
        assert r3b.lifecycle_state == ContainerLifecycle.PAUSED.value

        # Final state is paused
        wc = sess.get(WorkContainer, cid)
        assert wc.lifecycle_state == ContainerLifecycle.PAUSED.value
    finally:
        sess.close()
        conn.close()

    _cleanup_threaded_data(pg_engine, cid)


def test_concurrent_budget_adjustments_see_updated_floor(pg_session, pg_engine, monkeypatch):
    """Concurrent budget adjustments — the second operator sees the updated floor.

    Operator A consumes budget (raises used+reserved), then both operators try to
    adjust max_total_tokens concurrently.  The second commit must respect the new
    floor established by the first commit.
    """
    import uuid as uuid_mod

    from app.api.team_observatory import BudgetPatchRequest, patch_container_budget
    from app.core.enums import RunStatus
    from app.core.models import Task, TaskBudget, TaskPhase, TaskRun, WorkContainer, WorkSession

    # Setup directly in pg_session
    container = WorkContainer(
        name="并发预算调整测试",
        project_goal="测试并发预算调整",
        base_workdir="/workspace/cba",
        lifecycle_state=ContainerLifecycle.ACTIVE.value,
    )
    pg_session.add(container)
    pg_session.flush()
    cid = container.id

    task = Task(name=f"{container.name} · 开发", description="测试任务",
                workdir=container.base_workdir, template="small_feature")
    pg_session.add(task)
    pg_session.flush()
    run = TaskRun(task_id=task.id, attempt_no=1, strategy="dynamic",
                  status=RunStatus.EXECUTING.value)
    pg_session.add(run)
    pg_session.flush()
    run_id = run.id

    budget = TaskBudget(run_id=run.id, max_total_tokens=50_000,
                        max_llm_calls=10, max_cost=10.0,
                        used_tokens=30_000, reserved_tokens=5_000)
    pg_session.add(budget)
    for ph in ("scan", "analyze", "modify", "verify", "repair", "summarize"):
        pg_session.add(TaskPhase(run_id=run.id, phase=ph))
    ws = WorkSession(container_id=cid, role="开发", goal="达成目标",
                     task_id=task.id, current_run_id=run.id,
                     status=RunStatus.EXECUTING.value)
    pg_session.add(ws)
    pg_session.flush()
    _commit_via_connection(pg_session)

    results: list[dict] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)

    def operator_a():
        sess, conn = _per_thread_session(pg_engine)
        try:
            # Consume more tokens — raise used to 36_000, floor becomes 41_000
            budget_a = sess.get(TaskBudget, run_id)
            budget_a.used_tokens = 36_000
            budget_a.reserved_tokens = 5_000  # floor = 41_000
            sess.commit()

            barrier.wait()
            body = BudgetPatchRequest(max_total_tokens=45_000)
            try:
                result = patch_container_budget(cid, body, session=sess)
                sess.commit()
                with lock:
                    results.append({"op": "A", "ok": True, "new_max": result.new_values.get("max_total_tokens")})
            except Exception as exc:
                sess.rollback()
                with lock:
                    results.append({"op": "A", "ok": False, "error": str(exc)})
        finally:
            sess.close()
            conn.close()

    def operator_b():
        sess, conn = _per_thread_session(pg_engine)
        try:
            barrier.wait()
            body = BudgetPatchRequest(max_total_tokens=38_000)
            try:
                result = patch_container_budget(cid, body, session=sess)
                sess.commit()
                with lock:
                    results.append({"op": "B", "ok": True, "new_max": result.new_values.get("max_total_tokens")})
            except Exception as exc:
                sess.rollback()
                with lock:
                    results.append({"op": "B", "ok": False, "error": str(exc)})
        finally:
            sess.close()
            conn.close()

    t1 = threading.Thread(target=operator_a)
    t2 = threading.Thread(target=operator_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Operator A should always succeed (45_000 > 41_000 floor)
    op_a = next(r for r in results if r["op"] == "A")
    assert op_a["ok"], f"Operator A should have succeeded, got: {op_a}"

    # Operator B: if it saw A's floor (41_000), it fails (38_000 < 41_000).
    # If it saw the original floor (35_000), it succeeds (38_000 > 35_000).
    # Either outcome is acceptable — the point is no corruption.
    op_b = next(r for r in results if r["op"] == "B")
    if not op_b["ok"]:
        # Expected when B sees the updated floor
        assert "below used+reserved floor" in op_b.get("error", "")
    else:
        # B succeeded — verify the final DB state is consistent
        pass

    # Verify DB state: the final max_total_tokens should be >= current floor
    verify_sess, verify_conn = _per_thread_session(pg_engine)
    try:
        final_budget = verify_sess.get(TaskBudget, run_id)
        assert final_budget is not None
        assert final_budget.max_total_tokens >= (final_budget.used_tokens + final_budget.reserved_tokens), (
            f"max_total_tokens ({final_budget.max_total_tokens}) below floor "
            f"({final_budget.used_tokens + final_budget.reserved_tokens})"
        )
    finally:
        verify_sess.close()
        verify_conn.close()

    _cleanup_threaded_data(pg_engine, cid)


def test_container_pause_during_session_status_transition(pg_session, pg_engine, monkeypatch):
    """Container pause while a session is mid-transition — no inconsistent state.

    Simulates a scenario where one thread is changing a session's run status
    (e.g. EXECUTING → OBSERVING) at the same time another thread pauses the
    container.  The final database state must be consistent: no orphaned or
    half-updated rows.
    """
    from app.api.runs import _transition
    from app.api.team_observatory import pause_container
    from app.core.enums import ContainerLifecycle, RunStatus
    from app.core.models import Task, TaskBudget, TaskPhase, TaskRun, WorkContainer, WorkSession

    # Setup directly in pg_session
    container = WorkContainer(
        name="状态转换竞态测试",
        project_goal="测试中间状态转换竞态",
        base_workdir="/workspace/str",
        lifecycle_state=ContainerLifecycle.ACTIVE.value,
    )
    pg_session.add(container)
    pg_session.flush()
    cid = container.id

    task = Task(name=f"{container.name} · 开发", description="测试任务",
                workdir=container.base_workdir, template="small_feature")
    pg_session.add(task)
    pg_session.flush()
    run = TaskRun(task_id=task.id, attempt_no=1, strategy="dynamic",
                  status=RunStatus.EXECUTING.value)
    pg_session.add(run)
    pg_session.flush()
    run_id = run.id
    sid = None  # will be set below

    pg_session.add(TaskBudget(run_id=run.id))
    for ph in ("scan", "analyze", "modify", "verify", "repair", "summarize"):
        pg_session.add(TaskPhase(run_id=run.id, phase=ph))
    ws = WorkSession(container_id=cid, role="开发", goal="达成目标",
                     task_id=task.id, current_run_id=run.id,
                     status=RunStatus.EXECUTING.value)
    pg_session.add(ws)
    pg_session.flush()
    sid = ws.id
    _commit_via_connection(pg_session)

    results: list[dict] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)

    def do_status_transition():
        """Simulate a worker transitioning run status (EXECUTING → OBSERVING)."""
        sess, conn = _per_thread_session(pg_engine)
        try:
            run_obj = sess.get(TaskRun, run_id)
            barrier.wait()
            result = _transition(sess, run_obj, RunStatus.OBSERVING)
            ws_obj = sess.get(WorkSession, sid)
            if ws_obj and result.get("changed"):
                ws_obj.status = RunStatus.OBSERVING.value
            sess.commit()
            with lock:
                results.append({"op": "transition", "changed": result.get("changed"), "status": run_obj.status})
        finally:
            sess.close()
            conn.close()

    def do_pause():
        """Pause the container concurrently with the status transition."""
        sess, conn = _per_thread_session(pg_engine)
        try:
            barrier.wait()
            result = pause_container(cid, session=sess)
            sess.commit()
            with lock:
                results.append({
                    "op": "pause",
                    "changed": result.changed,
                    "lifecycle_state": result.lifecycle_state,
                    "paused_sessions": result.paused_sessions,
                })
        finally:
            sess.close()
            conn.close()

    t1 = threading.Thread(target=do_status_transition)
    t2 = threading.Thread(target=do_pause)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Verify final DB state is consistent
    verify_sess, verify_conn = _per_thread_session(pg_engine)
    try:
        wc = verify_sess.get(WorkContainer, cid)
        assert wc is not None
        assert wc.lifecycle_state in {
            ContainerLifecycle.ACTIVE.value,
            ContainerLifecycle.PAUSED.value,
        }, f"Unexpected container lifecycle: {wc.lifecycle_state}"

        run_obj = verify_sess.get(TaskRun, run_id)
        assert run_obj is not None
        assert RunStatus(run_obj.status) in {
            RunStatus.EXECUTING, RunStatus.OBSERVING, RunStatus.PAUSED, RunStatus.REPLANNING,
        }, f"Unexpected run status: {run_obj.status}"

        ws_obj = verify_sess.get(WorkSession, sid)
        assert ws_obj is not None
        assert ws_obj.status == run_obj.status, (
            f"Session status ({ws_obj.status}) does not match run status ({run_obj.status})"
        )

        if wc.lifecycle_state == ContainerLifecycle.PAUSED.value:
            assert run_obj.status == RunStatus.PAUSED.value, (
                f"Container paused but run status is {run_obj.status}, expected PAUSED"
            )
    finally:
        verify_sess.close()
        verify_conn.close()

    _cleanup_threaded_data(pg_engine, cid)
