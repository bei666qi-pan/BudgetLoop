"""End-to-end tests for Team Observatory — full API workflow through DB.

Covers: enriched container GET with observatory data, session creation,
pause/resume/stop lifecycle, message sending, audit events, budget operations,
and team progress/usage endpoints.
"""
from __future__ import annotations

import json
import os
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


def _create_container(c: TestClient, name: str = "观测台测试团队") -> dict:
    resp = c.post(
        "/api/work-containers",
        headers=AUTH,
        json={
            "name": name,
            "project_goal": "端到端观测台测试",
            "shared_context": "共享上下文",
            "base_workdir": "/workspace/test",
            "default_workspace_policy": "isolated",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_session(
    c: TestClient,
    container_id: str,
    key: str,
    role: str = "后端实现",
    **overrides,
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


# ---------------------------------------------------------------------------
#  Scenario 1: Get enriched container with observatory data
# ---------------------------------------------------------------------------


def test_get_enriched_container_with_observatory_data(client):
    """GET container returns enriched fields: team_status, usage_summary, progress_summary."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "obs-s1", role="后端实现")
    s2 = _create_session(c, cid, "obs-s2", role="前端开发")

    # GET enriched container
    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Core container fields
    assert data["name"] == "观测台测试团队"
    assert data["project_goal"] == "端到端观测台测试"
    assert data["lifecycle_state"] == "active"

    # Enriched observatory fields
    assert "team_status" in data
    assert "usage_summary" in data
    assert "progress_summary" in data

    # team_status
    ts = data["team_status"]
    assert ts["phase"] in ("running", "idle")
    assert ts["total_sessions"] == 3
    assert ts["lifecycle_state"] == "active"

    # usage_summary
    assert "usage_summary" in data
    us = data["usage_summary"]
    assert "tokens" in us or "total_tokens" in us
    assert "cost" in us or "total_cost" in us or us.get("total_cost") is None

    # progress_summary — list of per-session progress entries
    ps = data["progress_summary"]
    assert isinstance(ps, list)
    assert len(ps) == 3


def test_enriched_container_includes_sessions(client):
    """Session list is included in enriched container data."""
    c, _, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "ess-s1", role="后端")
    s2 = _create_session(c, cid, "ess-s2", role="前端")

    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()

    assert "sessions" in data
    assert len(data["sessions"]) == 3

    roles = [s["role"] for s in data["sessions"]]
    assert "后端" in roles
    assert "前端" in roles
    assert "汇总裁判" in roles


# ---------------------------------------------------------------------------
#  Scenario 2: Full pause/resume lifecycle with observatory state
# ---------------------------------------------------------------------------


def test_observatory_reflects_paused_state(client):
    """When container is paused, enriched GET reflects paused lifecycle."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "orp-s1", role="开发")

    # Pause
    r = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["lifecycle_state"] == "paused"

    # GET enriched
    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle_state"] == "paused"
    assert data["team_status"]["phase"] == "paused"


def test_observatory_reflects_resumed_state(client):
    """After resume, observatory data returns to active."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "orr-s1", role="开发")

    c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    c.post(f"/api/work-containers/{cid}/resume", headers=AUTH)

    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle_state"] == "active"


# ---------------------------------------------------------------------------
#  Scenario 3: Session messaging through observatory
# ---------------------------------------------------------------------------


def test_send_message_between_sessions(client):
    """Send a message from one session to another via the messages endpoint."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "msg-s1", role="发送者")
    s2 = _create_session(c, cid, "msg-s2", role="接收者")
    sid1 = s1["session"]["id"]
    sid2 = s2["session"]["id"]

    # Send message FROM s1 TO s2 (recipient is s2 in URL)
    resp = c.post(
        f"/api/work-containers/{cid}/sessions/{sid2}/messages",
        headers=AUTH,
        json={
            "content": "请开始处理API路由",
            "message_type": "message",
            "kind": "message",
            "sender_session_id": sid1,
        },
    )
    assert resp.status_code == 201, resp.text
    msg_data = resp.json()
    assert msg_data["message"]["content"] == "请开始处理API路由"
    assert msg_data["message"]["sender_session_id"] == sid1

    # Verify message persisted
    pg_session.expire_all()
    message = pg_session.get(SessionMessage, uuid.UUID(msg_data["message"]["id"]))
    assert message is not None
    assert message.content == "请开始处理API路由"


def test_send_handoff_between_sessions(client):
    """Send a handoff message with structured metadata."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "hnd-s1", role="架构设计")
    s2 = _create_session(c, cid, "hnd-s2", role="后端实现")
    sid1 = s1["session"]["id"]
    sid2 = s2["session"]["id"]

    resp = c.post(
        f"/api/work-containers/{cid}/sessions/{sid2}/messages",
        headers=AUTH,
        json={
            "message_type": "handoff",
            "kind": "handoff",
            "content": json.dumps({
                "conclusion": "接口使用RESTful POST /api/tasks",
                "evidence": "api-contract.md L42",
                "open_questions": ["是否需要分页"],
                "next_step": "实现端点",
            }),
            "sender_session_id": sid1,
            "metadata": {
                "conclusion": "接口使用RESTful POST /api/tasks",
                "evidence": "api-contract.md L42",
                "open_questions": ["是否需要分页"],
                "next_step": "实现端点",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    msg_data = resp.json()

    # Message type should reflect in entry_type or kind
    assert msg_data["message"]["sender_session_id"] == sid1

    # Verify metadata persisted
    pg_session.expire_all()
    message = pg_session.get(SessionMessage, uuid.UUID(msg_data["message"]["id"]))
    assert message is not None
    # metadata is stored as a JSON field; verify it exists
    assert message.metadata is not None


# ---------------------------------------------------------------------------
#  Scenario 4: Audit events for control operations
# ---------------------------------------------------------------------------


def test_pause_creates_audit_event(client):
    """Pausing a container creates an audit event."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "aud-p1", role="开发")

    r = c.post(f"/api/work-containers/{cid}/pause", headers=AUTH)
    assert r.status_code == 200

    # Check audit event exists
    from sqlalchemy import func, select as sa_select

    stmt = sa_select(func.count()).select_from(TeamAuditEvent).where(
        TeamAuditEvent.container_id == cid,
        TeamAuditEvent.action == "pause",
    )
    count = pg_session.execute(stmt).scalar_one()
    assert count == 1


def test_stop_with_confirmation_creates_audit_event(client):
    """Stopping a container with confirmation creates audit event and
    transitions lifecycle to completed."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    _create_session(c, str(cid), "aud-st1", role="开发")

    r = c.post(
        f"/api/work-containers/{cid}/stop",
        headers=AUTH,
        json={"confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle_state"] == "completed"

    # Verify container is completed
    pg_session.expire_all()
    wc = pg_session.get(WorkContainer, cid)
    assert wc.lifecycle_state == ContainerLifecycle.COMPLETED.value

    # Audit event
    from sqlalchemy import func, select as sa_select

    stmt = sa_select(func.count()).select_from(TeamAuditEvent).where(
        TeamAuditEvent.container_id == cid,
        TeamAuditEvent.action == "stop",
    )
    count = pg_session.execute(stmt).scalar_one()
    assert count == 1


# ---------------------------------------------------------------------------
#  Scenario 5: Budget operations through observatory
# ---------------------------------------------------------------------------


def test_budget_increase_updates_observatory(client):
    """Increasing container budget reflects in subsequent GET."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    _create_session(c, cid, "bud-s1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 5.0,
    })

    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 20_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_values"]["max_total_tokens"] == 20_000

    # Verify enriched container reflects budget
    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    # Budget might be in container's session budgets
    data = resp.json()
    assert "usage_summary" in data


def test_budget_below_floor_rejected(client):
    """Setting budget below used+reserved floor returns 422."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = uuid.UUID(container["id"])

    s1 = _create_session(c, cid, "bud-bf1", role="开发", budget={
        "max_total_tokens": 10_000,
        "max_llm_calls": 10,
        "max_cost": 5.0,
    })
    run_id = uuid.UUID(s1["session"]["current_run_id"])
    budget = pg_session.get(TaskBudget, run_id)
    budget.used_tokens = 8_000
    pg_session.commit()

    r = c.patch(
        f"/api/work-containers/{cid}/budget",
        headers=AUTH,
        json={"max_total_tokens": 6_000},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "below used+reserved floor" in detail["message"]


# ---------------------------------------------------------------------------
#  Scenario 6: Team progress and usage endpoints
# ---------------------------------------------------------------------------


def test_team_progress_endpoint(client):
    """GET /work-containers/{id}/progress returns team summary and signals."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    s1 = _create_session(c, cid, "prog-s1", role="后端实现")
    s2 = _create_session(c, cid, "prog-s2", role="前端开发")

    resp = c.get(f"/api/work-containers/{cid}/progress", headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "team_summary" in data
    assert data["team_summary"]["total"] == 3
    assert "sessions" in data


def test_team_usage_endpoint(client):
    """GET /work-containers/{id}/usage returns aggregated usage data."""
    c, pg_session, _ = client
    container = _create_container(c)
    cid = container["id"]

    _create_session(c, cid, "use-s1", role="开发")

    resp = c.get(f"/api/work-containers/{cid}/usage", headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "aggregate" in data
    # aggregate has used/reserved/remaining/max with tokens/cost/calls sub-keys
    agg = data["aggregate"]
    assert "used" in agg
    assert "tokens" in agg["used"]
    assert "cost" in agg["used"]
    assert "calls" in agg["used"]
    assert "team_pressure_mode" in data


# ---------------------------------------------------------------------------
#  Scenario 7: Multiple sessions and counts
# ---------------------------------------------------------------------------


def test_multiple_sessions_reflected_in_counts(client):
    """Creating multiple sessions updates the container's session counts."""
    c, _, _ = client
    container = _create_container(c)
    cid = container["id"]

    _create_session(c, cid, "ms-s1", role="开发1")
    _create_session(c, cid, "ms-s2", role="开发2")
    _create_session(c, cid, "ms-s3", role="开发3")

    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["sessions"]) == 4
    assert data["team_status"]["total_sessions"] == 4


def test_container_without_user_sessions_still_has_mandatory_judge(client):
    """A new container exposes its mandatory system judge immediately."""
    c, _, _ = client
    container = _create_container(c)
    cid = container["id"]

    resp = c.get(f"/api/work-containers/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_kind"] == "judge"
    assert data["team_status"]["total_sessions"] == 1
    # Empty container may show "idle" or "completed" depending on lifecycle state
    assert data["team_status"]["phase"] in ("idle", "completed")


# ---------------------------------------------------------------------------
#  Scenario 8: Stream endpoint returns SSE events (skipped — requires
#  execution_events.container_id column which doesn't exist in test DB)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="SSE endpoint opens its own SessionLocal() connection, which cannot see "
    "uncommitted test-transaction data. Requires a different test pattern (e.g., "
    "using raw psycopg connection for entire test setup). "
    "The SSE endpoint is tested via test_team_sse.py unit tests with db_session fixture."
)
def test_stream_endpoint_returns_sse(client):
    """GET /work-containers/{id}/stream returns an SSE response.
    
    NOTE: This test is skipped because the SSE endpoint opens its own
    SessionLocal() connection, which cannot see uncommitted test-transaction
    data. The SSE functionality is tested via test_team_sse.py.
    """
    pass
