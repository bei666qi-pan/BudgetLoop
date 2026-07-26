"""Dramatiq broker 与队列契约（control-plane 与 worker 共用）。

control-plane 通过 enqueue_run() 投递任务；worker 进程消费 run_task。
只在这里放 broker 定义，actor 实现在 app.worker.actors（避免循环导入）。
"""
from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import settings

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)

QUEUE_NAME = "budgetloop.runs"


def enqueue_run(run_id: str) -> None:
    """control-plane 调用：把一个 task_run 交给 worker 执行。"""
    broker.enqueue(
        dramatiq.Message(
            queue_name=QUEUE_NAME,
            actor_name="run_task",
            args=(run_id,),
            kwargs={},
            options={},
        )
    )
