"""TaskBudgetManager 行为测试（需要 docker 起 PG：CAS SQL 依赖 now()/RETURNING）。"""
from __future__ import annotations

import threading
import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.budget.manager import BudgetRejected, TaskBudgetManager
from app.core.models import Task, TaskBudget, TaskRun, utcnow
from tests.conftest import requires_docker

pytestmark = requires_docker


def _make_run(session: Session, **budget_kw) -> uuid.UUID:
    task = Task(name="t", description="", workdir="/workspace/x")
    session.add(task)
    session.flush()
    run = TaskRun(task_id=task.id, status="EXECUTING")
    session.add(run)
    session.flush()
    fields = {
        "max_total_tokens": 1000,
        "max_wall_time_seconds": 1200,
        "max_active_runtime_seconds": 600,
        "max_llm_calls": 5,
        "max_cost": 1.0,
    }
    fields.update(budget_kw)
    session.add(TaskBudget(run_id=run.id, **fields))
    session.commit()
    return run.id


def test_reserve_success(pg_session):
    run_id = _make_run(pg_session)
    mgr = TaskBudgetManager(pg_session, run_id)
    mgr.reserve(est_tokens=100, est_cost=0.1)
    pg_session.commit()
    snap = mgr.snapshot()
    assert snap.reserved_calls == 1
    assert snap.reserved_tokens == 100
    assert snap.remaining_tokens == 900


def test_reserve_rejected_on_calls(pg_session):
    run_id = _make_run(pg_session, max_llm_calls=1)
    mgr = TaskBudgetManager(pg_session, run_id)
    mgr.reserve(est_tokens=10, est_cost=0.01)
    pg_session.commit()
    with pytest.raises(BudgetRejected, match="max_llm_calls"):
        mgr.reserve(est_tokens=10, est_cost=0.01)


def test_reserve_rejected_on_tokens(pg_session):
    run_id = _make_run(pg_session, max_total_tokens=100)
    mgr = TaskBudgetManager(pg_session, run_id)
    with pytest.raises(BudgetRejected):
        mgr.reserve(est_tokens=101, est_cost=0.0)


def test_reserve_rejected_on_cost(pg_session):
    run_id = _make_run(pg_session, max_cost=0.5)
    mgr = TaskBudgetManager(pg_session, run_id)
    with pytest.raises(BudgetRejected):
        mgr.reserve(est_tokens=10, est_cost=0.6)


def test_concurrent_reserve_single_winner(pg_engine):
    # 参与竞争的线程用独立连接，因此夹具数据必须真实提交（不能用回滚型 pg_session）
    setup = Session(bind=pg_engine)
    run_id = _make_run(setup, max_llm_calls=1)
    setup.close()

    successes: list[uuid.UUID] = []
    lock = threading.Lock()

    def attempt():
        session = Session(bind=pg_engine)
        try:
            TaskBudgetManager(session, run_id).reserve(est_tokens=10, est_cost=0.01)
            session.commit()
            with lock:
                successes.append(run_id)
        except BudgetRejected:
            session.rollback()
        finally:
            session.close()

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check = Session(bind=pg_engine)
    try:
        assert len(successes) == 1
        assert TaskBudgetManager(check, run_id).snapshot().reserved_calls == 1
    finally:
        run = check.get(TaskRun, run_id)
        check.delete(check.get(TaskBudget, run_id))
        check.delete(run)
        check.delete(check.get(Task, run.task_id))
        check.commit()
        check.close()


def test_settle_moves_reserved_to_used(pg_session):
    run_id = _make_run(pg_session)
    mgr = TaskBudgetManager(pg_session, run_id)
    mgr.reserve(est_tokens=100, est_cost=0.5)
    pg_session.commit()
    mgr.settle(est_tokens=100, est_cost=0.5, actual_tokens=80, actual_cost=0.4)
    pg_session.commit()
    snap = mgr.snapshot()
    assert snap.used_calls == 1
    assert snap.used_tokens == 80
    assert snap.used_cost == pytest.approx(0.4)
    assert snap.reserved_calls == 0
    assert snap.reserved_tokens == 0
    assert snap.reserved_cost == pytest.approx(0.0)


def test_release_rolls_back_reservation(pg_session):
    run_id = _make_run(pg_session)
    mgr = TaskBudgetManager(pg_session, run_id)
    mgr.reserve(est_tokens=100, est_cost=0.5)
    pg_session.commit()
    mgr.release(est_tokens=100, est_cost=0.5)
    pg_session.commit()
    snap = mgr.snapshot()
    assert snap.reserved_calls == 0
    assert snap.reserved_tokens == 0
    assert snap.reserved_cost == pytest.approx(0.0)
    assert snap.used_calls == 0


def test_reserve_rejected_after_deadline(pg_session):
    run_id = _make_run(pg_session)
    run = pg_session.get(TaskRun, run_id)
    run.deadline_at = utcnow() - timedelta(seconds=1)
    pg_session.commit()
    with pytest.raises(BudgetRejected):
        TaskBudgetManager(pg_session, run_id).reserve(est_tokens=10, est_cost=0.01)
