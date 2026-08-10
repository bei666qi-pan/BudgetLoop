from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai_gateway.client import GatewayClient
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RunStatus
from app.core.models import ExecutionEvent, JudgeRound, SessionMessage, WorkSession
from app.main import app
from app.worker import broker
from app.worker.orchestrator import Orchestrator
from tests.conftest import requires_docker

pytestmark = requires_docker
AUTH = {"Authorization": f"Bearer {settings.api_token}"}


@pytest.fixture()
def client(pg_session, monkeypatch):
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(broker, "enqueue_run", lambda _run_id: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_container(client: TestClient) -> dict:
    response = client.post(
        "/api/work-containers",
        headers=AUTH,
        json={
            "name": "裁判闭环",
            "project_goal": "通过真实团队证据完成交付",
            "base_workdir": "/tmp/judge-loop",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_agent(client: TestClient, container_id: str, key: str) -> dict:
    response = client.post(
        f"/api/work-containers/{container_id}/sessions",
        headers={**AUTH, "Idempotency-Key": key},
        json={"role": key, "goal": "完成责任范围并回复裁判", "require_approval": False},
    )
    assert response.status_code == 201, response.text
    return response.json()["session"]


def test_team_creation_provisions_visible_independently_budgeted_judge(client):
    container = _create_container(client)
    judge = container["judge"]

    assert judge["enabled"] is True
    assert judge["session"]["role"] == "汇总裁判"
    assert judge["session"]["system_managed"] is True
    assert judge["session"]["budget"]["max_total_tokens"] == 60_000
    assert len(judge["policy"]["gates"]) == 8
    judge_sessions = [item for item in container["sessions"] if item["session_kind"] == "judge"]
    assert len(judge_sessions) == 1
    assert judge_sessions[0]["system_managed"] is True

    state = client.get(
        f"/api/work-containers/{container['id']}/judge", headers=AUTH
    )
    assert state.status_code == 200, state.text
    assert state.json()["session"]["id"] == judge["session"]["id"]


def test_failed_hard_gates_dispatch_parallel_feedback_and_resume_is_idempotent(
    client, pg_session, monkeypatch
):
    container = _create_container(client)
    first = _create_agent(client, container["id"], "frontend")
    second = _create_agent(client, container["id"], "qa")
    activated: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: activated.append(run_id))
    monkeypatch.setattr(
        GatewayClient,
        "recommend",
        lambda *_args, **_kwargs: pytest.fail("model must not run while a hard gate fails"),
    )

    headers = {**AUTH, "Idempotency-Key": "judge-round-one"}
    response = client.post(
        f"/api/work-containers/{container['id']}/judge/resume",
        headers=headers,
        json={"evidence": {}},
    )
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["current_round"]["verdict"] == "rework"
    assert len(state["current_round"]["gates"]) == 8
    assert any(not item["passed"] for item in state["current_round"]["gates"])
    assert set(state["pending_reply_session_ids"]) == {first["id"], second["id"]}
    assert set(activated) == {first["current_run_id"], second["current_run_id"]}

    messages = list(
        pg_session.execute(
            select(SessionMessage).where(
                SessionMessage.container_id == uuid.UUID(container["id"]),
                SessionMessage.sender_session_id == uuid.UUID(state["session"]["id"]),
            )
        ).scalars()
    )
    assert {str(item.recipient_session_id) for item in messages} == {first["id"], second["id"]}
    assert all(item.delivery_state == "queued" for item in messages)

    repeated = client.post(
        f"/api/work-containers/{container['id']}/judge/resume",
        headers=headers,
        json={"evidence": {}},
    )
    assert repeated.status_code == 200
    assert len(repeated.json()["rounds"]) == 1

    event_types = {
        item.type
        for item in pg_session.execute(
            select(ExecutionEvent).where(
                ExecutionEvent.container_id == uuid.UUID(container["id"])
            )
        ).scalars()
    }
    assert {
        "judge_state_changed",
        "judge_gate_completed",
        "judge_feedback_dispatched",
        "judge_verdict_recorded",
    } <= event_types


def test_failed_hard_gate_can_target_responsible_session(
    client, pg_session, monkeypatch
):
    container = _create_container(client)
    frontend = _create_agent(client, container["id"], "frontend")
    _create_agent(client, container["id"], "qa")
    frontend_row = pg_session.get(WorkSession, uuid.UUID(frontend["id"]))
    frontend_row.status = RunStatus.COMPLETED.value
    frontend_row.current_run.status = RunStatus.COMPLETED.value
    pg_session.commit()
    activated: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: activated.append(run_id))
    monkeypatch.setattr(
        GatewayClient,
        "recommend",
        lambda *_args, **_kwargs: pytest.fail("model must not run while a hard gate fails"),
    )

    response = client.post(
        f"/api/work-containers/{container['id']}/judge/resume",
        headers={**AUTH, "Idempotency-Key": "judge-targeted-hard-gate"},
        json={
            "evidence": {
                "tests_passed": False,
                "evidence_refs": ["playwright:mobile-overflow"],
                "responsible_session_ids": [frontend["id"]],
                "rework_instruction": "修复 390px 横向溢出后回复测试证据。",
            }
        },
    )

    assert response.status_code == 200, response.text
    round_ = response.json()["current_round"]
    assert round_["verdict"] == "rework"
    assert round_["pending_session_ids"] == [frontend["id"]]
    assert {item["responsible_session_id"] for item in round_["findings"]} == {
        frontend["id"]
    }
    pg_session.refresh(frontend_row)
    assert str(frontend_row.current_run_id) != frontend["current_run_id"]
    assert activated == [str(frontend_row.current_run_id)]
    assert "Judge-directed rework run" in (
        frontend_row.current_run.model_config["run_instruction"]
    )
    assert "修复 390px 横向溢出" in (
        frontend_row.current_run.model_config["run_instruction"]
    )
    message = pg_session.execute(
        select(SessionMessage).where(
            SessionMessage.container_id == uuid.UUID(container["id"]),
            SessionMessage.recipient_session_id == uuid.UUID(frontend["id"]),
            SessionMessage.sender_session_id
            == uuid.UUID(response.json()["session"]["id"]),
        )
    ).scalar_one()
    assert "修复 390px 横向溢出" in message.content


def test_invalid_model_output_blocks_instead_of_deterministic_approval(
    client, pg_session, monkeypatch, tmp_path: Path
):
    container = _create_container(client)
    agent = _create_agent(client, container["id"], "integration")
    judge_id = container["judge"]["session"]["id"]
    row = pg_session.get(WorkSession, uuid.UUID(agent["id"]))
    row.status = RunStatus.COMPLETED.value
    row.current_run.status = RunStatus.COMPLETED.value
    artifact = tmp_path / "index.html"
    artifact.write_text("<!doctype html>", encoding="utf-8")
    pg_session.add(
        SessionMessage(
            container_id=uuid.UUID(container["id"]),
            sender_session_id=row.id,
            recipient_session_id=uuid.UUID(judge_id),
            author_type="session",
            kind="handoff",
            message_type="handoff",
            content="已完成并附上验证证据",
            delivery_state="acknowledged",
        )
    )
    pg_session.commit()

    class Response:
        content = "not-json"

    monkeypatch.setattr(GatewayClient, "recommend", lambda *_args, **_kwargs: Response())
    response = client.post(
        f"/api/work-containers/{container['id']}/judge/resume",
        headers={**AUTH, "Idempotency-Key": "judge-model-invalid"},
        json={
            "evidence": {
                "evidence_refs": ["test-report"],
                "integration_published": True,
                "tests_passed": True,
                "test_commands": ["pytest"],
                "build_passed": True,
                "target_artifacts": [str(artifact)],
            }
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["current_round"]["verdict"] == "blocked"
    assert "输出无效" in response.json()["current_round"]["summary"]

    class ApprovedResponse:
        content = '{"verdict":"approve","summary":"证据与质量均通过","findings":[],"next_step":"交付"}'

    monkeypatch.setattr(GatewayClient, "recommend", lambda *_args, **_kwargs: ApprovedResponse())
    resumed = client.post(
        f"/api/work-containers/{container['id']}/judge/resume",
        headers={**AUTH, "Idempotency-Key": "judge-model-recovered"},
        json={"evidence": {}},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["current_round"]["verdict"] == "approve"


def test_required_judge_request_records_real_agent_output_as_acknowledged_reply(
    client, pg_session
):
    container = _create_container(client)
    agent = _create_agent(client, container["id"], "frontend")
    judge_id = uuid.UUID(container["judge"]["session"]["id"])
    agent_row = pg_session.get(WorkSession, uuid.UUID(agent["id"]))
    request = SessionMessage(
        container_id=uuid.UUID(container["id"]),
        sender_session_id=judge_id,
        recipient_session_id=agent_row.id,
        author_type="session",
        kind="handoff",
        message_type="system_fact",
        content="请补充响应式验证证据",
        delivery_state="injected",
        message_metadata={"required_response": True, "judge_round_id": "round-one"},
    )
    pg_session.add(request)
    pg_session.commit()

    orchestrator = Orchestrator(pg_session, agent_row.current_run_id)
    orchestrator._store_required_message_responses(
        agent_row.current_run,
        2,
        "已运行 390px 验收，控制台零错误。",
    )
    pg_session.refresh(request)
    reply = pg_session.execute(
        select(SessionMessage).where(
            SessionMessage.sender_session_id == agent_row.id,
            SessionMessage.recipient_session_id == judge_id,
        )
    ).scalar_one()
    assert request.delivery_state == "acknowledged"
    assert request.acknowledged_at is not None
    assert reply.content == "已运行 390px 验收，控制台零错误。"
    assert reply.delivery_state == "queued"
    assert reply.message_metadata["response_to_message_id"] == str(request.id)
