"""Integration coverage for work-container isolation and additive task ownership."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.ai_gateway import resolve_gateway_config  # noqa: E402
from app.collaboration.autonomous import release_autonomous_stages  # noqa: E402
from app.core.config import Settings, settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.enums import EventType  # noqa: E402
from app.core.models import (  # noqa: E402
    ExecutionEvent,
    SessionMessage,
    Task,
    TaskBudget,
    TaskRun,
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
        yield test_client, enqueued
    app.dependency_overrides.clear()


def _container(client: TestClient, name: str = "支付服务重构") -> dict:
    response = client.post(
        "/api/work-containers",
        headers=AUTH,
        json={
            "name": name,
            "project_goal": "用隔离的专业 Session 完成重构并保留审计链路",
            "shared_context": "PostgreSQL 是唯一业务事实来源。",
            "base_workdir": "/workspace/project",
            "default_workspace_policy": "isolated",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _session(client: TestClient, container_id: str, key: str = "session-1", **values) -> dict:
    body = {
        "role": "后端实现",
        "goal": "实现接口与持久化边界",
        "private_context": "只处理后端细节",
        "budget": {"max_total_tokens": 8_000, "max_llm_calls": 5},
    }
    body.update(values)
    response = client.post(
        f"/api/work-containers/{container_id}/sessions",
        headers={**AUTH, "Idempotency-Key": key},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_container_validation_lifecycle_and_listing(client):
    c, _ = client
    invalid = c.post(
        "/api/work-containers",
        headers=AUTH,
        json={"name": "x", "project_goal": "goal", "base_workdir": "relative/path"},
    )
    assert invalid.status_code == 422

    container = _container(c)
    assert container["counts"] == {"sessions": 0, "running": 0, "waiting": 0, "attention": 0}
    updated = c.patch(
        f"/api/work-containers/{container['id']}",
        headers=AUTH,
        json={"lifecycle_state": "paused", "shared_context": "更新后的共享事实"},
    )
    assert updated.status_code == 200
    assert updated.json()["lifecycle_state"] == "paused"
    listed = c.get("/api/work-containers?lifecycle=paused&limit=10", headers=AUTH).json()
    assert [item["id"] for item in listed["containers"]] == [container["id"]]
    assert c.get("/api/work-containers?limit=101", headers=AUTH).status_code == 422


def test_session_creation_is_atomic_idempotent_and_legacy_safe(client, pg_session):
    c, enqueued = client
    container = _container(c)
    first = _session(c, container["id"])
    created = first["session"]
    assert first["created"] is True
    assert created["task_id"] and created["current_run_id"]
    assert created["private_context"] == "只处理后端细节"
    assert enqueued == [created["current_run_id"]]

    repeated = _session(c, container["id"], role="另一个角色")
    assert repeated["created"] is False
    assert repeated["session"]["id"] == created["id"]
    assert enqueued == [created["current_run_id"]]

    owned_run = c.get(f"/api/runs/{created['current_run_id']}", headers=AUTH).json()["run"]
    assert owned_run["work_container_id"] == container["id"]
    assert owned_run["work_session_id"] == created["id"]

    legacy = c.post(
        "/api/tasks",
        headers=AUTH,
        json={"name": "legacy", "description": "legacy", "workdir": "/workspace/project"},
    ).json()
    legacy_run = c.get(f"/api/runs/{legacy['run_id']}", headers=AUTH).json()["run"]
    assert legacy_run["work_container_id"] is None
    assert pg_session.get(WorkSession, uuid.UUID(created["id"])).task is not None


def test_nested_ownership_message_idempotency_and_pause(client):
    c, _ = client
    container = _container(c)
    other = _container(c, "另一个项目")
    sender = _session(c, container["id"], key="sender", role="架构设计")["session"]
    recipient = _session(c, container["id"], key="recipient", role="后端实现")["session"]

    foreign = c.get(f"/api/work-containers/{other['id']}/sessions/{recipient['id']}", headers=AUTH)
    assert foreign.status_code == 404

    path = f"/api/work-containers/{container['id']}/sessions/{recipient['id']}/messages"
    body = {
        "sender_session_id": sender["id"],
        "kind": "handoff",
        "content": "请按接口契约实现，并保留幂等语义。",
    }
    first = c.post(path, headers={**AUTH, "Idempotency-Key": "handoff-1"}, json=body)
    assert first.status_code == 201, first.text
    assert first.json()["message"]["delivery_state"] == "queued"
    second = c.post(path, headers={**AUTH, "Idempotency-Key": "handoff-1"}, json=body)
    assert second.json()["created"] is False
    assert second.json()["message"]["id"] == first.json()["message"]["id"]

    cross_container = c.post(
        path,
        headers=AUTH,
        json={
            "sender_session_id": _session(c, other["id"], key="foreign")["session"]["id"],
            "kind": "handoff",
            "content": "不得跨容器",
        },
    )
    assert cross_container.status_code == 404

    paused = c.post(
        f"/api/work-containers/{container['id']}/sessions/{recipient['id']}/pause",
        headers=AUTH,
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"


def test_session_transcript_labels_agent_output_and_explicit_handoff(client, pg_session):
    c, _ = client
    container = _container(c)
    sender = _session(c, container["id"], key="s1", role="架构设计")["session"]
    recipient = _session(c, container["id"], key="s2", role="后端实现")["session"]
    c.post(
        f"/api/work-containers/{container['id']}/sessions/{recipient['id']}/messages",
        headers=AUTH,
        json={
            "sender_session_id": sender["id"],
            "kind": "handoff",
            "content": "这是显式移交内容",
        },
    )
    pg_session.add(
        ExecutionEvent(
            run_id=uuid.UUID(recipient["current_run_id"]),
            type=EventType.AGENT_MESSAGE.value,
            payload={"iteration": 1, "text": "这是公开 Agent 输出"},
        )
    )
    pg_session.commit()

    detail = c.get(f"/api/work-containers/{container['id']}/sessions/{recipient['id']}", headers=AUTH).json()
    assert {entry["entry_type"] for entry in detail["transcript"]} == {
        "handoff",
        "agent_output",
    }
    assert all("private_context" not in entry for entry in detail["transcript"])


def test_preset_catalog_and_local_langgraph_recommendation(client, monkeypatch):
    c, _ = client
    local_only = resolve_gateway_config(
        Settings(
            _env_file=None,
            ai_gateway_api_key="",
            ai_gateway_base_url="",
            litellm_master_key="",
        )
    )
    monkeypatch.setattr("app.api.team_presets.resolve_gateway_config", lambda: local_only)
    assert c.get("/api/work-container-presets").status_code == 401
    catalog = c.get("/api/work-container-presets", headers=AUTH)
    assert catalog.status_code == 200
    payload = catalog.json()
    assert len(payload["presets"]) == 9
    assert payload["runtime"] == {
        "graph": "LangGraph",
        "configuration_required": False,
        "recommendation_remote_calls": False,
        "ai_preferred": True,
        "local_fallback": True,
        "gateway_type": "new-api",
    }
    assert all(
        source["reviewed_stars"] >= 10_000 for preset in payload["presets"] for source in preset["sources"]
    )
    assert c.get("/api/work-container-presets?category=unknown", headers=AUTH).status_code == 422

    response = c.post(
        "/api/work-container-presets/recommend",
        headers=AUTH,
        json={"goal": "做一个手机解谜游戏试玩版", "pace": "fast", "risk": "creative"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["runtime"] == "langgraph"
    assert result["recommendations"][0]["preset"]["id"] == "game-development"
    assert result["recommendations"][0]["matched_signals"]
    assert "隐藏推理" in result["explanation"]


def test_create_team_later_is_atomic_idempotent_and_retry_safe(client, pg_session):
    c, enqueued = client
    body = {
        "preset_id": "game-development",
        "preset_version": 1,
        "name": "星港谜案",
        "project_goal": "交付一个移动端解谜游戏试玩版",
        "shared_context": "首个版本只做一章。",
        "base_workdir": "/workspace/game",
        "start_immediately": False,
    }
    headers = {**AUTH, "Idempotency-Key": "team-game-001"}
    first = c.post("/api/work-containers/from-preset", headers=headers, json=body)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result["created"] is True
    container = result["container"]
    assert container["preset_id"] == "game-development"
    assert container["preset_version"] == 1
    assert len(container["sessions"]) == 5
    assert {item["status"] for item in container["sessions"]} == {"PENDING"}
    assert enqueued == []
    snapshot = container["preset_snapshot"]
    assert snapshot["workspace_access"] == {
        "folder_access": "isolated",
        "project_dir": None,
        "worktree_required": False,
    }
    assert snapshot["activation_plan"]["runtime"] == "langgraph"
    assert [wave["stage"] for wave in snapshot["activation_plan"]["activation_waves"]] == [
        "planning",
        "design",
        "implementation",
        "review",
    ]

    repeated = c.post("/api/work-containers/from-preset", headers=headers, json=body)
    assert repeated.status_code == 201
    assert repeated.json()["created"] is False
    assert repeated.json()["container"]["id"] == container["id"]

    start = c.post(f"/api/work-containers/{container['id']}/start", headers=AUTH)
    assert start.status_code == 200
    assert start.json()["warnings"] == []
    assert len(start.json()["accepted"]) == 5
    assert enqueued == start.json()["accepted"]

    retry = c.post(f"/api/work-containers/{container['id']}/start", headers=AUTH)
    assert retry.status_code == 200
    assert retry.json()["accepted"] == []
    assert {item["reason"] for item in retry.json()["skipped"]} == {"already_dispatched"}
    assert len(enqueued) == 5

    stored = pg_session.get(WorkContainer, uuid.UUID(container["id"]))
    assert stored is not None
    assert stored.idempotency_key == "team-game-001"
    assert stored.preset_snapshot["dispatch"]["dispatched_run_ids"]
    assert all(
        pg_session.get(TaskRun, uuid.UUID(item["current_run_id"])).model_config["folder_access"] == "isolated"
        for item in container["sessions"]
    )


def test_autonomous_max_team_starts_entry_stage_and_releases_handoffs(client, pg_session):
    c, enqueued = client
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-autonomous-max-001"},
        json={
            "preset_id": "software-delivery",
            "preset_version": 1,
            "name": "自主交付",
            "project_goal": "并行完成应用交付并在阶段间自动移交",
            "base_workdir": "/workspace/autonomous",
            "team_mode": "autonomous",
            "budget_mode": "max",
            "start_immediately": True,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    container = payload["container"]
    assert container["preset_snapshot"]["team_mode"] == "autonomous"
    assert container["preset_snapshot"]["budget_mode"] == "max"
    assert len(enqueued) == 1  # discovery is the only dependency-free stage
    first = next(item for item in container["sessions"] if item["role"] == "产品负责人")
    first_run = pg_session.get(TaskRun, uuid.UUID(first["current_run_id"]))
    assert first_run is not None
    assert first_run.deadline_at is None
    assert first_run.model_config["team_mode"] == "autonomous"
    assert first_run.model_config["budget_mode"] == "max"

    pg_session.add(
        ExecutionEvent(
            run_id=first_run.id,
            type=EventType.AGENT_MESSAGE.value,
            payload={"text": "接口范围和验收条件已确认。"},
        )
    )
    first_run.status = "COMPLETED"
    pg_session.commit()
    released = release_autonomous_stages(pg_session, first_run)
    pg_session.commit()

    assert len(released) == 1
    handoffs = pg_session.query(SessionMessage).filter_by(container_id=uuid.UUID(container["id"])).all()
    assert len(handoffs) == 1
    assert handoffs[0].kind == "handoff"
    assert handoffs[0].author_type == "agent"
    assert "接口范围" in handoffs[0].content
    assert release_autonomous_stages(pg_session, first_run) == []


def test_full_access_team_persists_acknowledged_path_and_worktrees(client, pg_session):
    c, enqueued = client
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-full-access-001"},
        json={
            "preset_id": "software-delivery",
            "preset_version": 1,
            "name": "真实项目修复",
            "project_goal": "修复项目并补充回归测试",
            "base_workdir": "/workspace/project",
            "default_workspace_policy": "worktree",
            "folder_access": "full_access",
            "project_dir": "/tmp/budgetloop-project/",
            "full_access_acknowledged": True,
            "recommendation_source": "ai",
            "start_immediately": False,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert enqueued == []
    assert payload["container"]["preset_snapshot"]["workspace_access"] == {
        "folder_access": "full_access",
        "project_dir": "/tmp/budgetloop-project",
        "worktree_required": True,
    }
    assert payload["container"]["preset_snapshot"]["recommendation_source"] == "ai"
    assert all(item["worktree_enabled"] for item in payload["container"]["sessions"])
    run_ids = [uuid.UUID(item["current_run_id"]) for item in payload["container"]["sessions"]]
    for run_id in run_ids:
        run = pg_session.get(TaskRun, run_id)
        assert run is not None
        assert run.model_config["folder_access"] == "full_access"
        assert run.model_config["project_dir"] == "/tmp/budgetloop-project"


def test_full_access_team_rejects_cli_engine_before_creating_runs(client):
    c, _ = client
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-full-access-cli-001"},
        json={
            "preset_id": "software-delivery",
            "preset_version": 1,
            "name": "CLI 全访问团队",
            "project_goal": "确保完整访问不会被不可挂载的 CLI 引擎接受",
            "base_workdir": "/workspace/project",
            "default_workspace_policy": "worktree",
            "default_execution_engine": "codex",
            "folder_access": "full_access",
            "project_dir": "/tmp/budgetloop-project",
            "full_access_acknowledged": True,
            "start_immediately": False,
        },
    )
    assert response.status_code == 422
    assert "OpenHands" in response.json()["detail"]


@pytest.mark.parametrize(
    "fields",
    [
        {"folder_access": "full_access", "default_workspace_policy": "worktree"},
        {
            "folder_access": "full_access",
            "project_dir": "/tmp/project",
            "default_workspace_policy": "worktree",
        },
        {
            "folder_access": "full_access",
            "project_dir": "/tmp/project",
            "full_access_acknowledged": True,
            "default_workspace_policy": "isolated",
        },
        {"folder_access": "isolated", "full_access_acknowledged": True},
        {
            "folder_access": "full_access",
            "project_dir": "/etc/project",
            "full_access_acknowledged": True,
            "default_workspace_policy": "worktree",
        },
    ],
)
def test_full_access_team_rejects_incomplete_or_unsafe_policy(client, fields):
    c, _ = client
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": f"team-unsafe-{uuid.uuid4()}"},
        json={
            "preset_id": "software-delivery",
            "preset_version": 1,
            "name": "不安全团队",
            "project_goal": "验证权限策略会在创建前拒绝",
            "base_workdir": "/workspace/project",
            "start_immediately": False,
            **fields,
        },
    )
    assert response.status_code == 422


def test_create_team_applies_bounded_overrides_and_starts_in_sop_order(client, pg_session):
    c, enqueued = client
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-general-001"},
        json={
            "preset_id": "general-project",
            "preset_version": 1,
            "name": "门店改造",
            "project_goal": "规划并验证门店服务流程改造",
            "base_workdir": "/workspace/business",
            "default_workspace_policy": "isolated",
            "role_overrides": [
                {
                    "key": "specialist",
                    "role": "零售流程专家",
                    "goal": "产出门店流程蓝图",
                    "budget": {"max_total_tokens": 12345, "max_llm_calls": 7},
                },
                {"key": "research", "enabled": True},
            ],
            "start_immediately": True,
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["dispatch"]["warnings"] == []
    assert result["dispatch"]["accepted"] == enqueued
    assert len(enqueued) == 4
    specialist = next(item for item in result["container"]["sessions"] if item["role"] == "零售流程专家")
    budget = pg_session.get(TaskBudget, uuid.UUID(specialist["current_run_id"]))
    assert budget is not None
    assert budget.max_total_tokens == 12345
    assert budget.max_llm_calls == 7
    stored_session = pg_session.get(WorkSession, uuid.UUID(specialist["id"]))
    assert stored_session is not None
    assert "不会授予额外工具、权限" in stored_session.private_context


def test_preset_creation_rejects_missing_key_unknown_roles_and_unsafe_bounds(client):
    c, _ = client
    base = {
        "preset_id": "general-project",
        "preset_version": 1,
        "name": "项目",
        "project_goal": "完成一个明确项目",
        "base_workdir": "/workspace/project",
    }
    assert c.post("/api/work-containers/from-preset", headers=AUTH, json=base).status_code == 422
    unknown = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-invalid-01"},
        json={**base, "role_overrides": [{"key": "root", "enabled": True}]},
    )
    assert unknown.status_code == 422
    over_budget = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-invalid-02"},
        json={
            **base,
            "role_overrides": [{"key": "specialist", "budget": {"max_total_tokens": 999_999}}],
        },
    )
    assert over_budget.status_code == 422
    too_small = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-invalid-03"},
        json={
            **base,
            "role_overrides": [
                {"key": "lead", "enabled": False},
                {"key": "reviewer", "enabled": False},
            ],
        },
    )
    assert too_small.status_code == 422


def test_preset_dispatch_failure_is_truthful_and_retryable(client, monkeypatch):
    c, _ = client

    def unavailable(_run_id: str):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(broker, "enqueue_run", unavailable)
    response = c.post(
        "/api/work-containers/from-preset",
        headers={**AUTH, "Idempotency-Key": "team-queue-failure"},
        json={
            "preset_id": "software-delivery",
            "preset_version": 1,
            "name": "离线队列验证",
            "project_goal": "验证队列故障不会伪装成启动成功",
            "base_workdir": "/workspace/software",
            "start_immediately": True,
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert result["dispatch"]["accepted"] == []
    assert len(result["dispatch"]["warnings"]) == 5
    assert {item["status"] for item in result["container"]["sessions"]} == {"PENDING"}

    accepted: list[str] = []
    monkeypatch.setattr(broker, "enqueue_run", lambda run_id: accepted.append(run_id))
    retry = c.post(f"/api/work-containers/{result['container']['id']}/start", headers=AUTH)
    assert retry.status_code == 200
    assert retry.json()["warnings"] == []
    assert retry.json()["accepted"] == accepted
    assert len(accepted) == 5


def test_preset_creation_rolls_back_all_records_on_mid_transaction_failure(pg_engine, monkeypatch):
    from sqlalchemy.orm import Session

    import app.api.team_presets as preset_api

    original = preset_api._create_work_session_records
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected creation failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(preset_api, "_create_work_session_records", fail_second)

    def isolated_db():
        with Session(pg_engine) as database:
            try:
                yield database
            finally:
                database.rollback()

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, raise_server_exceptions=False) as isolated_client:
            response = isolated_client.post(
                "/api/work-containers/from-preset",
                headers={**AUTH, "Idempotency-Key": "team-atomic-failure"},
                json={
                    "preset_id": "game-development",
                    "preset_version": 1,
                    "name": "原子失败验证",
                    "project_goal": "中途失败时不留下半支团队",
                    "base_workdir": "/workspace/atomic",
                },
            )
            assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()

    with Session(pg_engine) as database:
        assert database.query(WorkContainer).filter_by(idempotency_key="team-atomic-failure").count() == 0
        assert database.query(Task).filter(Task.name.like("原子失败验证%")).count() == 0
