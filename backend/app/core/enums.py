"""BudgetLoop 核心枚举：状态机、策略、阶段、压力模式。

前后端共享的契约，前端按字符串渲染。
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


class TaskTemplate(StrEnum):
    FIX_BUG = "fix_bug"
    LOCATE_ISSUE = "locate_issue"
    ADD_TESTS = "add_tests"
    SMALL_FEATURE = "small_feature"
    FIX_BUILD = "fix_build"


class ContainerLifecycle(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class WorkspacePolicy(StrEnum):
    ISOLATED = "isolated"
    WORKTREE = "worktree"


class WorkSessionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SessionMessageKind(StrEnum):
    MESSAGE = "message"
    HANDOFF = "handoff"


class MessageDeliveryState(StrEnum):
    QUEUED = "queued"
    DELIVERED = "delivered"


class RunStatus(StrEnum):
    """task_run 状态机。PLANNING..REPLANNING 为 loop 内部状态，其余为分支/终态。"""

    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    EVALUATING = "EVALUATING"
    REPLANNING = "REPLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIAL_COMPLETED = "PARTIAL_COMPLETED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATUSES


TERMINAL_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.PARTIAL_COMPLETED,
        RunStatus.FAILED,
        RunStatus.BUDGET_EXHAUSTED,
        RunStatus.CANCELLED,
    }
)

# 合法的状态转换表（worker 编排层）。测试会校验所有转换都在表内。
ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.PLANNING, RunStatus.CANCELLED, RunStatus.FAILED}),
    RunStatus.PLANNING: frozenset(
        {RunStatus.EXECUTING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED,
         RunStatus.BUDGET_EXHAUSTED, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.EXECUTING: frozenset(
        {RunStatus.OBSERVING, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED,
         RunStatus.BUDGET_EXHAUSTED, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.OBSERVING: frozenset(
        {RunStatus.EVALUATING, RunStatus.BUDGET_EXHAUSTED, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.EVALUATING: frozenset(
        {RunStatus.REPLANNING, RunStatus.EXECUTING, RunStatus.COMPLETED,
         RunStatus.PARTIAL_COMPLETED, RunStatus.BUDGET_EXHAUSTED,
         RunStatus.WAITING_APPROVAL, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.REPLANNING: frozenset(
        {RunStatus.EXECUTING, RunStatus.PLANNING, RunStatus.WAITING_APPROVAL,
         RunStatus.PAUSED, RunStatus.BUDGET_EXHAUSTED, RunStatus.PARTIAL_COMPLETED,
         RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.WAITING_APPROVAL: frozenset(
        {RunStatus.REPLANNING, RunStatus.EXECUTING, RunStatus.PAUSED,
         RunStatus.CANCELLED, RunStatus.BUDGET_EXHAUSTED, RunStatus.FAILED}
    ),
    RunStatus.PAUSED: frozenset({RunStatus.REPLANNING, RunStatus.CANCELLED}),
    # 终态不可再转换
    RunStatus.COMPLETED: frozenset(),
    RunStatus.PARTIAL_COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.BUDGET_EXHAUSTED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


class Strategy(StrEnum):
    """预算策略：A/B/C 对照评测用。"""

    NONE = "none"        # 无预算基线
    FIXED = "fixed"      # 固定预算，不动态调整
    DYNAMIC = "dynamic"  # BudgetLoop 动态预算


class Phase(StrEnum):
    SCAN = "scan"
    ANALYZE = "analyze"
    MODIFY = "modify"
    VERIFY = "verify"
    REPAIR = "repair"
    SUMMARIZE = "summarize"


class PressureMode(StrEnum):
    NORMAL = "NORMAL"
    CONSERVATIVE = "CONSERVATIVE"
    CRITICAL = "CRITICAL"


class CallKind(StrEnum):
    AGENT = "agent"          # 主 Agent 推理调用
    CONDENSER = "condenser"  # 上下文压缩调用
    OTHER = "other"


class TokenSource(StrEnum):
    ACTUAL = "actual"          # 模型 API 返回的真实 usage
    ESTIMATED = "estimated"    # tokenizer 估算
    UNAVAILABLE = "unavailable"


class RequestStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED_BUDGET = "rejected_budget"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"  # 修改后允许


class ApprovalActionType(StrEnum):
    DELETE_FILE = "delete_file"
    DANGEROUS_COMMAND = "dangerous_command"
    DEPENDENCY_CHANGE = "dependency_change"
    OUT_OF_WORKDIR = "out_of_workdir"
    TOO_MANY_FILES = "too_many_files"
    NETWORK_ACCESS = "network_access"
    RAISE_BUDGET = "raise_budget"
    LARGE_REFACTOR = "large_refactor"


class EventType(StrEnum):
    """execution_events.type，SSE 推送与回放的事件类型。"""

    RUN_STARTED = "run_started"
    STATE_CHANGED = "state_changed"
    PHASE_CHANGED = "phase_changed"
    ITERATION_STARTED = "iteration_started"
    ITERATION_FINISHED = "iteration_finished"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TEST_RESULT = "test_result"
    PROGRESS_SCORED = "progress_scored"
    BUDGET_UPDATED = "budget_updated"
    BUDGET_REALLOCATED = "budget_reallocated"
    PRESSURE_CHANGED = "pressure_changed"
    STRATEGY_SWITCHED = "strategy_switched"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    CHECKPOINT_CREATED = "checkpoint_created"
    ROLLBACK = "rollback"
    AGENT_MESSAGE = "agent_message"
    COLLABORATION_DELIVERED = "collaboration_delivered"
    WARNING = "warning"
    RUN_FINISHED = "run_finished"
