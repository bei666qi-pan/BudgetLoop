"""路由共享的序列化与创建逻辑。"""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.budget.manager import TaskBudgetManager
from app.core.enums import EventType, Phase, RunStatus, Strategy
from app.core.models import Task, TaskBudget, TaskPhase, TaskRun, utcnow
from app.events.outbox import emit_event

DEFAULT_ACCEPTANCE_CRITERIA = (
    "1) 任务描述中的目标已达成；"
    "2) 相关自动化测试通过（无测试则说明人工验证步骤）；"
    "3) 改动范围未超出任务描述。"
)

# 初始阶段预算权重（tokens/seconds/calls/cost 均按此切分）。
# none=无预算基线（全 0）；fixed/dynamic 初始相同，dynamic 由 worker 运行时再分配。
PHASE_WEIGHTS: dict[Phase, float] = {
    Phase.SCAN: 0.05,
    Phase.ANALYZE: 0.15,
    Phase.MODIFY: 0.35,
    Phase.VERIFY: 0.20,
    Phase.REPAIR: 0.15,
    Phase.SUMMARIZE: 0.10,
}


def create_run(
    session: Session,
    task: Task,
    attempt_no: int,
    strategy: Strategy,
    budget_fields: dict,
    model_config: dict | None = None,
) -> TaskRun:
    """创建 TaskRun + TaskBudget + 六个 TaskPhase，并同事务发 run_started 事件。"""
    deadline = utcnow() + timedelta(seconds=budget_fields["max_wall_time_seconds"])
    run = TaskRun(
        task_id=task.id,
        attempt_no=attempt_no,
        strategy=strategy.value,
        status=RunStatus.PENDING.value,
        model_config=model_config or {},
        deadline_at=deadline,
    )
    session.add(run)
    session.flush()

    budget = TaskBudget(run_id=run.id, **budget_fields)
    session.add(budget)

    weighted = strategy in (Strategy.FIXED, Strategy.DYNAMIC)
    for phase in Phase:
        w = PHASE_WEIGHTS[phase] if weighted else 0.0
        session.add(
            TaskPhase(
                run_id=run.id,
                phase=phase.value,
                budget_tokens=int(budget_fields["max_total_tokens"] * w),
                budget_seconds=int(budget_fields["max_active_runtime_seconds"] * w),
                budget_calls=int(budget_fields["max_llm_calls"] * w),
                budget_cost=round(float(budget_fields["max_cost"]) * w, 6),
            )
        )

    emit_event(
        session,
        run.id,
        EventType.RUN_STARTED,
        {"task_id": str(task.id), "attempt_no": attempt_no, "strategy": strategy.value},
    )
    return run


def budget_snapshot_dict(session: Session, run_id: uuid.UUID) -> dict:
    return TaskBudgetManager(session, run_id).snapshot().to_dict()


def run_to_dict(run: TaskRun) -> dict:
    work_session = getattr(run, "work_session", None)
    return {
        "id": str(run.id),
        "task_id": str(run.task_id),
        "attempt_no": run.attempt_no,
        "strategy": run.strategy,
        "status": run.status,
        "current_phase": run.current_phase,
        "pressure_mode": run.pressure_mode,
        "iteration": run.iteration,
        "model_config": run.model_config or {},
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "deadline_at": run.deadline_at.isoformat() if run.deadline_at else None,
        "active_runtime_ms": run.active_runtime_ms,
        "error": run.error,
        "work_container_id": str(work_session.container_id) if work_session else None,
        "work_session_id": str(work_session.id) if work_session else None,
        "work_session_role": work_session.role if work_session else None,
    }


def task_to_dict(task: Task) -> dict:
    return {
        "id": str(task.id),
        "name": task.name,
        "description": task.description,
        "workdir": task.workdir,
        "acceptance_criteria": task.acceptance_criteria,
        "template": task.template,
        "require_approval": task.require_approval,
    }
