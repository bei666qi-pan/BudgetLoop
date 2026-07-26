"""API 集成测试：TestClient + testcontainers PG + 假 broker。"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")  # 必须在 import app.main 之前

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.models import Approval, Task, TaskRun, WorkContainer, WorkSession  # noqa: E402
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
    with TestClient(app) as c:
        yield c, enqueued
    app.dependency_overrides.clear()


def _create_task(client: TestClient, key: str | None = None, **overrides) -> dict:
    body = {"name": "修复库存并发扣减", "description": "...", "workdir": "/workspace/project"}
    body.update(overrides)
    headers = dict(AUTH)
    if key:
        headers["Idempotency-Key"] = key
    resp = client.post("/api/tasks", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health_no_auth(client):
    c, _ = client
    assert c.get("/api/health").json() == {"status": "ok"}


def test_auth_required(client):
    c, _ = client
    assert c.get("/api/tasks").status_code == 401
    assert c.get("/api/tasks", headers=AUTH).status_code == 200


def test_create_task_and_idempotency(client):
    c, enqueued = client
    first = _create_task(c, key="k-1", budget={"max_total_tokens": 5000, "max_llm_calls": 3})
    assert first["task_id"] and first["run_id"]
    assert enqueued == [first["run_id"]]

    # 重复提交同一 Idempotency-Key 返回同一任务，不再入队
    second = _create_task(c, key="k-1", name="另一个名字")
    assert second["task_id"] == first["task_id"]
    assert second["run_id"] == first["run_id"]
    assert len(enqueued) == 1

    # 不带 key 是新任务
    third = _create_task(c)
    assert third["task_id"] != first["task_id"]


def test_create_task_broker_down_still_creates(client, pg_session, monkeypatch):
    c, _ = client

    def boom(run_id):
        raise ConnectionError("redis down")

    monkeypatch.setattr(broker, "enqueue_run", boom)
    data = _create_task(c)
    assert "warning" in data
    run = c.get(f"/api/runs/{data['run_id']}", headers=AUTH).json()["run"]
    assert run["status"] == "PENDING"


def test_run_aggregate(client):
    c, _ = client
    data = _create_task(c, budget={"max_total_tokens": 5000, "max_llm_calls": 3, "max_cost": 2.0})
    resp = c.get(f"/api/runs/{data['run_id']}", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["status"] == "PENDING"
    assert body["run"]["attempt_no"] == 1
    assert body["task"]["name"] == "修复库存并发扣减"
    assert body["task"]["acceptance_criteria"]  # 空则生成默认标准
    budget = body["budget"]
    assert budget["max_total_tokens"] == 5000
    assert budget["remaining_tokens"] == 5000
    assert budget["projected_tokens"] == 0


def test_second_run_increments_attempt(client):
    c, _ = client
    data = _create_task(c)
    resp = c.post(
        f"/api/tasks/{data['task_id']}/runs",
        json={"strategy": "fixed", "model_config": {"model": "x"}},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["attempt_no"] == 2
    run = c.get(f"/api/runs/{resp.json()['run_id']}", headers=AUTH).json()["run"]
    assert run["strategy"] == "fixed"
    assert run["model_config"] == {"model": "x"}


def test_list_tasks_includes_latest_run(client):
    c, _ = client
    data = _create_task(c)
    tasks = c.get("/api/tasks", headers=AUTH).json()["tasks"]
    item = next(t for t in tasks if t["id"] == data["task_id"])
    assert item["latest_run"]["status"] == "PENDING"
    assert item["latest_run"]["used_tokens"] == 0


def test_delete_terminal_standalone_task_history(client, pg_session):
    c, _ = client
    data = _create_task(c)
    run = pg_session.get(TaskRun, uuid.UUID(data["run_id"]))
    run.status = "COMPLETED"
    pg_session.commit()

    response = c.delete(f"/api/tasks/{data['task_id']}", headers=AUTH)
    assert response.status_code == 204, response.text
    pg_session.expire_all()
    assert pg_session.get(Task, uuid.UUID(data["task_id"])) is None
    assert pg_session.get(TaskRun, uuid.UUID(data["run_id"])) is None


def test_delete_task_history_rejects_missing_and_active(client):
    c, _ = client
    assert c.delete(f"/api/tasks/{uuid.uuid4()}", headers=AUTH).status_code == 404
    data = _create_task(c)
    response = c.delete(f"/api/tasks/{data['task_id']}", headers=AUTH)
    assert response.status_code == 409
    assert c.get("/api/tasks", headers=AUTH).json()["tasks"]


def test_delete_task_history_rejects_team_owned_task(client, pg_session):
    c, _ = client
    data = _create_task(c)
    task_id = uuid.UUID(data["task_id"])
    run_id = uuid.UUID(data["run_id"])
    run = pg_session.get(TaskRun, run_id)
    run.status = "COMPLETED"
    container = WorkContainer(
        name="team",
        project_goal="goal",
        shared_context="",
        base_workdir="/workspace/project",
    )
    pg_session.add(container)
    pg_session.flush()
    pg_session.add(
        WorkSession(
            container_id=container.id,
            role="developer",
            goal="implement",
            task_id=task_id,
            current_run_id=run_id,
        )
    )
    pg_session.commit()
    assert c.delete(f"/api/tasks/{task_id}", headers=AUTH).status_code == 409
    assert pg_session.get(Task, task_id) is not None


def test_delete_task_history_rolls_back_on_statement_failure(client, pg_session, monkeypatch):
    c, _ = client
    data = _create_task(c)
    task_id = uuid.UUID(data["task_id"])
    run = pg_session.get(TaskRun, uuid.UUID(data["run_id"]))
    run.status = "COMPLETED"
    pg_session.commit()

    original_rollback = pg_session.rollback
    rolled_back = False

    def observed_rollback():
        nonlocal rolled_back
        rolled_back = True
        original_rollback()

    monkeypatch.setattr(pg_session, "rollback", observed_rollback)
    monkeypatch.setattr(
        "app.api.tasks.delete",
        lambda _model: (_ for _ in ()).throw(RuntimeError("fail")),
    )
    assert c.delete(f"/api/tasks/{task_id}", headers=AUTH).status_code == 409
    assert rolled_back is True


def test_pause_cancel_idempotent(client):
    c, _ = client
    run_id = _create_task(c)["run_id"]

    r1 = c.post(f"/api/runs/{run_id}/pause", headers=AUTH).json()
    assert r1["status"] == "PAUSED" and r1["changed"] is True
    r2 = c.post(f"/api/runs/{run_id}/pause", headers=AUTH).json()
    assert r2["status"] == "PAUSED" and r2["changed"] is False

    r3 = c.post(f"/api/runs/{run_id}/cancel", headers=AUTH).json()
    assert r3["status"] == "CANCELLED" and r3["changed"] is True
    # 终态后不可再操作，幂等返回当前状态
    r4 = c.post(f"/api/runs/{run_id}/pause", headers=AUTH).json()
    assert r4["status"] == "CANCELLED" and r4["changed"] is False


def test_events_replay_after_seq(client):
    c, _ = client
    run_id = _create_task(c)["run_id"]

    events = c.get(f"/api/runs/{run_id}/events", params={"after_seq": 0}, headers=AUTH).json()["events"]
    assert [e["type"] for e in events] == ["run_started"]
    seq = events[0]["seq"]

    assert c.get(f"/api/runs/{run_id}/events", params={"after_seq": seq}, headers=AUTH).json()["events"] == []

    c.post(f"/api/runs/{run_id}/pause", headers=AUTH)
    new_events = c.get(f"/api/runs/{run_id}/events", params={"after_seq": seq}, headers=AUTH).json()["events"]
    assert [e["type"] for e in new_events] == ["state_changed"]
    assert all(e["seq"] > seq for e in new_events)


def test_budget_endpoint(client):
    c, _ = client
    run_id = _create_task(c)["run_id"]
    body = c.get(f"/api/runs/{run_id}/budget", headers=AUTH).json()
    assert body["budget"]["remaining_calls"] == 20
    assert len(body["phases"]) == 6
    assert {p["phase"] for p in body["phases"]} == {
        "scan", "analyze", "modify", "verify", "repair", "summarize",
    }
    assert body["reallocations"] == []


def test_approval_decide_idempotent(client, pg_session):
    c, _ = client
    run_id = _create_task(c)["run_id"]
    approval = Approval(
        run_id=run_id, action_type="delete_file", description="删除 build/", payload={}
    )
    pg_session.add(approval)
    pg_session.commit()

    r1 = c.post(
        f"/api/approvals/{approval.id}/decide",
        json={"action": "approve", "note": "ok"},
        headers=AUTH,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "approved" and r1.json()["changed"] is True
    assert r1.json()["decided_at"] is not None

    # 已决策后重复 decide（即使不同 action）返回当前状态
    r2 = c.post(
        f"/api/approvals/{approval.id}/decide",
        json={"action": "reject"},
        headers=AUTH,
    ).json()
    assert r2["status"] == "approved" and r2["changed"] is False

    # 决策事件已入 outbox
    events = c.get(f"/api/runs/{run_id}/events", headers=AUTH).json()["events"]
    assert "approval_decided" in [e["type"] for e in events]


def test_report_404(client):
    c, _ = client
    run_id = _create_task(c)["run_id"]
    assert c.get(f"/api/runs/{run_id}/report", headers=AUTH).status_code == 404
    assert c.get(f"/api/runs/{run_id}/report/export", headers=AUTH).status_code == 404


# ---------------------------------------------------------------------------
# folder_access / project_dir（mac-launcher-folder-access）
# ---------------------------------------------------------------------------


def _post_task(c: TestClient, **overrides):
    body = {"name": "目录权限任务", "workdir": "/workspace/project"}
    body.update(overrides)
    return c.post("/api/tasks", json=body, headers=AUTH)


def test_full_access_without_project_dir_422(client):
    c, _ = client
    resp = _post_task(c, folder_access="full_access")
    assert resp.status_code == 422


def test_project_dir_relative_path_422(client):
    c, _ = client
    resp = _post_task(c, folder_access="full_access", project_dir="relative/path")
    assert resp.status_code == 422
    resp = _post_task(c, folder_access="full_access", project_dir="~/project")
    assert resp.status_code == 422
    resp = _post_task(c, folder_access="full_access", project_dir="/tmp/../etc")
    assert resp.status_code == 422


def test_project_dir_sensitive_roots_422(client):
    c, _ = client
    for path in ("/", "/System", "/System/x", "/usr/local", "/etc/ssl", "/private/tmp/x"):
        resp = _post_task(c, folder_access="full_access", project_dir=path)
        assert resp.status_code == 422, path


def test_project_dir_home_itself_422(client):
    c, _ = client
    home = os.path.expanduser("~")
    resp = _post_task(c, folder_access="full_access", project_dir=home)
    assert resp.status_code == 422
    # 家目录下的子目录是允许的
    resp = _post_task(c, folder_access="full_access", project_dir=f"{home}/budgetloop-e2e")
    assert resp.status_code == 201, resp.text


def test_full_access_persists_into_run_model_config(client):
    c, _ = client
    resp = _post_task(
        c,
        folder_access="full_access",
        project_dir="/tmp/budgetloop-project/",  # 尾斜杠应被归一化
    )
    assert resp.status_code == 201, resp.text
    run = c.get(f"/api/runs/{resp.json()['run_id']}", headers=AUTH).json()["run"]
    assert run["model_config"]["folder_access"] == "full_access"
    assert run["model_config"]["project_dir"] == "/tmp/budgetloop-project"


def test_default_folder_access_stays_isolated(client):
    c, _ = client
    data = _create_task(c)
    run = c.get(f"/api/runs/{data['run_id']}", headers=AUTH).json()["run"]
    assert run["model_config"].get("folder_access", "isolated") == "isolated"


def test_invalid_folder_access_value_422(client):
    c, _ = client
    resp = _post_task(c, folder_access="yolo", project_dir="/tmp/x")
    assert resp.status_code == 422
