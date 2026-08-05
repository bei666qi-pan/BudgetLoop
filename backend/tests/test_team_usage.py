"""Team usage aggregation tests — real PostgreSQL integration.

Coverage targets:
- Aggregation correctness (SUM of per-session == team aggregate)
- Reserved exclusion for terminal sessions
- Pressure mode bounds
- Missing/null field handling
- Consumption rate computation
- No double-counting
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone as tz

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.enums import ContainerLifecycle, RunStatus  # noqa: E402
from app.core.models import (  # noqa: E402
    LlmCall,
    Task,
    TaskBudget,
    TaskRun,
    WorkContainer,
    WorkSession,
    utcnow,
)
from app.main import app  # noqa: E402
from tests.conftest import requires_docker  # noqa: E402

pytestmark = requires_docker
AUTH = {"Authorization": f"Bearer {settings.api_token}"}


# --------------------------------------------------------------------------- --
# fixtures
# --------------------------------------------------------------------------- --


@pytest.fixture()
def client(pg_session):
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def empty_container(client, pg_session):
    """Container with no sessions (baseline)."""
    container = WorkContainer(
        name="empty team",
        project_goal="baseline",
        base_workdir="/workspace/empty",
        lifecycle_state=ContainerLifecycle.ACTIVE.value,
    )
    pg_session.add(container)
    pg_session.commit()
    pg_session.refresh(container)
    return container


_DEFAULT_BUDGET = {
    "max_total_tokens": 100_000,
    "max_wall_time_seconds": 1200,
    "max_active_runtime_seconds": 600,
    "max_llm_calls": 20,
    "max_cost": 5.0,
    "max_parallel_llm_calls": 2,
    "used_tokens": 10_000,
    "used_cost": 0.5,
    "used_calls": 3,
    "reserved_tokens": 0,
    "reserved_cost": 0.0,
    "reserved_calls": 0,
}


def _make_task_run_budget(
    pg_session,
    *,
    status: str = "EXECUTING",
    budget_kw: dict | None = None,
    run_kw: dict | None = None,
    **budget_overrides,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create Task + TaskRun + TaskBudget; return (run_id, task_id).

    Budget fields can be passed directly as kwargs (e.g. used_tokens=5000)
    or via budget_kw dict. Direct kwargs take precedence.
    """
    task = Task(
        name=f"测试任务-{uuid.uuid4().hex[:6]}",
        description="自动化测试任务",
        workdir="/workspace/test",
    )
    pg_session.add(task)
    pg_session.flush()

    run_defaults = {"status": status}
    if run_kw:
        run_defaults.update(run_kw)
    run = TaskRun(task_id=task.id, **run_defaults)
    pg_session.add(run)
    pg_session.flush()

    budget_defaults = dict(_DEFAULT_BUDGET)
    if budget_kw:
        budget_defaults.update(budget_kw)
    budget_defaults.update(budget_overrides)
    pg_session.add(TaskBudget(run_id=run.id, **budget_defaults))
    pg_session.commit()

    return run.id, task.id


def _make_session(
    pg_session,
    container: WorkContainer,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    *,
    role: str = "测试Session",
    status: str = "RUNNING",
) -> WorkSession:
    ws = WorkSession(
        container_id=container.id,
        role=role,
        goal="测试目标",
        task_id=task_id,
        current_run_id=run_id,
        status=status,
    )
    pg_session.add(ws)
    pg_session.commit()
    pg_session.refresh(ws)
    return ws


def _make_llm_call(
    pg_session,
    run_id: uuid.UUID,
    *,
    total_tokens: int = 1000,
    prompt_tokens: int = 600,
    completion_tokens: int = 300,
    reasoning_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    estimated_cost: float | None = 0.01,
    ttft_ms: int | None = None,
    started_at: datetime | None = None,
) -> LlmCall:
    call = LlmCall(
        run_id=run_id,
        call_id=str(uuid.uuid4()),
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        estimated_cost=estimated_cost,
        ttft_ms=ttft_ms,
        started_at=started_at,
        model="test-model",
        provider="test-provider",
    )
    pg_session.add(call)
    pg_session.commit()
    pg_session.refresh(call)
    return call


