"""Dramatiq actors：run_task（队列消费）+ sweeper（周期扫描）。

消费端：dramatiq app.worker.actors -p 1 -t 4
Sweeper：python -m app.worker.actors --sweeper
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from datetime import datetime, timezone

import dramatiq
import redis

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.enums import RunStatus
from app.core.models import Task, TaskRun, utcnow
from app.worker.broker import QUEUE_NAME

logger = logging.getLogger(__name__)

_RedisError = (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError)


def _redis_client() -> redis.Redis | None:
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        return r
    except _RedisError:
        return None


@dramatiq.actor(queue_name=QUEUE_NAME, actor_name="run_task", max_retries=0)
def run_task(run_id: str) -> None:
    """消费 task_run：PENDING/REPLANNING 方可启动（幂等）。"""
    session = SessionLocal()
    try:
        run = session.get(TaskRun, uuid.UUID(run_id))
        if run is None:
            logger.warning("run_task: run %s not found, skipping", run_id)
            return
        current = RunStatus(run.status)
        if current.is_terminal:
            logger.info("run_task: run %s already terminal (%s), skipping", run_id, current.value)
            return
        if current not in (RunStatus.PENDING, RunStatus.REPLANNING):
            logger.info("run_task: run %s status=%s, skipping", run_id, current.value)
            return

        def heartbeat(rid: str) -> None:
            try:
                r = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
                r.setex(f"budgetloop:hb:{rid}", settings.worker_heartbeat_ttl_seconds, "1")
            except _RedisError:
                pass

        from app.worker.orchestrator import Orchestrator

        orch = Orchestrator(session, run_id, heartbeat=heartbeat)
        orch.run()
    except Exception:
        logger.exception("run_task %s unhandled exception", run_id)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Sweeper
# ---------------------------------------------------------------------------

NON_TERMINAL_STATUSES = [
    RunStatus.PENDING.value,
    RunStatus.PLANNING.value,
    RunStatus.EXECUTING.value,
    RunStatus.OBSERVING.value,
    RunStatus.EVALUATING.value,
    RunStatus.REPLANNING.value,
    RunStatus.WAITING_APPROVAL.value,
    RunStatus.PAUSED.value,
]

ACTIVE_STATUSES = [
    RunStatus.PLANNING.value,
    RunStatus.EXECUTING.value,
    RunStatus.OBSERVING.value,
    RunStatus.EVALUATING.value,
    RunStatus.REPLANNING.value,
]


def _sweep_once() -> None:
    session = SessionLocal()
    try:
        r = _redis_client()

        # a) deadline 过期 → BUDGET_EXHAUSTED
        now = datetime.now(timezone.utc)
        expired = (
            session.query(TaskRun)
            .filter(
                TaskRun.status.in_(NON_TERMINAL_STATUSES),
                TaskRun.deadline_at.isnot(None),
                TaskRun.deadline_at < now,
            )
            .all()
        )
        for run in expired:
            logger.warning("sweeper: run %s deadline expired → BUDGET_EXHAUSTED", run.id)
            try:
                from app.worker.orchestrator import Orchestrator

                orch = Orchestrator(session, run.id)
                task = session.get(Task, run.task_id)
                if task is None:
                    raise RuntimeError(f"task {run.task_id} not found for expired run {run.id}")
                orch._write_final_report(run, task, RunStatus.BUDGET_EXHAUSTED, "")
                run.status = RunStatus.BUDGET_EXHAUSTED.value
                run.finished_at = utcnow()
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("sweeper: failed to expire run %s", run.id)

        # b) 心跳过期 → 重入队
        active = session.query(TaskRun).filter(TaskRun.status.in_(ACTIVE_STATUSES)).all()
        for run in active:
            hb = None
            if r is not None:
                try:
                    hb = r.get(f"budgetloop:hb:{run.id}")
                except _RedisError:
                    pass
            if hb is not None:
                continue
            logger.warning("sweeper: run %s heartbeat expired, re-enqueue", run.id)
            try:
                run.status = RunStatus.PENDING.value
                session.commit()
                from app.worker.broker import enqueue_run

                enqueue_run(str(run.id))
            except Exception:
                session.rollback()
                logger.exception("sweeper: failed to re-enqueue run %s", run.id)
    finally:
        session.close()


def run_sweeper_loop() -> None:
    logger.info("sweeper started, interval=%ds", settings.sweeper_interval_seconds)
    while True:
        try:
            _sweep_once()
        except Exception:
            logger.exception("sweeper iteration failed")
        time.sleep(settings.sweeper_interval_seconds)


# 直接调用 python -m app.worker.actors --sweeper
if __name__ == "__main__" and "--sweeper" in sys.argv:
    run_sweeper_loop()
