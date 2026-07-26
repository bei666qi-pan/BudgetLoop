"""TaskBudgetManager：预算的唯一写入口。

原则：
- 预检 + 预留用一条原子 UPDATE（PG 行锁串行化），并发请求不可能同时穿透额度；
- 结算（commit）与释放（release）同样是原子 UPDATE；
- 区分 used / reserved / remaining / projected；
- 所有时间判定用数据库 now()，防 worker 时钟漂移。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

# 原子预留：满足全部上限才扣减 reserved_*，否则 0 行返回 = 拒绝
RESERVE_SQL = text(
    """
    UPDATE task_budgets
    SET reserved_calls  = reserved_calls + 1,
        reserved_tokens = reserved_tokens + :est_tokens,
        reserved_cost   = reserved_cost + :est_cost
    WHERE run_id = :run_id
      AND used_calls + reserved_calls < max_llm_calls
      AND used_tokens + reserved_tokens + :est_tokens <= max_total_tokens
      AND used_cost + reserved_cost + :est_cost <= max_cost
      AND EXISTS (SELECT 1 FROM task_runs WHERE id = :run_id AND (deadline_at IS NULL OR now() < deadline_at))
    RETURNING reserved_calls
    """
)

# 结算：预留转实耗（按真实 usage）
SETTLE_SQL = text(
    """
    UPDATE task_budgets
    SET used_calls      = used_calls + 1,
        used_tokens     = used_tokens + :actual_tokens,
        used_cost       = used_cost + :actual_cost,
        reserved_calls  = GREATEST(reserved_calls - 1, 0),
        reserved_tokens = GREATEST(reserved_tokens - :est_tokens, 0),
        reserved_cost   = GREATEST(reserved_cost - :est_cost, 0)
    WHERE run_id = :run_id
    RETURNING used_calls, used_tokens, used_cost
    """
)

# 释放：调用未发生/被拒绝时退回预留
RELEASE_SQL = text(
    """
    UPDATE task_budgets
    SET reserved_calls  = GREATEST(reserved_calls - 1, 0),
        reserved_tokens = GREATEST(reserved_tokens - :est_tokens, 0),
        reserved_cost   = GREATEST(reserved_cost - :est_cost, 0)
    WHERE run_id = :run_id
    """
)


class BudgetRejected(Exception):
    """预算预检未通过。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class BudgetSnapshot:
    max_total_tokens: int
    max_wall_time_seconds: int
    max_active_runtime_seconds: int
    max_llm_calls: int
    max_cost: float
    max_parallel_llm_calls: int
    used_tokens: int
    used_cost: float
    used_calls: int
    reserved_tokens: int
    reserved_cost: float
    reserved_calls: int

    @property
    def remaining_tokens(self) -> int:
        return self.max_total_tokens - self.used_tokens - self.reserved_tokens

    @property
    def remaining_calls(self) -> int:
        return self.max_llm_calls - self.used_calls - self.reserved_calls

    @property
    def remaining_cost(self) -> float:
        return float(self.max_cost) - float(self.used_cost) - float(self.reserved_cost)

    @property
    def projected_tokens(self) -> int:
        """预计最终消耗 = 已用 + 已预留。"""
        return self.used_tokens + self.reserved_tokens

    def to_dict(self) -> dict:
        return {
            "max_total_tokens": self.max_total_tokens,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_active_runtime_seconds": self.max_active_runtime_seconds,
            "max_llm_calls": self.max_llm_calls,
            "max_cost": float(self.max_cost),
            "max_parallel_llm_calls": self.max_parallel_llm_calls,
            "used_tokens": self.used_tokens,
            "used_cost": float(self.used_cost),
            "used_calls": self.used_calls,
            "reserved_tokens": self.reserved_tokens,
            "reserved_cost": float(self.reserved_cost),
            "reserved_calls": self.reserved_calls,
            "remaining_tokens": self.remaining_tokens,
            "remaining_calls": self.remaining_calls,
            "remaining_cost": self.remaining_cost,
            "projected_tokens": self.projected_tokens,
        }


class TaskBudgetManager:
    """所有方法在同一 Session 事务内执行；调用方负责提交。"""

    def __init__(self, session: Session, run_id: uuid.UUID | str):
        self.session = session
        self.run_id = str(run_id)

    def reserve(self, est_tokens: int, est_cost: float) -> None:
        """原子预检+预留。失败抛 BudgetRejected。"""
        row = self.session.execute(
            RESERVE_SQL, {"run_id": self.run_id, "est_tokens": est_tokens, "est_cost": est_cost}
        ).first()
        if row is None:
            snap = self.snapshot()
            raise BudgetRejected(self._reject_reason(snap))

    def settle(self, est_tokens: int, est_cost: float, actual_tokens: int, actual_cost: float) -> None:
        """调用完成后按真实 usage 结算。"""
        self.session.execute(
            SETTLE_SQL,
            {
                "run_id": self.run_id,
                "est_tokens": est_tokens,
                "est_cost": est_cost,
                "actual_tokens": actual_tokens,
                "actual_cost": actual_cost,
            },
        )

    def release(self, est_tokens: int, est_cost: float) -> None:
        """调用未发生/失败时释放预留。"""
        self.session.execute(RELEASE_SQL, {"run_id": self.run_id, "est_tokens": est_tokens, "est_cost": est_cost})

    def snapshot(self) -> BudgetSnapshot:
        from app.core.models import TaskBudget

        b = self.session.get(TaskBudget, uuid.UUID(self.run_id))
        if b is None:
            raise BudgetRejected("budget row missing")
        return BudgetSnapshot(
            max_total_tokens=b.max_total_tokens,
            max_wall_time_seconds=b.max_wall_time_seconds,
            max_active_runtime_seconds=b.max_active_runtime_seconds,
            max_llm_calls=b.max_llm_calls,
            max_cost=float(b.max_cost),
            max_parallel_llm_calls=b.max_parallel_llm_calls,
            used_tokens=b.used_tokens,
            used_cost=float(b.used_cost),
            used_calls=b.used_calls,
            reserved_tokens=b.reserved_tokens,
            reserved_cost=float(b.reserved_cost),
            reserved_calls=b.reserved_calls,
        )

    @staticmethod
    def _reject_reason(snap: BudgetSnapshot) -> str:
        if snap.remaining_calls <= 0:
            return "max_llm_calls reached"
        if snap.remaining_tokens <= 0:
            return "max_total_tokens reached"
        if snap.remaining_cost <= 0:
            return "max_cost reached"
        return "budget check failed (deadline passed or insufficient allowance)"
