"""SQLAlchemy 模型：PostgreSQL 为唯一业务事实来源。

层级：tasks ──< task_runs ──< 其余全部（预算/阶段/迭代/调用/事件/审批/报告）。
大对象（完整日志、diff、报告原文）存 ArtifactStore，这里只放摘要 + artifact_ref。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    workdir: Mapped[str] = mapped_column(String(500))  # workspace 内工作目录
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)  # 空则由 agent 生成
    template: Mapped[str] = mapped_column(String(50), default="fix_bug")
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runs: Mapped[list["TaskRun"]] = relationship(back_populates="task", order_by="TaskRun.attempt_no")
    work_session: Mapped["WorkSession | None"] = relationship(
        back_populates="task", uselist=False, foreign_keys="WorkSession.task_id"
    )


class TaskRun(Base):
    """运行实例层：同一 task 可多次运行（重试/换模型/A-B-C 对照评测）。"""

    __tablename__ = "task_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    strategy: Mapped[str] = mapped_column(String(20), default="dynamic")  # none|fixed|dynamic
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # docker container id
    model_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    current_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pressure_mode: Mapped[str] = mapped_column(String(20), default="NORMAL")
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 实际执行时间（WAITING_APPROVAL/PAUSED 期间不累计），单调时钟增量累加
    active_runtime_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[Task] = relationship(back_populates="runs")
    budget: Mapped["TaskBudget"] = relationship(back_populates="run", uselist=False)
    work_session: Mapped["WorkSession | None"] = relationship(
        back_populates="current_run", uselist=False, foreign_keys="WorkSession.current_run_id"
    )


class WorkContainer(Base):
    """Durable project/team scope. Shared context is the only implicit cross-session context."""

    __tablename__ = "work_containers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    project_goal: Mapped[str] = mapped_column(Text)
    shared_context: Mapped[str] = mapped_column(Text, default="")
    lifecycle_state: Mapped[str] = mapped_column(String(20), default="active", index=True)
    base_workdir: Mapped[str] = mapped_column(String(500))
    default_workspace_policy: Mapped[str] = mapped_column(String(20), default="isolated")
    preset_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preset_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["WorkSession"]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
        order_by="WorkSession.created_at",
    )
    messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="container", cascade="all, delete-orphan"
    )


class WorkSession(Base):
    """One private specialist lane backed by a normal task and current run."""

    __tablename__ = "work_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_containers.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    private_context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), unique=True)
    current_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), unique=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    worktree_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    worktree_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    workspace_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    workspace_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    container: Mapped[WorkContainer] = relationship(back_populates="sessions")
    task: Mapped[Task] = relationship(back_populates="work_session", foreign_keys=[task_id])
    current_run: Mapped[TaskRun] = relationship(
        back_populates="work_session", foreign_keys=[current_run_id]
    )
    sent_messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="sender_session", foreign_keys="SessionMessage.sender_session_id"
    )
    received_messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="recipient_session", foreign_keys="SessionMessage.recipient_session_id"
    )

    __table_args__ = (
        UniqueConstraint("container_id", "idempotency_key", name="uq_work_session_container_key"),
    )


class SessionMessage(Base):
    """Explicit, recipient-specific collaboration inbox entry with immutable provenance."""

    __tablename__ = "session_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_containers.id", ondelete="CASCADE"), index=True
    )
    sender_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    author_type: Mapped[str] = mapped_column(String(20), default="operator")
    kind: Mapped[str] = mapped_column(String(20), default="message")
    content: Mapped[str] = mapped_column(Text)
    delivery_state: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    container: Mapped[WorkContainer] = relationship(back_populates="messages")
    sender_session: Mapped[WorkSession | None] = relationship(
        back_populates="sent_messages", foreign_keys=[sender_session_id]
    )
    recipient_session: Mapped[WorkSession] = relationship(
        back_populates="received_messages", foreign_keys=[recipient_session_id]
    )

    __table_args__ = (
        UniqueConstraint("container_id", "idempotency_key", name="uq_session_message_container_key"),
        Index(
            "ix_session_messages_recipient_delivery_created",
            "recipient_session_id",
            "delivery_state",
            "created_at",
        ),
    )


class TaskBudget(Base):
    """预算账本。used_* / reserved_* 只能通过原子 SQL（budget.manager）更新。"""

    __tablename__ = "task_budgets"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), primary_key=True)
    max_total_tokens: Mapped[int] = mapped_column(BigInteger, default=100_000)
    max_wall_time_seconds: Mapped[int] = mapped_column(Integer, default=1200)
    max_active_runtime_seconds: Mapped[int] = mapped_column(Integer, default=600)
    max_llm_calls: Mapped[int] = mapped_column(Integer, default=20)
    max_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=5.0)
    max_parallel_llm_calls: Mapped[int] = mapped_column(Integer, default=2)

    used_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    used_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    used_calls: Mapped[int] = mapped_column(Integer, default=0)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    reserved_calls: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped[TaskRun] = relationship(back_populates="budget")


class TaskPhase(Base):
    __tablename__ = "task_phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    phase: Mapped[str] = mapped_column(String(20))
    budget_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    budget_seconds: Mapped[int] = mapped_column(Integer, default=0)
    budget_calls: Mapped[int] = mapped_column(Integer, default=0)
    budget_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    used_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    used_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    used_calls: Mapped[int] = mapped_column(Integer, default=0)
    used_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|active|done|capped


class LoopIteration(Base):
    __tablename__ = "loop_iterations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state_from: Mapped[str | None] = mapped_column(String(30), nullable=True)
    state_to: Mapped[str | None] = mapped_column(String(30), nullable=True)
    progress_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)  # 确定性信号快照
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pressure_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LlmCall(Base):
    """每一次真实 LLM API 调用的独立记录。"""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    call_id: Mapped[str] = mapped_column(String(100), index=True)  # litellm x-litellm-call-id / uuid
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    call_kind: Mapped[str] = mapped_column(String(20), default="agent")  # agent|condenser|other
    agent_name: Mapped[str] = mapped_column(String(100), default="openhands-agent")
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ttft_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    token_source: Mapped[str] = mapped_column(String(20), default="unavailable")
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)  # None=价格未配置
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_status: Mapped[str] = mapped_column(String(20), default="success")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    response_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 完整内容在 ArtifactStore
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)  # 该调用对应的工具/决策
    effective: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # 是否产生有效进展
    progress_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    inefficiency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tool: Mapped[str] = mapped_column(String(100))
    args_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), nullable=True)


class ExecutionEvent(Base):
    """SSE outbox：随状态变更同事务写入，前端按 seq 去重、Last-Event-ID 回放。"""

    __tablename__ = "execution_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_events_run_seq", "run_id", "seq"),)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    est_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # 动作细节（命令、路径等）
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    git_ref: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    command: Mapped[str] = mapped_column(String(500))
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    artifact_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProgressSignal(Base):
    """确定性进展信号原始记录（评分依据，防伪智能：信号即事实）。"""

    __tablename__ = "progress_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    signals: Mapped[dict] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinalReport(Base):
    __tablename__ = "final_reports"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30))
    acceptance_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    files_changed: Mapped[dict] = mapped_column(JSONB, default=list)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    totals: Mapped[dict] = mapped_column(JSONB, default=dict)  # tokens/time/calls/cost
    strategy_switches: Mapped[dict] = mapped_column(JSONB, default=list)
    open_issues: Mapped[dict] = mapped_column(JSONB, default=list)
    suggestions: Mapped[dict] = mapped_column(JSONB, default=list)
    report_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
