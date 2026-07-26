"""BudgetLoop 主编排器：任务级状态机 + 预算预留/结算 + 确定性评分 + 策略切换
+ 审批闸门 + checkpoint/回滚 + 崩溃恢复。

驱动内核为 OpenHands agent-server（每个 task_run 一个 Workspace 容器）。
一个 BudgetLoop iteration 只驱动一个 OpenHands step：agent-server 的 OpenAPI
spec 没有 per-run 迭代上限参数（max_iterations 是 conversation 级配置）。
server transport 先提交消息、显式调用 conversation /run，再等待 execution_status
回到 idle；CLI transport 则由 send_message(run=True) 直接执行。

DB 写入通过注入的 Session 完成；测试可注入 MagicMock session +
FakeAgentServerClient + FakeWorkspaceManager，聚焦编排决策逻辑。
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from app.budget.manager import BudgetRejected, BudgetSnapshot, TaskBudgetManager
from app.collaboration.service import (
    delivery_event_payload,
    format_agent_inbox,
    mark_messages_delivered,
    queued_messages_for_run,
)
from app.core.config import settings
from app.core.enums import (
    ALLOWED_TRANSITIONS,
    CallKind,
    EventType,
    Phase,
    PressureMode,
    RunStatus,
    Strategy,
    TokenSource,
)
from app.core.models import (
    Approval,
    Checkpoint,
    ExecutionEvent,
    FinalReport,
    LlmCall,
    LoopIteration,
    ProgressSignal,
    Task,
    TaskPhase,
    TaskRun,
    TestResult,
    ToolCall,
    WorkSession,
    utcnow,
)
from app.execution_engines import DEFAULT_ENGINE_ID, adapter_for, engine_preflight
from app.execution_engines.adapters import ExecutionEngineAdapter
from app.policy.pressure import compute_pressure_mode
from app.policy.strategy import STRATEGY_DEFAULT, STRATEGY_ROLLBACK, decide_strategy
from app.project_uploads import ProjectUploadError, resolve_project_upload
from app.scoring.progress import compute_score, parse_unittest_output
from app.scoring.signals import ProgressSignals, action_fingerprint, detect_regression
from app.worker import risk as risk_mod
from app.worker.openhands_client import AgentServerError
from app.worker.workspace_manager import CONTAINER_WORKDIR, WorkspaceError, WorkspaceManager

DEFAULT_TEST_COMMAND = "python -m unittest discover -s tests -v"
DEFAULT_EST_TOKENS = 4000
DEFAULT_EST_COST = 0.02
DEFAULT_MAX_LOOP_ITERATIONS = 50

PHASE_GOALS: dict[Phase, str] = {
    Phase.SCAN: "扫描代码库结构，定位与任务相关的文件与模块。",
    Phase.ANALYZE: "分析根因 / 实现路径，形成具体修改计划。",
    Phase.MODIFY: "按计划做最小化代码修改。",
    Phase.VERIFY: "运行测试验证修改是否满足验收标准。",
    Phase.REPAIR: "修复验证阶段发现的问题。",
    Phase.SUMMARIZE: "总结改动并收尾。",
}

PRESSURE_HINTS: dict[PressureMode, str] = {
    PressureMode.NORMAL: "预算充足，可以充分探索与验证。",
    PressureMode.CONSERVATIVE: "预算偏紧：避免大范围重构，优先最小改动，每一步都要有明确证据产出。",
    PressureMode.CRITICAL: "预算紧急：只做最小修复，禁止探索性操作，立即收尾。",
}

MANAGED_AI_APP_GUIDANCE = (
    "如果任务生成 AI 应用且环境中存在 BUDGETLOOP_AI_MANAGED=1，只能在服务端进程中使用 "
    "OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_MODEL；它们是 BudgetLoop 短期受限运行时配置。"
    "不得把任何值写入项目文件、.env、Git、日志或浏览器 bundle；浏览器必须调用应用自己的服务端。"
)

FAILED_EXECUTION_STATUSES = frozenset({"error", "stuck"})


class InvalidTransition(Exception):
    """非法状态机转换。"""


def selected_execution_engine(model_config: dict[str, Any]) -> str:
    """Resolve a run engine and fail closed before any workspace is provisioned."""
    engine_id = str(model_config.get("execution_engine") or DEFAULT_ENGINE_ID)
    preflight = engine_preflight(engine_id)
    if not preflight.runtime_available:
        raise RuntimeError(f"execution engine {engine_id!r} is unavailable: {preflight.reason}")
    return engine_id


def build_cli_execution_instruction(
    *,
    pressure_mode: PressureMode | str,
    feedback: str | None = None,
) -> str:
    """A CLI process is one bounded end-to-end turn rather than an OpenHands step."""
    mode = PressureMode(pressure_mode)
    parts = [
        "在本次有界执行中完成任务：分析、修改、验证并给出公开总结。",
        f"压力模式 {mode.value}: {PRESSURE_HINTS[mode]}",
        "只能在分配的 workspace 内修改文件；不要扩大权限或访问其他 Session。",
        MANAGED_AI_APP_GUIDANCE,
        "遇到无法安全完成的动作时停止并明确说明，不得静默改用其他执行引擎。",
    ]
    if feedback:
        parts.append(f"人工审批反馈：{feedback}")
    return "\n".join(parts)


def can_transition(frm: RunStatus | str, to: RunStatus | str) -> bool:
    return RunStatus(to) in ALLOWED_TRANSITIONS[RunStatus(frm)]


def assert_transition(frm: RunStatus | str, to: RunStatus | str) -> None:
    if not can_transition(frm, to):
        raise InvalidTransition(f"illegal transition: {RunStatus(frm).value} -> {RunStatus(to).value}")


# ---------------------------------------------------------------------------
# 事件与 artifact 的可注入依赖（app.events.outbox / app.artifacts.store 由
# control-plane 代理实现；这里 lazy import，缺失时退化为本地实现以便独立测试）
# ---------------------------------------------------------------------------
def _default_emit(session, run_id, type_, payload) -> None:
    session.add(ExecutionEvent(run_id=run_id, type=str(type_), payload=payload))


def _load_outbox_emit() -> Callable[..., Any] | None:
    try:  # pragma: no cover - 依赖并行代理的模块
        from app.events.outbox import emit_event
    except Exception:  # noqa: BLE001
        return None
    return emit_event


_outbox_emit = _load_outbox_emit()


class _LocalArtifactStore:
    """get_store() 不可用时的本地文件退化实现。"""

    def __init__(self, root: str):
        self.root = root

    def put_bytes(self, key: str, data: bytes) -> str:
        import os

        path = os.path.join(self.root, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def get_bytes(self, ref: str) -> bytes:
        with open(ref, "rb") as f:
            return f.read()


def _default_store() -> _LocalArtifactStore:
    return _LocalArtifactStore(settings.artifact_local_dir)


def _load_get_store() -> Callable[[], Any] | None:
    try:  # pragma: no cover - 依赖并行代理的模块
        from app.artifacts.store import get_store
    except Exception:  # noqa: BLE001
        return None
    return get_store


_get_store = _load_get_store()


# ---------------------------------------------------------------------------
# Planner：指令文本（确定性模板，无 LLM 参与）
# ---------------------------------------------------------------------------
def build_initial_message(
    *,
    task_description: str,
    acceptance_criteria: str | None,
    phase: str,
    snapshot: BudgetSnapshot | None,
    pressure_mode: PressureMode | str,
) -> str:
    """首个 initial_message：任务描述 + 验收标准 + 当前阶段 + 剩余预算 + 压力模式提示。"""
    mode = PressureMode(pressure_mode)
    if snapshot is not None:
        budget_line = (
            f"剩余预算：tokens={snapshot.remaining_tokens}/{snapshot.max_total_tokens}, "
            f"calls={snapshot.remaining_calls}/{snapshot.max_llm_calls}, "
            f"cost={snapshot.remaining_cost:.4f}/{float(snapshot.max_cost):.4f}, "
            f"wall_time={snapshot.max_wall_time_seconds}s, "
            f"active_runtime={snapshot.max_active_runtime_seconds}s"
        )
    else:
        budget_line = "预算：本 run 不跟踪预算（strategy=none 基线）。"
    return (
        "# 任务\n"
        f"{task_description}\n\n"
        "# 验收标准\n"
        f"{acceptance_criteria or '（未显式给出：以任务描述为准，自行判断完成标准）'}\n\n"
        "# 当前阶段\n"
        f"{phase}: {PHASE_GOALS.get(Phase(phase), '')}\n\n"
        "# 预算\n"
        f"{budget_line}\n\n"
        "# 压力模式\n"
        f"{mode.value}: {PRESSURE_HINTS[mode]}\n\n"
        "# 生成 AI 应用的密钥边界\n"
        f"{MANAGED_AI_APP_GUIDANCE}\n"
    )


def build_iteration_instruction(
    *,
    iteration: int,
    phase: str,
    pressure_mode: PressureMode | str,
    last_score: float | None = None,
    feedback: str | None = None,
) -> str:
    """每轮指令：阶段目标 + 压力模式约束（+ 审批拒绝反馈 / 上轮评分）。"""
    mode = PressureMode(pressure_mode)
    parts = [
        f"[BudgetLoop iteration {iteration}] 阶段 {phase}: {PHASE_GOALS.get(Phase(phase), '')}",
        f"压力模式 {mode.value}: {PRESSURE_HINTS[mode]}",
    ]
    if last_score is not None:
        parts.append(f"上一轮进展评分: {last_score:.2f}（0~1，低分表示无有效进展，请改变做法）。")
    if feedback:
        parts.append(f"人工审批反馈：{feedback}（请在后续动作中遵守）。")
    parts.append("请只推进当前阶段目标，完成一个动作步骤后停下等待下一步指令。")
    return "\n".join(parts)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class Orchestrator:
    """task_run 级编排器。所有外部依赖均可注入以便单元测试。"""

    def __init__(
        self,
        session,
        run_id: str | uuid.UUID,
        *,
        client=None,
        workspace_manager: WorkspaceManager | None = None,
        budget_manager: TaskBudgetManager | None = None,
        emit_event: Callable | None = None,
        store=None,
        heartbeat: Callable[[str], None] | None = None,
        step_timeout_seconds: float = 300.0,
        approval_timeout_seconds: float = 1800.0,
        approval_poll_interval: float = 5.0,
    ):
        self.session = session
        self.run_uuid = uuid.UUID(str(run_id))
        self.run_id = str(run_id)
        self.client = client
        self.workspace_manager = workspace_manager
        self.budget_manager = budget_manager
        self.emit = emit_event or _outbox_emit or _default_emit
        self.store = store
        self.heartbeat = heartbeat
        self.step_timeout_seconds = step_timeout_seconds
        self.approval_timeout_seconds = approval_timeout_seconds
        self.approval_poll_interval = approval_poll_interval

        # 循环内状态
        self._last_tick = time.monotonic()
        self._last_event_id: str | None = None
        self._action_fingerprints: set[str] = set()
        self._prev_test: tuple[int, int] | None = None  # (passed, failed)
        self._stats_cursor: dict[str, dict[str, int]] = {}  # usage_id -> 已消费的 stats 列表长度
        self._scores: list[float] = []
        self._repeated_count = 0
        self._regression_count = 0
        self._current_strategy = STRATEGY_DEFAULT
        self._strategy_switches: list[dict] = []
        self._feedback: str | None = None
        self._workspace_handle = None
        self._managed_runtime_accounting = False
        self.engine_adapter: ExecutionEngineAdapter | None = None

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------
    def run(self) -> TaskRun:
        run = self._load_run()
        if RunStatus(run.status).is_terminal:
            return run
        try:
            self._run_inner(run)
        except Exception as exc:  # noqa: BLE001 - 所有异常 -> FAILED
            self._fail(run, exc)
        return run

    # ------------------------------------------------------------------
    def _load_run(self) -> TaskRun:
        run = self.session.get(TaskRun, self.run_uuid)
        if run is None:
            raise InvalidTransition(f"task_run not found: {self.run_id}")
        return run

    def _run_inner(self, run: TaskRun) -> None:
        task = getattr(run, "task", None) or self.session.get(Task, run.task_id)
        strategy = Strategy(run.strategy)
        model_config = dict(run.model_config or {})
        execution_engine = selected_execution_engine(model_config)
        engine_adapter = adapter_for(execution_engine)
        self.engine_adapter = engine_adapter
        if self.workspace_manager is None:
            self.workspace_manager = engine_adapter.create_workspace_manager()

        self.transition(run, RunStatus.PLANNING)
        self.emit_event(
            run,
            EventType.RUN_STARTED,
            {
                "run_id": self.run_id,
                "strategy": strategy.value,
                "execution_engine": execution_engine,
            },
        )
        run.started_at = run.started_at or utcnow()
        self._last_tick = time.monotonic()
        self._commit()

        # workspace：崩溃恢复（已有 container）则 attach，否则 provision
        handle = self._ensure_workspace(run, task, model_config)
        self._workspace_handle = handle
        if self.client is None:
            self.client = engine_adapter.create_client(handle, model_config)

        # conversation：conversation_id = uuid5(NAMESPACE_URL, run_id)，幂等
        self._ensure_conversation(run, task, strategy, model_config, handle)
        self._commit()

        final_status = self._loop(run, task, strategy, model_config, handle.working_dir)
        self._finish(run, task, final_status, handle.working_dir)

    # ------------------------------------------------------------------
    # workspace / conversation
    # ------------------------------------------------------------------
    def _ensure_workspace(self, run: TaskRun, task: Task, model_config: dict):
        engine_adapter = self.engine_adapter or adapter_for(DEFAULT_ENGINE_ID)
        self.engine_adapter = engine_adapter
        if self.workspace_manager is None:
            self.workspace_manager = engine_adapter.create_workspace_manager()
        owner = self._work_session(run)
        if owner is not None:
            owner.workspace_status = "PROVISIONING"
            owner.workspace_error = None
        if run.workspace_id:
            working_dir = (
                owner.worktree_path
                if owner is not None and owner.worktree_enabled and owner.worktree_path
                else CONTAINER_WORKDIR
            )
            handle = self.workspace_manager.attach(
                self.run_id,
                run.workspace_id,
                working_dir=working_dir,
                worktree_branch=owner.worktree_branch if owner is not None else None,
            )
        else:
            source_dir = model_config.get("project_dir")
            project_upload_id = model_config.get("project_upload_id")
            if project_upload_id:
                if model_config.get("folder_access", "isolated") != "isolated" or source_dir:
                    raise WorkspaceError(
                        "project upload snapshots are only valid for isolated workspaces"
                    )
                try:
                    source_dir = resolve_project_upload(str(project_upload_id))
                except ProjectUploadError as exc:
                    raise WorkspaceError(str(exc)) from exc
            if (
                owner is not None
                and model_config.get("folder_access") == "full_access"
                and not owner.worktree_enabled
            ):
                raise WorkspaceError(
                    "full_access Agent Team sessions require a server-generated worktree"
                )
            if source_dir is None and engine_adapter.engine.transport == "cli":
                source_dir = getattr(task, "workdir", None)
            handle = self.workspace_manager.provision(
                self.run_id,
                source_dir=source_dir,
                worktree_session_id=str(owner.id) if owner is not None and owner.worktree_enabled else None,
                folder_access=model_config.get("folder_access", "isolated"),
                project_dir=model_config.get("project_dir"),
            )
            run.workspace_id = handle.container_id
        if owner is not None:
            owner.worktree_branch = handle.worktree_branch
            owner.worktree_path = handle.worktree_path
            owner.workspace_status = "READY"
            owner.updated_at = utcnow()
        return handle

    def _ensure_conversation(
        self, run: TaskRun, task: Task, strategy: Strategy, model_config: dict, handle: Any
    ) -> None:
        """Create an engine conversation without disclosing an upstream credential.

        Agent-server conversations receive only the short-lived capability injected
        into their workspace. CLI engines retain their existing subprocess-based
        runtime environment handling.
        """
        working_dir = str(handle.working_dir)
        conversation_id = uuid.uuid5(uuid.NAMESPACE_URL, self.run_id)
        runtime_env = getattr(handle, "runtime_env", {})
        if not isinstance(runtime_env, dict):
            runtime_env = {}
        server_transport = getattr(self.client, "transport", "server") != "cli"
        self._managed_runtime_accounting = (
            server_transport and runtime_env.get("BUDGETLOOP_AI_MANAGED") == "1"
        )
        if run.conversation_id:
            # 崩溃恢复：复用已有 conversation
            if getattr(self.client, "transport", "server") == "cli":
                self.client.create_conversation(
                    model=model_config.get("model", ""),
                    llm_base_url="",
                    llm_api_key="",
                    working_dir=working_dir,
                    initial_message=None,
                    conversation_id=uuid.UUID(str(run.conversation_id)),
                )
            else:
                self.client.conversation_id = uuid.UUID(str(run.conversation_id))
            return
        snapshot = self._snapshot_or_none(run, strategy)
        phase = run.current_phase or Phase.SCAN.value
        initial_message = build_initial_message(
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            phase=phase,
            snapshot=snapshot,
            pressure_mode=PressureMode(run.pressure_mode or PressureMode.NORMAL.value),
        )
        conversation_model = model_config.get("model")
        llm_base_url = ""
        llm_api_key = ""
        if server_transport:
            llm_base_url = str(runtime_env.get("OPENAI_BASE_URL") or "").strip()
            llm_api_key = str(runtime_env.get("OPENAI_API_KEY") or "").strip()
            runtime_model = str(runtime_env.get("OPENAI_MODEL") or "").strip()
            managed = runtime_env.get("BUDGETLOOP_AI_MANAGED") == "1"
            if not (managed and llm_base_url and llm_api_key and runtime_model):
                raise WorkspaceError(
                    "managed AI runtime unavailable; enable inherited AI access in Settings before "
                    "starting an agent-server run"
                )
            conversation_model = f"openai/{runtime_model}"
        self.client.create_conversation(
            model=conversation_model or "",
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            working_dir=working_dir,
            initial_message=initial_message,
            conversation_id=conversation_id,
            max_iterations=model_config.get("agent_max_iterations", 500),
            usage_id="agent",
        )
        run.conversation_id = conversation_id
        owner = self._work_session(run)
        if owner is not None:
            owner.conversation_id = conversation_id
            owner.updated_at = utcnow()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------
    def _loop(
        self, run: TaskRun, task: Task, strategy: Strategy, model_config: dict, working_dir: str
    ) -> RunStatus:
        max_iterations = int(model_config.get("max_loop_iterations", DEFAULT_MAX_LOOP_ITERATIONS))
        est_tokens = int(model_config.get("per_call_est_tokens", DEFAULT_EST_TOKENS))
        est_cost = float(model_config.get("per_call_est_cost", DEFAULT_EST_COST))
        budget = self._budget(run)

        while True:
            iteration = int(run.iteration or 0) + 1
            if iteration > max_iterations:
                return self.transition(run, RunStatus.PARTIAL_COMPLETED)
            if self.heartbeat:
                self.heartbeat(self.run_id)

            # a. 预算预检（strategy=none 跳过：基线对照）
            if strategy != Strategy.NONE:
                try:
                    budget.reserve(est_tokens, est_cost)
                except BudgetRejected as exc:
                    self.emit_event(run, EventType.WARNING, {"reason": f"budget rejected: {exc.reason}"})
                    return self.transition(run, RunStatus.BUDGET_EXHAUSTED)

            # b. active runtime 心跳（单调时钟增量累加）
            self._tick(run)

            # c. EXECUTING：发送本轮指令并驱动一个 step（等待 idle 近似）
            self.transition(run, RunStatus.EXECUTING)
            self.emit_event(run, EventType.ITERATION_STARTED, {"iteration": iteration})
            self._commit()
            pressure = PressureMode(run.pressure_mode or PressureMode.NORMAL.value)
            if getattr(self.client, "transport", "server") == "cli":
                instruction = build_cli_execution_instruction(
                    pressure_mode=pressure,
                    feedback=self._feedback,
                )
            else:
                instruction = build_iteration_instruction(
                    iteration=iteration,
                    phase=run.current_phase or Phase.SCAN.value,
                    pressure_mode=pressure,
                    last_score=self._scores[-1] if self._scores else None,
                    feedback=self._feedback,
                )
            inbox = queued_messages_for_run(self.session, self.run_uuid)
            if inbox:
                instruction = f"{instruction}\n\n{format_agent_inbox(inbox)}"
            self._feedback = None
            try:
                self._send_iteration_message(run, instruction, inbox)
                info = self.client.wait_until_idle(
                    timeout_seconds=self.step_timeout_seconds,
                    require_execution_start=(
                        getattr(self.client, "transport", "server") != "cli"
                    ),
                )
                conv_status = str(info.get("execution_status", "idle"))
                if conv_status in FAILED_EXECUTION_STATUSES:
                    raise AgentServerError(
                        f"agent-server execution ended with status {conv_status!r}"
                    )
            except Exception:
                if strategy != Strategy.NONE:
                    budget.release(est_tokens, est_cost)
                    self._commit()
                raise
            # d. OBSERVING：拉取本轮新增事件 + stats 增量 + settle
            try:
                self.transition(run, RunStatus.OBSERVING)
                events = self.client.search_events(after_id=self._last_event_id)
                if events:
                    self._last_event_id = events[-1].get("id", self._last_event_id)
                observed = self._record_events(run, iteration, events)
                llm_calls, actual_tokens, actual_cost = self._record_llm_calls(run, iteration, info)
                self._finalize_iteration_budget(
                    budget,
                    strategy,
                    est_tokens,
                    est_cost,
                    actual_tokens,
                    actual_cost,
                )
                self.emit_event(run, EventType.BUDGET_UPDATED, self._snapshot_dict(run, strategy))
                self._commit()
            except Exception:
                self.session.rollback()
                if strategy != Strategy.NONE:
                    budget.release(est_tokens, est_cost)
                    self._commit()
                raise

            # e. 测试（验收涉及测试或当前阶段为 verify/repair）
            cur_test = self._maybe_run_tests(run, task, iteration, working_dir, model_config)
            if cur_test is not None:
                self._commit()

            # f. EVALUATING：确定性评分
            self.transition(run, RunStatus.EVALUATING)
            diff_files, diff_lines = self._diff_stats(working_dir)
            signals = self._build_signals(observed, cur_test, diff_files, diff_lines)
            score = compute_score(signals)
            self._record_score(run, iteration, signals, score, llm_calls)

            # g1. 验收判定
            if self._acceptance_met(task, conv_status, cur_test):
                run.iteration = iteration
                return self.transition(run, RunStatus.COMPLETED)

            # g2. 危险动作审批闸门
            if observed["risk_hits"] and getattr(task, "require_approval", True):
                approved = self._approval_gate(run, iteration, observed["risk_hits"])
                if not approved:
                    # 拒绝理由作为反馈进入 REPLANNING，下轮指令中说明
                    self.transition(run, RunStatus.REPLANNING)

            # g3. 策略切换（仅 dynamic 做动态调整）
            if strategy == Strategy.DYNAMIC:
                self._strategy_step(run, iteration, working_dir)
                self._pressure_step(run, budget)
                self._phase_budget_step(run, iteration, budget)

            # h. checkpoint：git commit + checkpoints 表
            self._checkpoint(run, iteration, working_dir)

            # 阶段推进
            self._advance_phase(run, cur_test)

            run.iteration = iteration
            self.emit_event(
                run,
                EventType.ITERATION_FINISHED,
                {
                    "iteration": iteration,
                    "score": score,
                    "pressure_mode": run.pressure_mode,
                },
            )
            self._commit()

    def _finalize_iteration_budget(
        self,
        budget: TaskBudgetManager,
        strategy: Strategy,
        est_tokens: int,
        est_cost: float,
        actual_tokens: int,
        actual_cost: float,
    ) -> None:
        """Finalize only the worker-owned reservation.

        Managed-runtime requests settle individually at the proxy boundary, so
        their cumulative OpenHands metrics are observability data rather than a
        second budget settlement source.
        """
        if strategy == Strategy.NONE:
            return
        if self._managed_runtime_accounting:
            budget.release(est_tokens, est_cost)
            return
        budget.settle(est_tokens, est_cost, actual_tokens, actual_cost)

    def _send_iteration_message(self, run: TaskRun, instruction: str, inbox: list) -> None:
        """Submit and schedule execution before claiming inbox delivery."""
        if getattr(self.client, "transport", "server") == "cli":
            self.client.send_message(instruction, run=True)
        else:
            self.client.send_message(instruction, run=False)
            self.client.run_conversation()
        if not inbox:
            return
        mark_messages_delivered(inbox)
        self.emit_event(
            run,
            EventType.COLLABORATION_DELIVERED,
            delivery_event_payload(inbox),
        )
        self._commit()

    # ------------------------------------------------------------------
    # d. 事件记录：ActionEvent/ObservationEvent 配对 -> tool_calls
    # ------------------------------------------------------------------
    def _record_events(self, run: TaskRun, iteration: int, events: list[dict]) -> dict:
        actions: dict[str, dict] = {}
        observations: dict[str, dict] = {}
        new_evidence = 0
        repeated = False
        risk_hits: list[risk_mod.RiskHit] = []
        max_chars = settings.summary_max_chars

        for ev in events:
            kind = ev.get("kind")
            if kind == "ActionEvent":
                event_id = ev.get("tool_call_id") or ev.get("id")
                if event_id is not None:
                    actions[str(event_id)] = ev
            elif kind == "ObservationEvent":
                event_id = ev.get("tool_call_id") or ev.get("action_id")
                if event_id is not None:
                    observations[str(event_id)] = ev
                new_evidence += 1
            elif kind == "MessageEvent" and ev.get("source") == "agent":
                text = self._message_text(ev)
                if text:
                    self.emit_event(
                        run,
                        EventType.AGENT_MESSAGE,
                        {
                            "iteration": iteration,
                            "text": text[:max_chars],
                        },
                    )

        phase = run.current_phase
        for call_id, action in actions.items():
            tool = action.get("tool_name") or "unknown"
            args = action.get("action") or action.get("tool_call")
            args_text = json.dumps(args, ensure_ascii=False, default=str)
            fp = action_fingerprint(tool, args_text)
            if fp in self._action_fingerprints:
                repeated = True
                self._repeated_count += 1
            self._action_fingerprints.add(fp)

            obs = observations.get(call_id)
            obs_payload = obs.get("observation") if obs else None
            obs_text = (
                json.dumps(obs_payload, ensure_ascii=False, default=str) if obs_payload is not None else ""
            )
            exit_code = obs_payload.get("exit_code") if isinstance(obs_payload, dict) else None

            hits = risk_mod.assess_action(tool, args if isinstance(args, dict) else args_text)
            risk_hits.extend(hits)

            artifact_ref = self._put_artifact(
                f"{self.run_id}/tool_calls/{iteration}-{call_id}.json",
                json.dumps(
                    {"action": action, "observation": obs_payload}, ensure_ascii=False, default=str
                ).encode(),
            )
            started = _parse_ts(action.get("timestamp"))
            ended = _parse_ts(obs.get("timestamp")) if obs else None
            duration_ms = int((ended - started).total_seconds() * 1000) if started and ended else None
            self.session.add(
                ToolCall(
                    run_id=self.run_uuid,
                    iteration=iteration,
                    phase=phase,
                    tool=str(tool)[:100],
                    args_summary=args_text[:max_chars],
                    started_at=started,
                    ended_at=ended,
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    output_summary=obs_text[:max_chars] or None,
                    artifact_ref=artifact_ref,
                    success=(exit_code in (0, None)),
                    risk_level=hits[0].risk if hits else "low",
                )
            )
            self.emit_event(
                run,
                EventType.TOOL_CALL,
                {
                    "iteration": iteration,
                    "tool": tool,
                    "args_summary": args_text[:200],
                    "exit_code": exit_code,
                },
            )
        return {"new_evidence": new_evidence, "repeated": repeated, "risk_hits": risk_hits}

    @staticmethod
    def _message_text(ev: dict) -> str:
        msg = ev.get("llm_message") or {}
        parts = [c.get("text", "") for c in msg.get("content", []) if isinstance(c, dict)]
        return "\n".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # d. stats 增量 -> llm_calls
    # ------------------------------------------------------------------
    def _record_llm_calls(self, run: TaskRun, iteration: int, info: dict) -> tuple[list[LlmCall], int, float]:
        stats = (info or {}).get("stats") or {}
        usage_to_metrics = stats.get("usage_to_metrics") or {}
        calls: list[LlmCall] = []
        total_tokens = 0
        total_cost = 0.0
        for usage_id, metrics in usage_to_metrics.items():
            cursor = self._stats_cursor.setdefault(usage_id, {"usages": 0, "costs": 0, "latencies": 0})
            token_usages = metrics.get("token_usages") or []
            costs = metrics.get("costs") or []
            latencies = metrics.get("response_latencies") or []
            new_usages = token_usages[cursor["usages"] :]
            new_costs = costs[cursor["costs"] :]
            new_latencies = latencies[cursor["latencies"] :]
            cursor["usages"] = len(token_usages)
            cursor["costs"] = len(costs)
            cursor["latencies"] = len(latencies)

            for i, usage in enumerate(new_usages):
                prompt = int(usage.get("prompt_tokens") or 0)
                completion = int(usage.get("completion_tokens") or 0)
                total = prompt + completion
                cost = self._response_metric_number(
                    new_costs,
                    usage,
                    i,
                    fields=("cost", "total_cost", "amount", "value"),
                )
                latency = self._response_metric_number(
                    new_latencies,
                    usage,
                    i,
                    fields=("latency", "duration", "value"),
                )
                total_tokens += total
                total_cost += cost or 0.0
                call = LlmCall(
                    run_id=self.run_uuid,
                    call_id=usage.get("response_id") or str(uuid.uuid4()),
                    iteration=iteration,
                    phase=run.current_phase,
                    call_kind=self._call_kind(usage_id).value,
                    model=usage.get("model") or metrics.get("model_name"),
                    duration_ms=int(latency * 1000) if latency is not None else None,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    reasoning_tokens=usage.get("reasoning_tokens"),
                    cache_read_tokens=usage.get("cache_read_tokens"),
                    cache_write_tokens=usage.get("cache_write_tokens"),
                    total_tokens=total,
                    token_source=TokenSource.ACTUAL.value if total > 0 else TokenSource.UNAVAILABLE.value,
                    estimated_cost=cost,  # None = 价格未知
                    response_id=usage.get("response_id") or None,
                )
                self.session.add(call)
                calls.append(call)
                self.emit_event(
                    run,
                    EventType.LLM_CALL,
                    {
                        "iteration": iteration,
                        "call_kind": call.call_kind,
                        "total_tokens": total,
                        "cost": cost,
                    },
                )
        return calls, total_tokens, total_cost

    @staticmethod
    def _response_metric_number(
        entries: list,
        usage: dict,
        index: int,
        *,
        fields: tuple[str, ...],
    ) -> float | None:
        entry = None
        response_id = usage.get("response_id")
        if response_id:
            entry = next(
                (
                    item
                    for item in entries
                    if isinstance(item, dict) and item.get("response_id") == response_id
                ),
                None,
            )
        if entry is None and index < len(entries):
            entry = entries[index]
        if isinstance(entry, int | float):
            return float(entry)
        if isinstance(entry, dict):
            for field in fields:
                value = entry.get(field)
                if isinstance(value, int | float):
                    return float(value)
        return None

    @staticmethod
    def _call_kind(usage_id: str) -> CallKind:
        uid = str(usage_id).lower()
        if "condenser" in uid:
            return CallKind.CONDENSER
        if "agent" in uid:
            return CallKind.AGENT
        return CallKind.OTHER

    # ------------------------------------------------------------------
    # e. 测试
    # ------------------------------------------------------------------
    def _tests_required(self, task: Task) -> bool:
        acceptance = (getattr(task, "acceptance_criteria", None) or "").lower()
        return any(k in acceptance for k in ("test", "测试", "unittest", "pytest"))

    def _maybe_run_tests(
        self, run: TaskRun, task: Task, iteration: int, working_dir: str, model_config: dict
    ) -> tuple[int, int] | None:
        phase = run.current_phase
        if not (self._tests_required(task) or phase in (Phase.VERIFY.value, Phase.REPAIR.value)):
            return self._prev_test
        command = model_config.get("test_command", DEFAULT_TEST_COMMAND)
        out = self.client.execute_bash(
            command, timeout=int(model_config.get("test_timeout", 300)), cwd=working_dir
        )
        text = f"{out.get('stdout') or ''}\n{out.get('stderr') or ''}"
        passed, failed, skipped = parse_unittest_output(text)
        artifact_ref = self._put_artifact(f"{self.run_id}/tests/{iteration}.log", text.encode())
        self.session.add(
            TestResult(
                run_id=self.run_uuid,
                iteration=iteration,
                command=command,
                passed=passed,
                failed=failed,
                skipped=skipped,
                artifact_ref=artifact_ref,
            )
        )
        self.emit_event(
            run,
            EventType.TEST_RESULT,
            {
                "iteration": iteration,
                "command": command,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            },
        )
        return (passed, failed)

    # ------------------------------------------------------------------
    # f. 评分
    # ------------------------------------------------------------------
    def _diff_stats(self, working_dir: str) -> tuple[int, int]:
        try:
            diff = self.client.git_diff(working_dir)
        except Exception:  # noqa: BLE001 - diff 不可得视为无改动
            return 0, 0
        text = (diff or {}).get("modified") or ""
        files = sum(1 for line in text.splitlines() if line.startswith("diff --git"))
        lines = sum(
            1
            for line in text.splitlines()
            if (line.startswith("+") or line.startswith("-")) and not line.startswith(("+++", "---"))
        )
        return files, lines

    def _build_signals(
        self,
        observed: dict,
        cur_test: tuple[int, int] | None,
        diff_files: int,
        diff_lines: int,
    ) -> ProgressSignals:
        failed_delta = passed_delta = 0
        regression = False
        if cur_test is not None and self._prev_test is not None:
            prev_passed, prev_failed = self._prev_test
            cur_passed, cur_failed = cur_test
            failed_delta = prev_failed - cur_failed
            passed_delta = cur_passed - prev_passed
            regression = detect_regression(prev_passed, prev_failed, cur_passed, cur_failed, diff_lines)
        if regression:
            self._regression_count += 1
        else:
            self._regression_count = 0
        signals = ProgressSignals(
            failed_tests_delta=failed_delta,
            passed_tests_delta=passed_delta,
            compile_errors_delta=0,
            diff_files=diff_files,
            diff_lines=diff_lines,
            new_evidence=observed["new_evidence"],
            repeated_action=observed["repeated"],
            regression=regression,
            plan_steps_completed=0,
        )
        if cur_test is not None:
            self._prev_test = cur_test
        return signals

    def _record_score(
        self, run: TaskRun, iteration: int, signals: ProgressSignals, score: float, llm_calls: list[LlmCall]
    ) -> None:
        self._scores.append(score)
        self.session.add(
            ProgressSignal(
                run_id=self.run_uuid,
                iteration=iteration,
                signals=signals.to_dict(),
                score=score,
            )
        )
        self.session.add(
            LoopIteration(
                run_id=self.run_uuid,
                iteration=iteration,
                phase=run.current_phase,
                progress_score=score,
                score_evidence=signals.to_dict(),
                strategy=self._current_strategy,
                pressure_mode=run.pressure_mode,
                ended_at=utcnow(),
            )
        )
        # 回写本轮 llm_calls 的有效性
        reason = None
        if score < 0.5:
            if signals.repeated_action:
                reason = "repeated_action: 动作与历史重复，无新进展"
            elif signals.regression:
                reason = "regression: 测试出现回退且 diff 无变化"
            elif signals.new_evidence == 0:
                reason = "no_new_evidence: 本轮无新工具观测证据"
        for call in llm_calls:
            call.progress_score = score
            call.effective = score >= 0.5
            call.inefficiency_reason = reason
        self.emit_event(
            run,
            EventType.PROGRESS_SCORED,
            {
                "iteration": iteration,
                "score": score,
                "signals": signals.to_dict(),
            },
        )
        self._commit()

    # ------------------------------------------------------------------
    # g. 验收 / 审批 / 策略 / 压力 / 阶段预算
    # ------------------------------------------------------------------
    def _acceptance_met(self, task: Task, conv_status: str, cur_test: tuple[int, int] | None) -> bool:
        if conv_status != "finished":
            return False
        if self._tests_required(task):
            return cur_test is not None and cur_test[1] == 0 and cur_test[0] > 0
        return True

    def _approval_gate(self, run: TaskRun, iteration: int, hits: list[risk_mod.RiskHit]) -> bool:
        hit = hits[0]
        approval = Approval(
            run_id=self.run_uuid,
            action_type=hit.action_type.value,
            description=hit.description,
            risk=hit.risk,
            payload={
                "iteration": iteration,
                "hits": [
                    {"action_type": h.action_type.value, "description": h.description, "risk": h}
                    if False
                    else {"action_type": h.action_type.value, "description": h.description, "risk": h.risk}
                    for h in hits
                ],
            },
        )
        self.session.add(approval)
        self.emit_event(
            run,
            EventType.APPROVAL_REQUESTED,
            {
                "iteration": iteration,
                "action_type": hit.action_type.value,
                "description": hit.description,
                "risk": hit.risk,
            },
        )
        self.transition(run, RunStatus.WAITING_APPROVAL)
        self._commit()

        deadline = time.monotonic() + self.approval_timeout_seconds
        while time.monotonic() < deadline:
            self.session.refresh(approval)
            status = str(approval.status)
            if status != "pending":
                self.emit_event(
                    run,
                    EventType.APPROVAL_DECIDED,
                    {
                        "iteration": iteration,
                        "status": status,
                        "decision_note": approval.decision_note,
                    },
                )
                self._last_tick = time.monotonic()  # 审批等待不计入 active runtime
                if status in ("approved", "modified"):
                    return True
                self._feedback = (
                    f"危险动作被拒绝（{hit.description}）：{approval.decision_note or '无说明'}。"
                    "请改用安全的方式推进任务。"
                )
                return False
            time.sleep(self.approval_poll_interval)
        # 审批超时：按拒绝处理
        self._feedback = f"审批超时（{self.approval_timeout_seconds}s 未决），动作按拒绝处理。"
        self._last_tick = time.monotonic()
        return False

    def _strategy_step(self, run: TaskRun, iteration: int, working_dir: str) -> None:
        decision = decide_strategy(
            recent_scores=self._scores,
            repeated_action_count=self._repeated_count,
            pressure_mode=PressureMode(run.pressure_mode or PressureMode.NORMAL.value),
            current_strategy=self._current_strategy,
            regression_count=self._regression_count,
        )
        if not decision.should_switch:
            return
        snapshot = self._snapshot_dict(run, Strategy(run.strategy))
        self._strategy_switches.append(
            {
                "iteration": iteration,
                "from": self._current_strategy,
                "to": decision.new_strategy,
                "reason": decision.reason,
                "remaining_budget": snapshot,
            }
        )
        self.emit_event(
            run,
            EventType.STRATEGY_SWITCHED,
            {
                "iteration": iteration,
                "old_strategy": self._current_strategy,
                "new_strategy": decision.new_strategy,
                "reason": decision.reason,
                "remaining_budget": snapshot,
            },
        )
        self._current_strategy = decision.new_strategy
        if decision.new_strategy == STRATEGY_ROLLBACK:
            self._rollback(run, iteration, working_dir)

    def _rollback(self, run: TaskRun, iteration: int, working_dir: str) -> None:
        out = self.client.execute_bash("git reset --hard HEAD~1", timeout=60, cwd=working_dir)
        self.emit_event(
            run,
            EventType.ROLLBACK,
            {
                "iteration": iteration,
                "command": "git reset --hard HEAD~1",
                "exit_code": out.get("exit_code"),
            },
        )
        self.transition(run, RunStatus.REPLANNING)
        self._regression_count = 0

    def _pressure_step(self, run: TaskRun, budget: TaskBudgetManager) -> None:
        snapshot = budget.snapshot()
        mode = compute_pressure_mode(
            deadline_at=run.deadline_at,
            max_wall_time_seconds=snapshot.max_wall_time_seconds,
            active_runtime_ms=int(run.active_runtime_ms or 0),
            max_active_runtime_seconds=snapshot.max_active_runtime_seconds,
            remaining_tokens=snapshot.remaining_tokens,
            max_total_tokens=snapshot.max_total_tokens,
        )
        if mode.value != run.pressure_mode:
            old = run.pressure_mode
            run.pressure_mode = mode.value
            self.emit_event(run, EventType.PRESSURE_CHANGED, {"from": old, "to": mode.value})

    def _phase_budget_step(self, run: TaskRun, iteration: int, budget: TaskBudgetManager) -> None:
        """阶段预算检查与重分配：消耗过快无进展 -> capped 并把余额转移给后续阶段。"""
        phases = self.session.query(TaskPhase).filter_by(run_id=self.run_uuid).order_by(TaskPhase.id).all()
        if not phases:
            return
        snapshot = budget.snapshot()
        current = next((p for p in phases if p.phase == run.current_phase), None)
        if current is None or current.status != "active":
            return
        last_score = self._scores[-1] if self._scores else 1.0
        if current.budget_tokens and current.used_tokens >= current.budget_tokens and last_score < 0.3:
            current.status = "capped"
            nxt = next((p for p in phases if p.status == "pending"), None)
            if nxt is not None:
                nxt.budget_tokens += current.budget_tokens  # 余额转移（此处为简化：转移全额预算）
            self.emit_event(
                run,
                EventType.BUDGET_REALLOCATED,
                {
                    "iteration": iteration,
                    "phase": current.phase,
                    "action": "capped",
                    "reason": f"phase token budget exhausted with low progress (score={last_score:.2f})",
                    "used_tokens": current.used_tokens,
                },
            )
        current.used_tokens = snapshot.used_tokens

    def _advance_phase(self, run: TaskRun, cur_test: tuple[int, int] | None) -> None:
        old = run.current_phase or Phase.SCAN.value
        nxt = {
            Phase.SCAN.value: Phase.ANALYZE.value,
            Phase.ANALYZE.value: Phase.MODIFY.value,
            Phase.MODIFY.value: Phase.VERIFY.value,
            Phase.VERIFY.value: (
                Phase.REPAIR.value if (cur_test and cur_test[1] > 0) else Phase.MODIFY.value
            ),
            Phase.REPAIR.value: Phase.VERIFY.value,
            Phase.SUMMARIZE.value: Phase.SUMMARIZE.value,
        }.get(old, Phase.MODIFY.value)
        if nxt != old:
            run.current_phase = nxt
            self.emit_event(run, EventType.PHASE_CHANGED, {"from": old, "to": nxt})

    # ------------------------------------------------------------------
    # h. checkpoint
    # ------------------------------------------------------------------
    def _checkpoint(self, run: TaskRun, iteration: int, working_dir: str) -> None:
        out = self.client.execute_bash(
            f"git add -A && git commit -q -m 'budgetloop checkpoint iteration {iteration}' --allow-empty "
            "&& git rev-parse HEAD",
            timeout=120,
            cwd=working_dir,
        )
        git_ref = (out.get("stdout") or "").strip().splitlines()[-1] if out.get("stdout") else "unknown"
        if out.get("exit_code") not in (0, None):
            self.emit_event(
                run,
                EventType.WARNING,
                {
                    "iteration": iteration,
                    "reason": f"checkpoint commit failed: exit {out.get('exit_code')}",
                },
            )
            return
        self.session.add(
            Checkpoint(
                run_id=self.run_uuid,
                iteration=iteration,
                git_ref=git_ref[:100],
                note=f"iteration {iteration} checkpoint",
            )
        )
        self.emit_event(run, EventType.CHECKPOINT_CREATED, {"iteration": iteration, "git_ref": git_ref[:100]})

    # ------------------------------------------------------------------
    # 结束处理
    # ------------------------------------------------------------------
    def _finish(self, run: TaskRun, task: Task, status: RunStatus, working_dir: str) -> None:
        run.finished_at = utcnow()
        self._write_final_report(run, task, status, working_dir)
        self.emit_event(
            run,
            EventType.RUN_FINISHED,
            {
                "run_id": self.run_id,
                "status": status.value,
                "iterations": run.iteration,
            },
        )
        self._commit()
        self._destroy_workspace()

    def _fail(self, run: TaskRun, exc: Exception) -> None:
        with suppress(Exception):
            self.session.rollback()
        run.error = f"{type(exc).__name__}: {exc}"
        owner = self._work_session(run)
        if owner is not None and owner.workspace_status == "PROVISIONING":
            owner.workspace_status = "FAILED"
            owner.workspace_error = run.error
            owner.updated_at = utcnow()
        try:
            if not RunStatus(str(run.status)).is_terminal:
                self.transition(run, RunStatus.FAILED)
            run.finished_at = utcnow()
            self.emit_event(run, EventType.WARNING, {"reason": run.error})
            self._commit()
        except Exception:  # noqa: BLE001
            pass
        self._destroy_workspace()

    def _write_final_report(self, run: TaskRun, task: Task, status: RunStatus, working_dir: str) -> None:
        strategy = Strategy(run.strategy)
        snapshot = self._snapshot_dict(run, strategy)
        try:
            diff = self.client.git_diff(working_dir)
            diff_text = (diff or {}).get("modified") or ""
        except Exception:  # noqa: BLE001
            diff_text = ""
        files_changed = [
            line.split(" b/")[-1] for line in diff_text.splitlines() if line.startswith("diff --git")
        ]
        diff_summary = diff_text[: settings.summary_max_chars]
        acceptance_result = {
            "met": status == RunStatus.COMPLETED,
            "criteria": getattr(task, "acceptance_criteria", None),
            "last_test": (
                {"passed": self._prev_test[0], "failed": self._prev_test[1]} if self._prev_test else None
            ),
        }
        totals = {
            "iterations": run.iteration,
            "active_runtime_ms": run.active_runtime_ms,
            "budget": snapshot,
            "scores": self._scores,
        }
        open_issues = (
            []
            if status == RunStatus.COMPLETED
            else [f"run ended with status {status.value}" + (f": {run.error}" if run.error else "")]
        )
        suggestions = []
        if self._strategy_switches:
            suggestions.append(f"共发生 {len(self._strategy_switches)} 次策略切换，详见 strategy_switches。")
        if status == RunStatus.BUDGET_EXHAUSTED:
            suggestions.append("预算耗尽：可考虑提高预算上限或缩小任务范围后重试。")

        report_md = self._render_report_md(
            run, task, status, acceptance_result, totals, open_issues, suggestions
        )
        artifact_ref = self._put_artifact(f"{self.run_id}/final_report.md", report_md.encode())
        self.session.add(
            FinalReport(
                run_id=self.run_uuid,
                status=status.value,
                acceptance_result=acceptance_result,
                files_changed=files_changed,
                diff_summary=diff_summary,
                totals=totals,
                strategy_switches=self._strategy_switches,
                open_issues=open_issues,
                suggestions=suggestions,
                report_md=report_md,
                artifact_ref=artifact_ref,
            )
        )

    @staticmethod
    def _render_report_md(run, task, status, acceptance_result, totals, open_issues, suggestions) -> str:
        lines = [
            f"# BudgetLoop 运行报告 {run.id}",
            "",
            f"- 任务: {getattr(task, 'name', '')}",
            f"- 状态: {status.value}",
            f"- 迭代数: {totals['iterations']}",
            f"- active runtime: {totals['active_runtime_ms']} ms",
            "",
            "## 验收",
            f"- 达成: {acceptance_result['met']}",
            f"- 标准: {acceptance_result.get('criteria') or '（未显式给出）'}",
        ]
        if acceptance_result.get("last_test"):
            t = acceptance_result["last_test"]
            lines.append(f"- 最终测试: passed={t['passed']} failed={t['failed']}")
        lines += ["", "## 开放问题"] + [f"- {i}" for i in open_issues or ["无"]]
        lines += ["", "## 建议"] + [f"- {s}" for s in suggestions or ["无"]]
        return "\n".join(lines)

    def _destroy_workspace(self) -> None:
        try:
            if self.client is not None and hasattr(self.client, "close"):
                self.client.close()
            if self.workspace_manager is not None:
                self.workspace_manager.destroy(self.run_id)
        except Exception:  # noqa: BLE001 - 清理失败不影响终态
            pass

    # ------------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------------
    @staticmethod
    def _work_session(run: TaskRun) -> WorkSession | None:
        owner = getattr(run, "work_session", None)
        return owner if isinstance(owner, WorkSession) else None

    def transition(self, run: TaskRun, to: RunStatus) -> RunStatus:
        frm = RunStatus(str(run.status))
        assert_transition(frm, to)
        run.status = to.value
        self.emit_event(run, EventType.STATE_CHANGED, {"from": frm.value, "to": to.value})
        return to

    def emit_event(self, run: TaskRun, type_: EventType, payload: dict) -> None:
        self.emit(self.session, self.run_uuid, type_.value, payload)

    def _budget(self, run: TaskRun) -> TaskBudgetManager:
        if self.budget_manager is None:
            self.budget_manager = TaskBudgetManager(self.session, self.run_uuid)
        return self.budget_manager

    def _snapshot_or_none(self, run: TaskRun, strategy: Strategy) -> BudgetSnapshot | None:
        if strategy == Strategy.NONE:
            return None
        try:
            return self._budget(run).snapshot()
        except Exception:  # noqa: BLE001
            return None

    def _snapshot_dict(self, run: TaskRun, strategy: Strategy) -> dict:
        snapshot = self._snapshot_or_none(run, strategy)
        return snapshot.to_dict() if snapshot else {}

    def _tick(self, run: TaskRun) -> None:
        now = time.monotonic()
        run.active_runtime_ms = int(run.active_runtime_ms or 0) + int((now - self._last_tick) * 1000)
        self._last_tick = now

    def _put_artifact(self, key: str, data: bytes) -> str | None:
        try:
            store = self.store
            if store is None:
                store = self.store = _get_store() if _get_store else _default_store()
            return store.put_bytes(key, data[: settings.artifact_max_bytes])
        except Exception:  # noqa: BLE001 - artifact 不可用不阻断主流程
            return None

    def _commit(self) -> None:
        self.session.commit()
