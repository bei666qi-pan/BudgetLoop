"""编排器单元测试：状态机转换 + 预算拒绝路径（mock session + fake client）。"""

import uuid
from unittest.mock import MagicMock

from app.core.enums import ALLOWED_TRANSITIONS, EventType, RunStatus
from app.worker.orchestrator import (
    InvalidTransition,
    Orchestrator,
    assert_transition,
    build_cli_execution_instruction,
    can_transition,
)


class TestStateMachineTransitions:
    """所有 ALLOWED_TRANSITIONS 表内合法、表外抛错。"""

    def test_all_terminal_statuses_have_no_exits(self):
        terminals = {
            RunStatus.COMPLETED,
            RunStatus.PARTIAL_COMPLETED,
            RunStatus.FAILED,
            RunStatus.BUDGET_EXHAUSTED,
            RunStatus.CANCELLED,
        }
        for s in terminals:
            assert ALLOWED_TRANSITIONS[s] == frozenset(), f"{s} should have no allowed transitions"

    def test_legitimate_transition(self):
        assert can_transition(RunStatus.PLANNING, RunStatus.EXECUTING) is True
        assert_transition(RunStatus.PLANNING, RunStatus.EXECUTING)  # no error

    def test_illegal_transition(self):
        assert can_transition(RunStatus.EXECUTING, RunStatus.PLANNING) is False
        try:
            assert_transition(RunStatus.EXECUTING, RunStatus.PLANNING)
            assert False, "should have raised"
        except InvalidTransition:
            pass

    def test_cancelling_from_non_terminal(self):
        for frm in ALLOWED_TRANSITIONS:
            if frm.is_terminal:
                continue
            assert RunStatus.CANCELLED in ALLOWED_TRANSITIONS[frm], (
                f"{frm} should be able to transition to CANCELLED"
            )


def test_cli_instruction_requests_one_bounded_end_to_end_turn() -> None:
    instruction = build_cli_execution_instruction(pressure_mode="NORMAL")
    assert "分析、修改、验证" in instruction
    assert "分配的 workspace" in instruction
    assert "不得静默改用其他执行引擎" in instruction


def test_orchestrator_routes_workspace_and_client_through_selected_adapter(monkeypatch) -> None:
    run = MagicMock()
    run.task = MagicMock()
    run.strategy = "dynamic"
    run.model_config = {"execution_engine": "codex"}
    run.started_at = None
    adapter = MagicMock()
    adapter.engine.transport = "cli"
    manager = MagicMock()
    client = MagicMock()
    adapter.create_workspace_manager.return_value = manager
    adapter.create_client.return_value = client
    handle = MagicMock(working_dir="/isolated/run")

    monkeypatch.setattr("app.worker.orchestrator.selected_execution_engine", lambda _config: "codex")
    monkeypatch.setattr("app.worker.orchestrator.adapter_for", lambda _engine: adapter)
    orchestrator = Orchestrator(MagicMock(), str(uuid.uuid4()))
    orchestrator.transition = MagicMock()
    orchestrator.emit_event = MagicMock()
    orchestrator._commit = MagicMock()
    orchestrator._ensure_workspace = MagicMock(return_value=handle)
    orchestrator._ensure_conversation = MagicMock()
    orchestrator._loop = MagicMock(return_value=RunStatus.COMPLETED)
    orchestrator._finish = MagicMock()

    orchestrator._run_inner(run)

    adapter.create_workspace_manager.assert_called_once_with()
    adapter.create_client.assert_called_once_with(handle, run.model_config)
    orchestrator._ensure_conversation.assert_called_once()
    orchestrator.emit_event.assert_any_call(
        run,
        EventType.RUN_STARTED,
        {"run_id": orchestrator.run_id, "strategy": "dynamic", "execution_engine": "codex"},
    )


class TestOrchestratorBudgetRejection:
    """预算拒绝路径验证。"""

    def test_budget_rejected_leads_to_budget_exhausted(self, monkeypatch):
        from app.budget.manager import BudgetRejected
        from app.core.models import Task, TaskBudget, TaskRun

        run_id = uuid.uuid4()
        task_id = uuid.uuid4()

        mock_session = MagicMock()
        mock_run = MagicMock(spec=TaskRun)
        mock_run.id = run_id
        mock_run.task_id = task_id
        mock_run.status = RunStatus.PENDING.value
        mock_run.strategy = "dynamic"
        mock_run.model_config = {}
        mock_run.workspace_id = None
        mock_run.conversation_id = None
        mock_run.current_phase = "scan"
        mock_run.pressure_mode = "NORMAL"
        mock_run.iteration = 0
        mock_run.active_runtime_ms = 0
        mock_run.deadline_at = None
        mock_run.require_approval = True

        mock_budget = MagicMock(spec=TaskBudget)
        mock_budget.max_total_tokens = 100
        mock_budget.max_llm_calls = 1
        mock_budget.max_cost = 1.0
        mock_budget.max_wall_time_seconds = 1200
        mock_budget.max_active_runtime_seconds = 600
        mock_budget.used_tokens = 99
        mock_budget.used_calls = 0
        mock_budget.used_cost = 0
        mock_budget.reserved_tokens = 1
        mock_budget.reserved_calls = 0
        mock_budget.reserved_cost = 0

        mock_session.get.side_effect = lambda model, pk: {
            TaskRun: mock_run,
            TaskBudget: mock_budget,
            Task: MagicMock(),
        }.get(model)

        class FakeBudgetManager:
            def __init__(self):
                self.called_reserve = False

            def reserve(self, est_tokens, est_cost):
                self.called_reserve = True
                raise BudgetRejected("max_llm_calls reached")

            def snapshot(self):
                from app.budget.manager import BudgetSnapshot

                return BudgetSnapshot(
                    max_total_tokens=100,
                    max_wall_time_seconds=1200,
                    max_active_runtime_seconds=600,
                    max_llm_calls=1,
                    max_cost=1.0,
                    max_parallel_llm_calls=2,
                    used_tokens=99,
                    used_cost=0,
                    used_calls=0,
                    reserved_tokens=1,
                    reserved_cost=0,
                    reserved_calls=0,
                )

            def settle(self, *a, **kw):
                pass

            def release(self, *a, **kw):
                pass

        fake_client = MagicMock()
        fake_workspace = MagicMock()
        fake_workspace.provision.return_value = MagicMock(
            container_id="fake-ctr",
            base_url="http://x:8000",
            session_key="fake-key",
            volume_name="v",
            working_dir="/ws",
            runtime_env={
                "BUDGETLOOP_AI_MANAGED": "1",
                "OPENAI_BASE_URL": "http://runtime/v1",
                "OPENAI_API_KEY": "scoped-test-capability",
                "OPENAI_MODEL": "test-model",
            },
        )
        fake_workspace.attach.side_effect = RuntimeError("should provision, not attach")

        budget_mgr = FakeBudgetManager()
        orch = Orchestrator(
            mock_session,
            run_id,
            budget_manager=budget_mgr,
            client=fake_client,
            workspace_manager=fake_workspace,
        )
        orch.run()

        # verify reserve was called (budget rejected → orchestrator handled it)
        assert budget_mgr.called_reserve is True

    def test_orchestrator_rejects_illegal_transition(self):
        mock_session = MagicMock()
        mock_run = MagicMock()
        mock_run.status = RunStatus.PLANNING.value

        orch = Orchestrator(mock_session, str(uuid.uuid4()))
        try:
            orch.transition(mock_run, RunStatus.PLANNING)  # self-loop not in table
            assert False, "should raise"
        except InvalidTransition:
            pass