# --------------------------------------------------------------------------- --
# tests
# --------------------------------------------------------------------------- --


class TestUsageAggregationCorrectness:
    """Verify team aggregate equals simple SUM of per-session used_* fields."""

    def test_team_aggregate_sums_per_session(self, client, pg_session):
        container = WorkContainer(
            name="agg test",
            project_goal="verify aggregation",
            base_workdir="/workspace/agg",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        # session 1: 10k used
        r1, t1 = _make_task_run_budget(
            pg_session,
            used_tokens=10_000,
            used_cost=0.5,
            used_calls=3,
            max_total_tokens=50_000,
        )
        ws1 = _make_session(pg_session, container, r1, t1, role="前端开发")

        # session 2: 5k used
        r2, t2 = _make_task_run_budget(
            pg_session,
            used_tokens=5_000,
            used_cost=0.3,
            used_calls=2,
            max_total_tokens=30_000,
        )
        ws2 = _make_session(pg_session, container, r2, t2, role="后端实现")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        agg = data["aggregate"]
        assert agg["used"]["tokens"] == 15_000  # 10000 + 5000
        assert round(agg["used"]["cost"], 2) == 0.80  # 0.5 + 0.3
        assert agg["used"]["calls"] == 5  # 3 + 2
        assert agg["max"]["tokens"] == 80_000  # 50000 + 30000

        # per_session breakdown count
        assert len(data["per_session"]) == 2

        # verify per_session entries
        session_ids = {s["session_id"] for s in data["per_session"]}
        assert str(ws1.id) in session_ids
        assert str(ws2.id) in session_ids

    def test_used_only_from_budget_not_llm_calls(self, client, pg_session):
        """Team aggregate uses budget.used_* — not llm_calls totals."""
        container = WorkContainer(
            name="budget-only test",
            project_goal="budget source of truth",
            base_workdir="/workspace/budget",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r1, t1 = _make_task_run_budget(
            pg_session,
            used_tokens=7_000,
            used_cost=0.35,
            used_calls=2,
        )
        _make_session(pg_session, container, r1, t1, role="测试")

        # create llm_calls that exceed the budget used_* — they should not affect aggregate
        for _ in range(10):
            _make_llm_call(pg_session, r1, total_tokens=5000)

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # aggregate should still be 7000, not 50000 from llm_calls
        assert data["aggregate"]["used"]["tokens"] == 7_000
        assert data["aggregate"]["used"]["calls"] == 2

        # but token_sub_types should reflect llm_calls data
        sub = data["token_sub_types"]
        assert sub["prompt"] == 10 * 600
        assert sub["completion"] == 10 * 300


class TestReservedExclusionForTerminal:
    """reserved_* from terminal sessions must be excluded from team aggregate."""

    def test_terminal_sessions_excluded_from_reserved(self, client, pg_session):
        container = WorkContainer(
            name="terminal test",
            project_goal="exclude terminal",
            base_workdir="/workspace/term",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        # active session with reserved
        r1, t1 = _make_task_run_budget(
            pg_session,
            status="EXECUTING",
            reserved_tokens=2000,
            reserved_cost=0.1,
            reserved_calls=1,
        )
        ws1 = _make_session(pg_session, container, r1, t1, role="活跃", status="RUNNING")

        # completed session with reserved — should be EXCLUDED
        r2, t2 = _make_task_run_budget(
            pg_session,
            status="COMPLETED",
            reserved_tokens=5000,
            reserved_cost=0.3,
            reserved_calls=2,
        )
        ws2 = _make_session(pg_session, container, r2, t2, role="已完成", status="COMPLETED")

        # failed session with reserved — should be EXCLUDED
        r3, t3 = _make_task_run_budget(
            pg_session,
            status="FAILED",
            reserved_tokens=3000,
            reserved_cost=0.2,
            reserved_calls=1,
        )
        ws3 = _make_session(pg_session, container, r3, t3, role="已失败", status="FAILED")

        # cancelled session with reserved — should be EXCLUDED
        r4, t4 = _make_task_run_budget(
            pg_session,
            status="CANCELLED",
            reserved_tokens=1000,
            reserved_cost=0.05,
            reserved_calls=0,
        )
        ws4 = _make_session(pg_session, container, r4, t4, role="已取消", status="CANCELLED")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # only active session reserved counts
        assert data["aggregate"]["reserved"]["tokens"] == 2000
        assert data["aggregate"]["reserved"]["calls"] == 1

        # used_* from terminal sessions still counts (actual consumption)
        assert data["aggregate"]["used"]["tokens"] == 40_000  # 4 * 10000
        assert data["aggregate"]["used"]["calls"] == 12  # 4 * 3

        # check per_session: terminal sessions show reserved as 0
        for s in data["per_session"]:
            if s["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                assert s["reserved"]["tokens"] == 0
                assert s["reserved"]["cost"] == 0.0
                assert s["reserved"]["calls"] == 0

    def test_budget_exhausted_excluded_from_reserved(self, client, pg_session):
        container = WorkContainer(
            name="exhausted test",
            project_goal="exclude exhausted",
            base_workdir="/workspace/exhaust",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r1, t1 = _make_task_run_budget(
            pg_session,
            status="BUDGET_EXHAUSTED",
            reserved_tokens=4000,
        )
        _make_session(pg_session, container, r1, t1, role="耗尽", status="BUDGET_EXHAUSTED")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["aggregate"]["reserved"]["tokens"] == 0


class TestPressureModeBounds:
    """Team pressure mode = worst of all active session pressure modes."""

    def test_all_normal_yields_normal(self, client, pg_session):
        container = WorkContainer(
            name="normal team",
            project_goal="all normal",
            base_workdir="/workspace/normal",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        now = utcnow()
        for i in range(3):
            r, t = _make_task_run_budget(
                pg_session,
                status="EXECUTING",
                max_total_tokens=100_000,
                max_active_runtime_seconds=600,
                used_tokens=10_000,  # 90% remaining
                run_kw={
                    "active_runtime_ms": 100_000,  # ~16% of 600s
                    "deadline_at": now + timedelta(seconds=1000),
                },
            )
            _make_session(pg_session, container, r, t, role=f"session-{i}")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["team_pressure_mode"] == "NORMAL"

    def test_one_critical_yields_critical(self, client, pg_session):
        container = WorkContainer(
            name="critical team",
            project_goal="one critical",
            base_workdir="/workspace/crit",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        now = utcnow()

        # normal session
        r1, t1 = _make_task_run_budget(
            pg_session,
            status="EXECUTING",
            max_total_tokens=100_000,
            max_active_runtime_seconds=600,
            used_tokens=10_000,
            run_kw={
                "active_runtime_ms": 100_000,
                "deadline_at": now + timedelta(seconds=1000),
            },
        )
        _make_session(pg_session, container, r1, t1, role="正常")

        # critical session: active almost exhausted
        r2, t2 = _make_task_run_budget(
            pg_session,
            status="EXECUTING",
            max_total_tokens=100_000,
            max_active_runtime_seconds=600,
            used_tokens=95_000,  # nearly exhausted
            run_kw={
                "active_runtime_ms": 590_000,  # almost all 600s used
                "deadline_at": now + timedelta(seconds=10),
            },
        )
        _make_session(pg_session, container, r2, t2, role="紧张")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["team_pressure_mode"] == "CRITICAL"

    def test_conservative_edge(self, client, pg_session):
        """Token ratio < 0.2 should escalate from NORMAL to CONSERVATIVE."""
        container = WorkContainer(
            name="conservative team",
            project_goal="token tense",
            base_workdir="/workspace/cons",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        now = utcnow()
        # wall and active are fine, but tokens are tight
        r, t = _make_task_run_budget(
            pg_session,
            status="EXECUTING",
            max_total_tokens=100_000,
            max_active_runtime_seconds=600,
            used_tokens=85_000,  # 15% remaining — below 20% threshold
            run_kw={
                "active_runtime_ms": 100_000,
                "deadline_at": now + timedelta(seconds=1000),
            },
        )
        _make_session(pg_session, container, r, t, role="代币紧张")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["team_pressure_mode"] == "CONSERVATIVE"

    def test_terminal_sessions_not_in_pressure_calc(self, client, pg_session):
        """Completed/failed sessions should not affect team pressure mode."""
        container = WorkContainer(
            name="terminal pressure",
            project_goal="terminal ignore",
            base_workdir="/workspace/termp",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        now = utcnow()

        # completed session with terrible stats
        r1, t1 = _make_task_run_budget(
            pg_session,
            status="COMPLETED",
            max_total_tokens=100_000,
            max_active_runtime_seconds=600,
            used_tokens=99_000,
            run_kw={
                "active_runtime_ms": 590_000,
                "deadline_at": now - timedelta(seconds=10),
            },
        )
        _make_session(pg_session, container, r1, t1, role="已完成", status="COMPLETED")

        # active session with healthy stats
        r2, t2 = _make_task_run_budget(
            pg_session,
            status="EXECUTING",
            max_total_tokens=100_000,
            max_active_runtime_seconds=600,
            used_tokens=10_000,
            run_kw={
                "active_runtime_ms": 100_000,
                "deadline_at": now + timedelta(seconds=1000),
            },
        )
        _make_session(pg_session, container, r2, t2, role="正常活跃")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Should be NORMAL because only active session counts
        assert data["team_pressure_mode"] == "NORMAL"


class TestMissingFieldNulls:
    """Optional fields (estimated_cost, ttft_ms, cache tokens) must return null, never 0."""

    def test_token_sub_types_respect_nulls(self, client, pg_session):
        container = WorkContainer(
            name="null test",
            project_goal="null handling",
            base_workdir="/workspace/null",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session)
        _make_session(pg_session, container, r, t, role="null-test")

        # Create llm calls where some have NULL optional fields
        # First call: complete data
        _make_llm_call(
            pg_session,
            r,
            total_tokens=1000,
            prompt_tokens=500,
            completion_tokens=400,
            reasoning_tokens=50,
            cache_read_tokens=30,
            cache_write_tokens=20,
            estimated_cost=0.01,
            ttft_ms=200,
        )
        # Second call: missing reasonin_g and cache
        _make_llm_call(
            pg_session,
            r,
            total_tokens=500,
            prompt_tokens=300,
            completion_tokens=200,
            reasoning_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            estimated_cost=None,
            ttft_ms=None,
        )

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # token_sub_types: SQL COALESCE with 0, so NULLs are interpreted as 0 in aggregation
        # But the sub-types are from COALESCE(SUM(...), 0), so individual NULLs default to 0
        sub = data["token_sub_types"]
        assert sub["prompt"] == 800  # 500 + 300
        assert sub["completion"] == 600  # 400 + 200
        # reasoning: only 50 from first call (second call NULL → treated as 0 by COALESCE)
        assert sub["reasoning"] == 50
        assert sub["cache_read"] == 30
        assert sub["cache_write"] == 20

    def test_empty_container_returns_zeros_for_sums_none_for_consumption(
        self, client, empty_container
    ):
        resp = client.get(
            f"/api/work-containers/{empty_container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["aggregate"]["used"]["tokens"] == 0
        assert data["aggregate"]["used"]["cost"] == 0
        assert data["aggregate"]["used"]["calls"] == 0
        assert data["consumption"]["rate_calls_per_minute"] == 0.0
        assert data["consumption"]["estimated_depletion_seconds"] is None

    def test_cost_none_in_budget_handled(self, client, pg_session):
        """If budget used_cost is absent, should default to 0.0 via Python, not None."""
        container = WorkContainer(
            name="cost-none",
            project_goal="cost null",
            base_workdir="/workspace/cost",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        # Create a budget with used_cost explicitly set
        r, t = _make_task_run_budget(
            pg_session,
            used_cost=0.0,
            max_cost=1.0,
        )
        _make_session(pg_session, container, r, t, role="min-cost")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["aggregate"]["used"]["cost"] == 0.0


class TestConsumptionRate:
    """Trailing 5-minute llm_calls are used to compute consumption rate."""

    def test_consumption_rate_from_trailing_window(self, client, pg_session):
        container = WorkContainer(
            name="rate test",
            project_goal="consumption rate",
            base_workdir="/workspace/rate",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session)
        _make_session(pg_session, container, r, t, role="rate-session")

        now = utcnow()

        # 10 calls in the last 5 minutes
        for i in range(10):
            _make_llm_call(
                pg_session,
                r,
                total_tokens=1000,
                prompt_tokens=600,
                completion_tokens=400,
                started_at=now - timedelta(minutes=2),  # within window
            )

        # 5 calls older than 5 minutes
        for i in range(5):
            _make_llm_call(
                pg_session,
                r,
                total_tokens=500,
                prompt_tokens=300,
                completion_tokens=200,
                started_at=now - timedelta(minutes=10),  # outside window
            )

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # 10 calls in 5 minutes → 2.0 calls/min
        rate = data["consumption"]["rate_calls_per_minute"]
        assert rate == 2.0  # 10 / 5

    def test_depletion_time_computation(self, client, pg_session):
        container = WorkContainer(
            name="depletion test",
            project_goal="depletion time",
            base_workdir="/workspace/deplet",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(
            pg_session,
            used_tokens=50_000,
            max_total_tokens=100_000,
        )
        _make_session(pg_session, container, r, t, role="depletion")

        now = utcnow()

        # 10 calls in window, each 2000 tokens → 20k tokens total
        for _ in range(10):
            _make_llm_call(
                pg_session,
                r,
                total_tokens=2000,
                prompt_tokens=1200,
                completion_tokens=800,
                started_at=now - timedelta(minutes=2),
            )

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # remaining = 50000 tokens, rate = 4000 tokens/min (2000*10/5)
        # calls_remaining = 50000 / 2000 = 25 calls
        # minutes_remaining = 25 / 2.0 = 12.5 min
        # seconds = 12.5 * 60 = 750
        depletion = data["consumption"]["estimated_depletion_seconds"]
        assert depletion is not None
        assert depletion == 750

    def test_no_calls_zero_depletion(self, client, pg_session):
        container = WorkContainer(
            name="no calls",
            project_goal="zero depletion",
            base_workdir="/workspace/no-calls",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session)
        _make_session(pg_session, container, r, t, role="inactive")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["consumption"]["rate_calls_per_minute"] == 0.0
        # No consumption → no depletion estimate
        assert data["consumption"]["estimated_depletion_seconds"] is None


class TestNoDoubleCounting:
    """Each llm_call is settled exactly once by the worker into task_budget.used_*."""

    def test_budget_is_calls_settled_llm_calls_are_raw_log(self, client, pg_session):
        container = WorkContainer(
            name="nodedup test",
            project_goal="no double count",
            base_workdir="/workspace/nodup",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(
            pg_session,
            used_tokens=5_000,
            used_cost=0.25,
            used_calls=1,
            max_total_tokens=20_000,
        )
        _make_session(pg_session, container, r, t, role="settled")

        # raw llm_calls shows 3 calls, budget only settled 1 — worker is behind
        for _ in range(3):
            _make_llm_call(pg_session, r, total_tokens=2000)

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # used = from budget (settled), not from llm_calls sum
        assert data["aggregate"]["used"]["tokens"] == 5_000
        assert data["aggregate"]["used"]["calls"] == 1
        # token_sub_types = from llm_calls raw data (for detail breakdown)
        assert data["token_sub_types"]["prompt"] == 3 * 600
        assert data["token_sub_types"]["completion"] == 3 * 300

    def test_two_sessions_each_settled_independently(self, client, pg_session):
        container = WorkContainer(
            name="two session",
            project_goal="independent settle",
            base_workdir="/workspace/two",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r1, t1 = _make_task_run_budget(
            pg_session,
            used_tokens=3_000,
            used_calls=2,
        )
        _make_session(pg_session, container, r1, t1, role="session-A")

        r2, t2 = _make_task_run_budget(
            pg_session,
            used_tokens=7_000,
            used_calls=4,
        )
        _make_session(pg_session, container, r2, t2, role="session-B")

        resp = client.get(
            f"/api/work-containers/{container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # simple SUM, not SUM+duplicate or other aggregation
        assert data["aggregate"]["used"]["tokens"] == 10_000
        assert data["aggregate"]["used"]["calls"] == 6


class TestContainersExtension:
    """GET /api/containers includes team_status, active_session_count, alert_count."""

    def test_extended_container_list(self, client, pg_session):
        container = WorkContainer(
            name="extended test",
            project_goal="extension",
            base_workdir="/workspace/ext",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        # active session
        r1, t1 = _make_task_run_budget(pg_session, status="EXECUTING")
        _make_session(pg_session, container, r1, t1, role="running")

        # failed session
        r2, t2 = _make_task_run_budget(pg_session, status="FAILED")
        _make_session(pg_session, container, r2, t2, role="failed", status="FAILED")

        resp = client.get("/api/containers", headers=AUTH)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        containers = data["containers"]
        assert len(containers) >= 1

        our = [c for c in containers if c["id"] == str(container.id)]
        assert len(our) == 1
        item = our[0]

        assert item["team_status"] is not None
        assert item["active_session_count"] == 1  # failed is terminal, so only 1 active
        assert item["alert_count"] == 1  # one failed session

    def test_team_status_running(self, client, pg_session):
        container = WorkContainer(
            name="running team",
            project_goal="status running",
            base_workdir="/workspace/run",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session, status="EXECUTING")
        _make_session(pg_session, container, r, t, role="runner")

        resp = client.get("/api/containers", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()
        our = [c for c in data["containers"] if c["id"] == str(container.id)][0]
        assert our["team_status"] == "running"

    def test_team_status_paused_container(self, client, pg_session):
        container = WorkContainer(
            name="paused team",
            project_goal="paused",
            base_workdir="/workspace/paused",
            lifecycle_state=ContainerLifecycle.PAUSED.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session, status="PAUSED")
        _make_session(pg_session, container, r, t, role="paused", status="PAUSED")

        resp = client.get("/api/containers", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()
        our = [c for c in data["containers"] if c["id"] == str(container.id)][0]
        assert our["team_status"] == "paused"

    def test_team_status_attention(self, client, pg_session):
        container = WorkContainer(
            name="attention team",
            project_goal="needs attention",
            base_workdir="/workspace/attn",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session, status="FAILED")
        _make_session(pg_session, container, r, t, role="broken", status="FAILED")

        resp = client.get("/api/containers", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()
        our = [c for c in data["containers"] if c["id"] == str(container.id)][0]
        assert our["team_status"] == "attention"
        assert our["alert_count"] == 1

    def test_existing_work_containers_endpoint_still_works(self, client, pg_session):
        """Verify GET /api/work-containers still returns and includes new fields."""
        container = WorkContainer(
            name="compat test",
            project_goal="backward compat",
            base_workdir="/workspace/compat",
            lifecycle_state=ContainerLifecycle.ACTIVE.value,
        )
        pg_session.add(container)
        pg_session.commit()

        r, t = _make_task_run_budget(pg_session, status="EXECUTING")
        _make_session(pg_session, container, r, t, role="compat")

        resp = client.get("/api/work-containers", headers=AUTH)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        containers = data["containers"]
        our = [c for c in containers if c["id"] == str(container.id)][0]

        # New fields present
        assert "team_status" in our
        assert "active_session_count" in our
        assert "alert_count" in our
        # Old fields still present
        assert "counts" in our
        assert "sessions" in our
        assert "lifecycle_state" in our

    def test_usage_endpoint_empty_container(self, client, empty_container):
        resp = client.get(
            f"/api/work-containers/{empty_container.id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["active_session_count"] == 0
        assert data["total_session_count"] == 0
        assert len(data["per_session"]) == 0
        assert data["team_pressure_mode"] == "NORMAL"
        assert data["aggregate"]["used"]["tokens"] == 0
        assert data["aggregate"]["reserved"]["tokens"] == 0
        assert data["aggregate"]["remaining"]["tokens"] == 0

    def test_usage_endpoint_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/work-containers/{fake_id}/usage",
            headers=AUTH,
        )
        assert resp.status_code == 404


class TestAuthRequired:
    """Every endpoint must enforce auth via Depends(require_token)."""

    def test_usage_requires_auth(self, client):
        resp = client.get(
            f"/api/work-containers/{uuid.uuid4()}/usage",
        )
        assert resp.status_code == 401

    def test_containers_extended_requires_auth(self, client):
        resp = client.get("/api/containers")
        assert resp.status_code == 401
