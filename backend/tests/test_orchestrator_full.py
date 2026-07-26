"""编排器全面测试：覆盖所有关键函数、边界情况与异常路径。"""
import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock, patch

import pytest

from app.budget.manager import BudgetRejected, BudgetSnapshot
from app.core.enums import ALLOWED_TRANSITIONS, ApprovalActionType, CallKind, EventType, Phase, PressureMode, RunStatus, Strategy
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
)
from app.scoring.signals import ProgressSignals
from app.worker import risk as risk_mod
from app.worker.openhands_client import AgentServerError
from app.worker.orchestrator import (
    DEFAULT_EST_COST,
    DEFAULT_EST_TOKENS,
    DEFAULT_MAX_LOOP_ITERATIONS,
    InvalidTransition,
    Orchestrator,
    _parse_ts,
    assert_transition,
    build_initial_message,
    build_iteration_instruction,
    can_transition,
)
from app.worker.workspace_manager import WorkspaceError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_run(**kw) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "status": RunStatus.PENDING.value,
        "strategy": Strategy.DYNAMIC.value,
        "model_config": {},
        "workspace_id": None,
        "conversation_id": None,
        "current_phase": Phase.SCAN.value,
        "pressure_mode": PressureMode.NORMAL.value,
        "iteration": 0,
        "active_runtime_ms": 0,
        "deadline_at": None,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "require_approval": True,
    }
    defaults.update(kw)
    run = MagicMock(spec=TaskRun)
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


def _make_task(**kw) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-task",
        "description": "Fix the login bug",
        "acceptance_criteria": "All login tests pass",
        "require_approval": True,
    }
    defaults.update(kw)
    task = MagicMock(spec=Task)
    for k, v in defaults.items():
        setattr(task, k, v)
    return task


def _make_budget_snapshot(**kw) -> BudgetSnapshot:
    defaults = {
        "max_total_tokens": 100_000,
        "max_wall_time_seconds": 1200,
        "max_active_runtime_seconds": 600,
        "max_llm_calls": 20,
        "max_cost": 5.0,
        "max_parallel_llm_calls": 2,
        "used_tokens": 5000,
        "used_cost": 0.5,
        "used_calls": 3,
        "reserved_tokens": 1000,
        "reserved_cost": 0.1,
        "reserved_calls": 0,
    }
    defaults.update(kw)
    return BudgetSnapshot(**defaults)


def _make_orch(mock_session=None, run_id=None, **kw) -> Orchestrator:
    if mock_session is None:
        mock_session = MagicMock()
    if run_id is None:
        run_id = uuid.uuid4()
    return Orchestrator(mock_session, run_id, **kw)


# ---------------------------------------------------------------------------
# 1. build_initial_message
# ---------------------------------------------------------------------------

class TestBuildInitialMessage:
    """build_initial_message：各压力模式、有无 snapshot、边界输入。"""

    def test_with_snapshot_all_modes(self):
        snapshot = _make_budget_snapshot()
        for mode in PressureMode:
            msg = build_initial_message(
                task_description="desc",
                acceptance_criteria="crit",
                phase=Phase.SCAN.value,
                snapshot=snapshot,
                pressure_mode=mode,
            )
            assert "desc" in msg
            assert "crit" in msg
            assert "剩余预算" in msg
            assert mode.value in msg

    def test_without_snapshot(self):
        msg = build_initial_message(
            task_description="desc",
            acceptance_criteria="crit",
            phase=Phase.ANALYZE.value,
            snapshot=None,
            pressure_mode=PressureMode.CRITICAL,
        )
        assert "不跟踪预算" in msg

    def test_empty_acceptance_criteria(self):
        snapshot = _make_budget_snapshot()
        msg = build_initial_message(
            task_description="desc",
            acceptance_criteria=None,
            phase=Phase.MODIFY.value,
            snapshot=snapshot,
            pressure_mode=PressureMode.CONSERVATIVE,
        )
        assert "未显式给出" in msg

    def test_pressure_mode_as_string(self):
        snapshot = _make_budget_snapshot()
        msg = build_initial_message(
            task_description="desc",
            acceptance_criteria=None,
            phase=Phase.SCAN.value,
            snapshot=snapshot,
            pressure_mode="NORMAL",
        )
        assert "NORMAL" in msg


# ---------------------------------------------------------------------------
# 2. build_iteration_instruction
# ---------------------------------------------------------------------------

class TestBuildIterationInstruction:
    """build_iteration_instruction：各压力模式、评分/反馈边界。"""

    def test_all_pressure_modes(self):
        for mode in PressureMode:
            inst = build_iteration_instruction(
                iteration=1,
                phase=Phase.SCAN.value,
                pressure_mode=mode,
            )
            assert f"iteration 1" in inst
            assert mode.value in inst

    def test_with_last_score_and_feedback(self):
        inst = build_iteration_instruction(
            iteration=5,
            phase=Phase.MODIFY.value,
            pressure_mode=PressureMode.CRITICAL,
            last_score=0.3,
            feedback="请避免删除文件",
        )
        assert "0.30" in inst
        assert "人工审批反馈" in inst
        assert "请避免删除文件" in inst

    def test_without_last_score_and_feedback(self):
        inst = build_iteration_instruction(
            iteration=2,
            phase=Phase.VERIFY.value,
            pressure_mode=PressureMode.NORMAL,
        )
        assert "上一轮进展评分" not in inst
        assert "人工审批反馈" not in inst


# ---------------------------------------------------------------------------
# 3. _parse_ts
# ---------------------------------------------------------------------------

class TestParseTs:
    """_parse_ts：有效时间戳、None、空串、非法格式。"""

    def test_valid_iso(self):
        dt = _parse_ts("2025-06-15T12:30:00")
        assert dt == datetime(2025, 6, 15, 12, 30)
        assert dt.tzinfo is None

    def test_iso_with_z(self):
        dt = _parse_ts("2025-06-15T12:30:00Z")
        assert dt == datetime(2025, 6, 15, 12, 30, tzinfo=timezone.utc)

    @pytest.mark.parametrize("value", [None, "", 0, False])
    def test_falsy_values_return_none(self, value):
        assert _parse_ts(value) is None

    def test_invalid_format(self):
        assert _parse_ts("not-a-date") is None


# ---------------------------------------------------------------------------
# 4. _call_kind
# ---------------------------------------------------------------------------

class TestCallKind:
    """_call_kind：condenser/agent/other 分类。"""

    def test_condenser(self):
        assert Orchestrator._call_kind("condenser") == CallKind.CONDENSER
        assert Orchestrator._call_kind("my-condenser-123") == CallKind.CONDENSER

    def test_agent(self):
        assert Orchestrator._call_kind("agent") == CallKind.AGENT
        assert Orchestrator._call_kind("primary-agent-7") == CallKind.AGENT

    def test_other(self):
        assert Orchestrator._call_kind("unknown") == CallKind.OTHER
        assert Orchestrator._call_kind("") == CallKind.OTHER


# ---------------------------------------------------------------------------
# 5. _message_text
# ---------------------------------------------------------------------------

class TestMessageText:
    """_message_text：各种消息结构提取文本。"""

    def test_single_text_content(self):
        ev = {"llm_message": {"content": [{"text": "hello"}]}}
        assert Orchestrator._message_text(ev) == "hello"

    def test_multiple_content_parts(self):
        ev = {"llm_message": {"content": [{"text": "a"}, {"text": "b"}]}}
        assert Orchestrator._message_text(ev) == "a\nb"

    def test_empty_content(self):
        ev = {"llm_message": {"content": []}}
        assert Orchestrator._message_text(ev) == ""

    def test_missing_llm_message(self):
        assert Orchestrator._message_text({}) == ""

    def test_non_dict_content_entries(self):
        ev = {"llm_message": {"content": [{"text": "ok"}, "plain_string"]}}
        assert Orchestrator._message_text(ev) == "ok"


# ---------------------------------------------------------------------------
# 6. can_transition / assert_transition 边界
# ---------------------------------------------------------------------------

class TestTransitionEdgeCases:
    """can_transition/assert_transition：终态不可转换、字符串兼容。"""

    @pytest.mark.parametrize("terminal", [
        RunStatus.COMPLETED, RunStatus.PARTIAL_COMPLETED,
        RunStatus.FAILED, RunStatus.BUDGET_EXHAUSTED, RunStatus.CANCELLED,
    ])
    def test_terminal_to_any_raises(self, terminal):
        assert can_transition(terminal, RunStatus.PLANNING) is False
        with pytest.raises(InvalidTransition):
            assert_transition(terminal, RunStatus.PLANNING)

    def test_string_arguments(self):
        assert can_transition("PENDING", "PLANNING") is True
        assert_transition("PLANNING", "EXECUTING")  # no error

    def test_planning_self_loop_invalid(self):
        assert can_transition(RunStatus.PLANNING, RunStatus.PLANNING) is False

    def test_completed_to_self_raises(self):
        with pytest.raises(InvalidTransition):
            assert_transition(RunStatus.COMPLETED, RunStatus.COMPLETED)


# ---------------------------------------------------------------------------
# 7. _tests_required
# ---------------------------------------------------------------------------

class TestTestsRequired:
    """_tests_required：验收标准关键词匹配。"""

    @pytest.mark.parametrize("criteria", [
        "run tests before approval",
        "需要运行测试验证",
        "add unittests for coverage",
        "use pytest to verify",
        "please test everything",
    ])
    def test_tests_required(self, criteria):
        orch = _make_orch()
        task = _make_task(acceptance_criteria=criteria)
        assert orch._tests_required(task) is True

    def test_no_keyword(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="fix the bug and commit")
        assert orch._tests_required(task) is False

    def test_none_criteria(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria=None)
        assert orch._tests_required(task) is False


# ---------------------------------------------------------------------------
# 8. _advance_phase
# ---------------------------------------------------------------------------

class TestAdvancePhase:
    """_advance_phase：各阶段推进规则。"""

    def test_scan_to_analyze(self):
        orch = _make_orch()
        run = _make_run(current_phase=Phase.SCAN.value)
        orch._advance_phase(run, None)
        assert run.current_phase == Phase.ANALYZE.value

    def test_verify_to_repair_when_tests_fail(self):
        orch = _make_orch()
        run = _make_run(current_phase=Phase.VERIFY.value)
        orch._advance_phase(run, (5, 2))  # 2 failures
        assert run.current_phase == Phase.REPAIR.value

    def test_verify_to_modify_when_tests_pass(self):
        orch = _make_orch()
        run = _make_run(current_phase=Phase.VERIFY.value)
        orch._advance_phase(run, (5, 0))  # all passed
        assert run.current_phase == Phase.MODIFY.value

    def test_summarize_stays(self):
        orch = _make_orch()
        run = _make_run(current_phase=Phase.SUMMARIZE.value)
        orch._advance_phase(run, None)
        assert run.current_phase == Phase.SUMMARIZE.value

    def test_repair_to_verify(self):
        orch = _make_orch()
        run = _make_run(current_phase=Phase.REPAIR.value)
        orch._advance_phase(run, None)
        assert run.current_phase == Phase.VERIFY.value


# ---------------------------------------------------------------------------
# 9. _acceptance_met
# ---------------------------------------------------------------------------

class TestAcceptanceMet:
    """_acceptance_met：完成判定逻辑。"""

    def test_finished_all_pass(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="run tests")
        assert orch._acceptance_met(task, "finished", (3, 0)) is True

    def test_finished_with_failures(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="run tests")
        assert orch._acceptance_met(task, "finished", (3, 2)) is False

    def test_not_finished_even_with_passing_tests(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="run tests")
        assert orch._acceptance_met(task, "idle", (3, 0)) is False

    def test_no_test_requirement_finished(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="just do it")
        assert orch._acceptance_met(task, "finished", None) is True

    def test_no_test_requirement_not_finished(self):
        orch = _make_orch()
        task = _make_task(acceptance_criteria="just do it")
        assert orch._acceptance_met(task, "idle", None) is False


# ---------------------------------------------------------------------------
# 10. _render_report_md
# ---------------------------------------------------------------------------

class TestRenderReportMd:
    """_render_report_md：报告渲染输出验证。"""

    def test_full_report(self):
        run = MagicMock()
        run.id = uuid.uuid4()
        task = _make_task(name="My Task")
        status = RunStatus.COMPLETED
        acceptance_result = {
            "met": True,
            "criteria": "all tests pass",
            "last_test": {"passed": 5, "failed": 0},
        }
        totals = {"iterations": 3, "active_runtime_ms": 45000}
        open_issues: list = []
        suggestions: list = []

        report = Orchestrator._render_report_md(
            run, task, status, acceptance_result, totals, open_issues, suggestions
        )
        assert "# BudgetLoop" in report
        assert "My Task" in report
        assert "COMPLETED" in report
        assert "passed=5" in report
        assert "无" in report  # 开放问题/建议默认值

    def test_report_with_issues_and_suggestions(self):
        run = MagicMock()
        run.id = uuid.uuid4()
        task = _make_task()
        status = RunStatus.BUDGET_EXHAUSTED
        acceptance_result = {"met": False, "criteria": None, "last_test": None}
        totals = {"iterations": 10, "active_runtime_ms": 120000}
        open_issues = ["ran out of budget"]
        suggestions = ["increase max_tokens"]

        report = Orchestrator._render_report_md(
            run, task, status, acceptance_result, totals, open_issues, suggestions
        )
        assert "BUDGET_EXHAUSTED" in report
        assert "ran out of budget" in report
        assert "increase max_tokens" in report


# ---------------------------------------------------------------------------
# 11. _record_events
# ---------------------------------------------------------------------------

class TestRecordEvents:
    """_record_events：ActionEvent/ObservationEvent 配对、指纹、风险。"""

    def test_action_observation_pair(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        events = [
            {"kind": "ActionEvent", "tool_call_id": "tc1", "tool_name": "bash",
             "action": {"command": "ls"}, "timestamp": "2025-06-15T12:00:00"},
            {"kind": "ObservationEvent", "tool_call_id": "tc1",
             "observation": {"exit_code": 0, "stdout": "file.py"},
             "timestamp": "2025-06-15T12:00:01"},
        ]
        result = orch._record_events(run, 1, events)
        assert result["new_evidence"] == 1
        assert result["repeated"] is False
        # ToolCall 被写入 session
        assert session.add.called

    def test_repeated_action_detection(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        ev = {"kind": "ActionEvent", "tool_call_id": "tc1", "tool_name": "bash",
              "action": {"command": "ls -la"}, "timestamp": "2025-06-15T12:00:00"}
        obs = {"kind": "ObservationEvent", "tool_call_id": "tc1",
               "observation": {"exit_code": 0}, "timestamp": "2025-06-15T12:00:01"}

        orch._record_events(run, 1, [ev, obs])
        result = orch._record_events(run, 2, [ev, obs])
        assert result["repeated"] is True
        assert orch._repeated_count == 1

    def test_risk_hits_included(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        events = [
            {"kind": "ActionEvent", "tool_call_id": "tc1", "tool_name": "bash",
             "action": {"command": "rm -rf /tmp/x"}, "timestamp": "2025-06-15T12:00:00"},
            {"kind": "ObservationEvent", "tool_call_id": "tc1",
             "observation": {"exit_code": 0}, "timestamp": "2025-06-15T12:00:01"},
        ]
        result = orch._record_events(run, 1, events)
        assert len(result["risk_hits"]) > 0

    def test_no_risk_for_safe_action(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        events = [
            {"kind": "ActionEvent", "tool_call_id": "tc1", "tool_name": "read",
             "action": {"path": "file.py"}, "timestamp": "2025-06-15T12:00:00"},
            {"kind": "ObservationEvent", "tool_call_id": "tc1",
             "observation": {"content": "data"}, "timestamp": "2025-06-15T12:00:01"},
        ]
        result = orch._record_events(run, 1, events)
        assert result["risk_hits"] == []


# ---------------------------------------------------------------------------
# 12. _record_llm_calls
# ---------------------------------------------------------------------------

class TestRecordLlmCalls:
    """_record_llm_calls：stats cursor 增量、多 usage_id。"""

    def test_single_usage_id(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        info = {
            "stats": {
                "usage_to_metrics": {
                    "agent": {
                        "token_usages": [{"prompt_tokens": 100, "completion_tokens": 50}],
                        "costs": [0.01],
                        "response_latencies": [1.2],
                    }
                }
            }
        }
        calls, total_tokens, total_cost = orch._record_llm_calls(run, 1, info)
        assert len(calls) == 1
        assert calls[0].call_kind == CallKind.AGENT.value
        assert total_tokens == 150
        assert session.add.called

    def test_response_scoped_metric_objects_match_by_response_id(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()
        info = {
            "stats": {
                "usage_to_metrics": {
                    "agent": {
                        "token_usages": [
                            {
                                "response_id": "response-2",
                                "prompt_tokens": 100,
                                "completion_tokens": 20,
                            }
                        ],
                        "costs": [
                            {"response_id": "response-2", "cost": 0.03},
                        ],
                        "response_latencies": [
                            {"response_id": "response-2", "latency": 25.2814},
                        ],
                    }
                }
            }
        }

        calls, total_tokens, total_cost = orch._record_llm_calls(run, 1, info)

        assert total_tokens == 120
        assert total_cost == pytest.approx(0.03)
        assert calls[0].duration_ms == 25_281
        assert calls[0].estimated_cost == pytest.approx(0.03)

    def test_multiple_usage_ids_incremental(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        info1 = {
            "stats": {
                "usage_to_metrics": {
                    "agent": {
                        "token_usages": [{"prompt_tokens": 100, "completion_tokens": 50}],
                        "costs": [0.01],
                        "response_latencies": [1.0],
                    }
                }
            }
        }
        orch._record_llm_calls(run, 1, info1)

        # 第二轮：多了 1 个新 token usage
        info2 = {
            "stats": {
                "usage_to_metrics": {
                    "agent": {
                        "token_usages": [
                            {"prompt_tokens": 100, "completion_tokens": 50},
                            {"prompt_tokens": 200, "completion_tokens": 100},
                        ],
                        "costs": [0.01, 0.02],
                        "response_latencies": [1.0, 1.5],
                    }
                }
            }
        }
        calls, total_tokens, total_cost = orch._record_llm_calls(run, 2, info2)
        assert len(calls) == 1  # 仅增量
        assert total_tokens == 300

    def test_missing_stats(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        calls, total_tokens, total_cost = orch._record_llm_calls(run, 1, {})
        assert calls == []
        assert total_tokens == 0
        assert total_cost == 0.0


# ---------------------------------------------------------------------------
# 13. _build_signals
# ---------------------------------------------------------------------------

class TestBuildSignals:
    """_build_signals：测试对比、回归检测、prev_test 追踪。"""

    def test_no_prev_no_current(self):
        orch = _make_orch()
        signals = orch._build_signals({"new_evidence": 2, "repeated": False}, None, 1, 5)
        assert isinstance(signals, ProgressSignals)
        assert signals.new_evidence == 2
        assert signals.failed_tests_delta == 0

    def test_regression_detected(self):
        orch = _make_orch()
        orch._prev_test = (5, 2)
        signals = orch._build_signals(
            {"new_evidence": 1, "repeated": False}, (4, 3), 0, 0
        )
        assert signals.regression is True
        assert orch._regression_count == 1

    def test_improvement_no_regression(self):
        orch = _make_orch()
        orch._prev_test = (3, 4)
        signals = orch._build_signals(
            {"new_evidence": 1, "repeated": False}, (5, 2), 3, 20
        )
        assert signals.regression is False
        assert signals.failed_tests_delta == 2
        assert signals.passed_tests_delta == 2
        assert orch._regression_count == 0

    def test_prev_test_updated(self):
        orch = _make_orch()
        orch._build_signals({"new_evidence": 1, "repeated": False}, (10, 1), 1, 5)
        assert orch._prev_test == (10, 1)


# ---------------------------------------------------------------------------
# 14. _record_score
# ---------------------------------------------------------------------------

class TestRecordScore:
    """_record_score：评分记录、低分原因分配。"""

    def test_high_score_effective(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        signals = ProgressSignals(new_evidence=3, diff_lines=10)
        calls = [MagicMock(spec=LlmCall) for _ in range(2)]

        orch._record_score(run, 1, signals, 0.8, calls)
        assert len(orch._scores) == 1
        assert orch._scores[0] == 0.8
        for c in calls:
            assert c.progress_score == 0.8
            assert c.effective is True
            assert c.inefficiency_reason is None

    def test_low_score_repeated_reason(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        signals = ProgressSignals(repeated_action=True)
        calls = [MagicMock(spec=LlmCall)]

        orch._record_score(run, 1, signals, 0.3, calls)
        assert calls[0].inefficiency_reason is not None
        assert "repeated_action" in calls[0].inefficiency_reason

    def test_low_score_no_evidence_reason(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run()

        signals = ProgressSignals(new_evidence=0, diff_lines=0)
        calls = [MagicMock(spec=LlmCall)]

        orch._record_score(run, 1, signals, 0.2, calls)
        assert calls[0].inefficiency_reason is not None
        assert "no_new_evidence" in calls[0].inefficiency_reason


# ---------------------------------------------------------------------------
# 15. _strategy_step
# ---------------------------------------------------------------------------

class TestStrategyStep:
    """_strategy_step：策略切换与 rollback 触发。"""

    def test_no_switch(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run(pressure_mode=PressureMode.NORMAL.value)
        orch._scores = [0.8, 0.9, 0.85]

        orch._strategy_step(run, 5, "/ws")
        assert len(orch._strategy_switches) == 0

    def test_switch_to_rollback_triggers_git_reset(self):
        session = MagicMock()
        client = MagicMock()
        client.execute_bash.return_value = {"exit_code": 0, "stdout": ""}
        orch = _make_orch(mock_session=session, client=client)
        # REPLANNING is allowed from EVALUATING
        run = _make_run(pressure_mode=PressureMode.NORMAL.value, status=RunStatus.EVALUATING.value)
        orch._scores = [0.2, 0.1, 0.1]
        orch._repeated_count = 5
        orch._regression_count = 3  # triggers regression rollback

        orch._strategy_step(run, 5, "/ws")
        client.execute_bash.assert_called()
        assert orch._current_strategy == "rollback"


# ---------------------------------------------------------------------------
# 16. _rollback
# ---------------------------------------------------------------------------

class TestRollback:
    """_rollback：git reset 命令与 REPLANNING 转换。"""

    def test_rollback_command_and_transition(self):
        session = MagicMock()
        client = MagicMock()
        client.execute_bash.return_value = {"exit_code": 0, "stdout": ""}
        orch = _make_orch(mock_session=session, client=client)
        # REPLANNING is allowed from EVALUATING
        run = _make_run(status=RunStatus.EVALUATING.value)

        orch._rollback(run, 3, "/ws")
        args, _ = client.execute_bash.call_args
        assert "git reset --hard HEAD~1" in args[0]
        assert orch._regression_count == 0
        assert run.status == RunStatus.REPLANNING.value


# ---------------------------------------------------------------------------
# 17. _pressure_step
# ---------------------------------------------------------------------------

class TestPressureStep:
    """_pressure_step：模式切换、同模式 no-op。"""

    def test_pressure_change(self):
        session = MagicMock()
        # 构造一个预算极少的快照，迫使 pressure 上升到 CRITICAL
        budget_mgr = MagicMock()
        budget_mgr.snapshot.return_value = BudgetSnapshot(
            max_total_tokens=100, max_wall_time_seconds=1200,
            max_active_runtime_seconds=600, max_llm_calls=20, max_cost=5.0,
            max_parallel_llm_calls=2, used_tokens=95, used_cost=4.95, used_calls=19,
            reserved_tokens=0, reserved_cost=0, reserved_calls=0,
        )
        orch = _make_orch(mock_session=session, budget_manager=budget_mgr)
        run = _make_run(pressure_mode=PressureMode.NORMAL.value, active_runtime_ms=590_000)

        orch._pressure_step(run, budget_mgr)
        assert run.pressure_mode == PressureMode.CRITICAL.value

    def test_same_mode_no_change(self):
        budget_mgr = MagicMock()
        budget_mgr.snapshot.return_value = BudgetSnapshot(
            max_total_tokens=100_000, max_wall_time_seconds=1200,
            max_active_runtime_seconds=600, max_llm_calls=20, max_cost=5.0,
            max_parallel_llm_calls=2, used_tokens=1000, used_cost=0.01, used_calls=1,
            reserved_tokens=0, reserved_cost=0, reserved_calls=0,
        )
        orch = _make_orch(budget_manager=budget_mgr)
        run = _make_run(pressure_mode=PressureMode.NORMAL.value, active_runtime_ms=1000)

        old = run.pressure_mode
        orch._pressure_step(run, budget_mgr)
        assert run.pressure_mode == old


# ---------------------------------------------------------------------------
# 18. _phase_budget_step
# ---------------------------------------------------------------------------

class TestPhaseBudgetStep:
    """_phase_budget_step：capped 阶段、预算转移、边界。"""

    def test_no_phases_returns_early(self):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
        budget_mgr = MagicMock()

        orch = _make_orch(mock_session=session, budget_manager=budget_mgr)
        run = _make_run()
        orch._phase_budget_step(run, 5, budget_mgr)
        # 不应抛异常

    def test_phase_capped_and_budget_transferred(self):
        session = MagicMock()
        budget_mgr = MagicMock()
        budget_mgr.snapshot.return_value = BudgetSnapshot(
            max_total_tokens=100_000, max_wall_time_seconds=1200,
            max_active_runtime_seconds=600, max_llm_calls=20, max_cost=5.0,
            max_parallel_llm_calls=2, used_tokens=5000, used_cost=0.5, used_calls=3,
            reserved_tokens=0, reserved_cost=0, reserved_calls=0,
        )

        active_phase = MagicMock(spec=TaskPhase)
        active_phase.phase = Phase.MODIFY.value
        active_phase.status = "active"
        active_phase.budget_tokens = 1000
        active_phase.used_tokens = 1000

        pending_phase = MagicMock(spec=TaskPhase)
        pending_phase.phase = Phase.VERIFY.value
        pending_phase.status = "pending"
        pending_phase.budget_tokens = 500

        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            active_phase, pending_phase,
        ]

        orch = _make_orch(mock_session=session, budget_manager=budget_mgr)
        orch._scores = [0.2]  # low score
        run = _make_run(current_phase=Phase.MODIFY.value)

        orch._phase_budget_step(run, 5, budget_mgr)
        assert active_phase.status == "capped"
        assert pending_phase.budget_tokens == 1500  # 500 + 1000 transferred


# ---------------------------------------------------------------------------
# 19. _tick
# ---------------------------------------------------------------------------

class TestTick:
    """_tick：active runtime 累积。"""

    def test_tick_accumulates(self):
        import time

        orch = _make_orch()
        run = _make_run(active_runtime_ms=1000)

        start = time.monotonic()
        orch._last_tick = start - 0.5  # simulate 500ms elapsed
        orch._tick(run)
        assert run.active_runtime_ms >= 1000 + 400  # ~500ms added, allow tolerance


# ---------------------------------------------------------------------------
# 20. _diff_stats
# ---------------------------------------------------------------------------

class TestDiffStats:
    """_diff_stats：git diff 解析与错误回退。"""

    def test_diff_with_changes(self):
        client = MagicMock()
        client.git_diff.return_value = {
            "modified": "diff --git a/main.py b/main.py\n+foo\n-bar\ndiff --git a/util.py b/util.py\n+baz\n"
        }
        orch = _make_orch(client=client)
        files, lines = orch._diff_stats("/ws")
        assert files == 2
        assert lines == 3

    def test_diff_error_returns_zero(self):
        client = MagicMock()
        client.git_diff.side_effect = RuntimeError("no git")
        orch = _make_orch(client=client)
        files, lines = orch._diff_stats("/ws")
        assert files == 0
        assert lines == 0

    def test_no_modified_key(self):
        client = MagicMock()
        client.git_diff.return_value = {}
        orch = _make_orch(client=client)
        files, lines = orch._diff_stats("/ws")
        assert files == 0
        assert lines == 0


# ---------------------------------------------------------------------------
# 21. _checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    """_checkpoint：git commit 与错误处理。"""

    def test_successful_checkpoint(self):
        session = MagicMock()
        client = MagicMock()
        client.execute_bash.return_value = {
            "exit_code": 0, "stdout": "abc123def456\n"
        }
        orch = _make_orch(mock_session=session, client=client)
        run = _make_run()

        orch._checkpoint(run, 3, "/ws")
        assert client.execute_bash.called
        # Checkpoint was added to session
        checkpoint_calls = [
            c for c in session.add.call_args_list
            if len(c[0]) > 0 and isinstance(c[0][0], Checkpoint)
        ]
        assert len(checkpoint_calls) == 1

    def test_checkpoint_commit_failure(self):
        session = MagicMock()
        client = MagicMock()
        client.execute_bash.return_value = {"exit_code": 128, "stdout": "fatal"}
        orch = _make_orch(mock_session=session, client=client)
        run = _make_run()

        # Should not raise; no Checkpoint added
        orch._checkpoint(run, 3, "/ws")
        # Verify that session.add was called at most once (by emit_event for warning)
        # Since _default_emit calls session.add, we check the git commit failed path
        # The key assertion: no Checkpoint was added
        checkpoint_calls = [
            c for c in session.add.call_args_list
            if len(c[0]) > 0 and isinstance(c[0][0], Checkpoint)
        ]
        assert len(checkpoint_calls) == 0


# ---------------------------------------------------------------------------
# 22. _finish
# ---------------------------------------------------------------------------

class TestFinish:
    """_finish：报告生成、事件发射、workspace 清理。"""

    def test_finish_flow(self):
        session = MagicMock()
        client = MagicMock()
        client.git_diff.return_value = {"modified": "diff --git a/x.py b/x.py\n+ok\n"}
        ws_mgr = MagicMock()
        orch = _make_orch(mock_session=session, client=client, workspace_manager=ws_mgr)
        run = _make_run(strategy=Strategy.DYNAMIC.value)
        task = _make_task()

        orch._finish(run, task, RunStatus.COMPLETED, "/ws")
        assert run.finished_at is not None
        assert session.add.called  # FinalReport
        ws_mgr.destroy.assert_called_once()


# ---------------------------------------------------------------------------
# 23. _fail
# ---------------------------------------------------------------------------

class TestFail:
    """_fail：异常处理、回滚、转换。"""

    def test_fail_sets_error_and_status(self):
        session = MagicMock()
        ws_mgr = MagicMock()
        orch = _make_orch(mock_session=session, workspace_manager=ws_mgr)
        run = _make_run(status=RunStatus.EXECUTING.value)

        orch._fail(run, ValueError("something broke"))
        assert "ValueError" in run.error
        assert run.status == RunStatus.FAILED.value
        assert run.finished_at is not None
        ws_mgr.destroy.assert_called_once()

    def test_fail_on_terminal_does_not_retransition(self):
        session = MagicMock()
        ws_mgr = MagicMock()
        orch = _make_orch(mock_session=session, workspace_manager=ws_mgr)
        run = _make_run(status=RunStatus.COMPLETED.value)
        old_status = run.status

        orch._fail(run, ValueError("late error"))
        assert run.status == old_status


# ---------------------------------------------------------------------------
# 24. _loop edge cases
# ---------------------------------------------------------------------------

class TestLoopEdgeCases:
    """_loop：max iterations、budget rejection、client error。"""

    def test_max_iterations_exceeded(self):
        session = MagicMock()
        client = MagicMock()
        ws_mgr = MagicMock()
        ws_mgr.provision.return_value = MagicMock(
            container_id="ctr", base_url="http://x:8000", session_key="k",
            volume_name="v", working_dir="/ws", runtime_env={
                "OPENAI_BASE_URL": "http://runtime/v1",
                "OPENAI_API_KEY": "blrt1.test-capability",
                "OPENAI_MODEL": "test-model",
                "BUDGETLOOP_AI_MANAGED": "1",
            },
        )
        client.create_conversation.return_value = None
        client.send_message.return_value = None
        client.wait_until_idle.return_value = {"execution_status": "idle"}
        client.search_events.return_value = []
        client.git_diff.return_value = {}
        client.execute_bash.return_value = {"exit_code": 0, "stdout": ""}

        session.get.side_effect = lambda model, pk: {
            TaskRun: _make_run(iteration=50, model_config={"max_loop_iterations": 2}),
            Task: _make_task(),
        }.get(model)

        budget_mgr = MagicMock()
        budget_mgr.snapshot.return_value = BudgetSnapshot(
            max_total_tokens=100_000, max_wall_time_seconds=1200,
            max_active_runtime_seconds=600, max_llm_calls=20, max_cost=5.0,
            max_parallel_llm_calls=2, used_tokens=0, used_cost=0, used_calls=0,
            reserved_tokens=0, reserved_cost=0, reserved_calls=0,
        )

        orch = Orchestrator(
            session, uuid.uuid4(), client=client, workspace_manager=ws_mgr,
            budget_manager=budget_mgr,
        )
        orch.client = client
        orch.workspace_manager = ws_mgr
        orch.transition = MagicMock(side_effect=lambda r, s: s)

        run = orch.run()
        # iteration=50 -> next would be 51 > max_iterations=2 -> PARTIAL_COMPLETED
        orch.transition.assert_called_with(ANY, RunStatus.PARTIAL_COMPLETED)

    def test_send_message_client_error(self):
        session = MagicMock()
        client = MagicMock()
        ws_mgr = MagicMock()
        ws_mgr.provision.return_value = MagicMock(
            container_id="ctr", base_url="http://x:8000", session_key="k",
            volume_name="v", working_dir="/ws", runtime_env={
                "OPENAI_BASE_URL": "http://runtime/v1",
                "OPENAI_API_KEY": "blrt1.test-capability",
                "OPENAI_MODEL": "test-model",
                "BUDGETLOOP_AI_MANAGED": "1",
            },
        )
        client.create_conversation.return_value = None
        client.send_message.side_effect = ConnectionError("agent down")

        session.get.side_effect = lambda model, pk: {
            TaskRun: _make_run(),
            Task: _make_task(),
        }.get(model)

        budget_mgr = MagicMock()
        budget_mgr.snapshot.return_value = BudgetSnapshot(
            max_total_tokens=100_000, max_wall_time_seconds=1200,
            max_active_runtime_seconds=600, max_llm_calls=20, max_cost=5.0,
            max_parallel_llm_calls=2, used_tokens=0, used_cost=0, used_calls=0,
            reserved_tokens=0, reserved_cost=0, reserved_calls=0,
        )

        orch = Orchestrator(
            session, uuid.uuid4(), client=client, workspace_manager=ws_mgr,
            budget_manager=budget_mgr,
        )
        orch.client = client
        orch.workspace_manager = ws_mgr

        run = orch.run()
        assert run.error is not None
        assert "ConnectionError" in run.error

    def test_agent_server_error_status_releases_reservation_and_stops(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        client.wait_until_idle.return_value = {"execution_status": "error", "stats": {}}
        budget = MagicMock()
        run = _make_run(status=RunStatus.PLANNING.value)
        task = _make_task()
        orch = _make_orch(mock_session=session, client=client, budget_manager=budget)

        with (
            patch("app.worker.orchestrator.queued_messages_for_run", return_value=[]),
            pytest.raises(AgentServerError, match="status 'error'"),
        ):
            orch._loop(run, task, Strategy.DYNAMIC, {}, "/workspace")

        client.send_message.assert_called_once_with(ANY, run=False)
        client.run_conversation.assert_called_once_with()
        budget.reserve.assert_called_once_with(DEFAULT_EST_TOKENS, DEFAULT_EST_COST)
        budget.release.assert_called_once_with(DEFAULT_EST_TOKENS, DEFAULT_EST_COST)
        client.search_events.assert_not_called()

    def test_observation_error_rolls_back_and_releases_reservation(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        client.wait_until_idle.return_value = {"execution_status": "idle", "stats": {}}
        client.search_events.return_value = []
        budget = MagicMock()
        run = _make_run(status=RunStatus.PLANNING.value)
        task = _make_task()
        orch = _make_orch(mock_session=session, client=client, budget_manager=budget)
        orch._record_llm_calls = MagicMock(side_effect=TypeError("bad metric"))

        with (
            patch("app.worker.orchestrator.queued_messages_for_run", return_value=[]),
            pytest.raises(TypeError, match="bad metric"),
        ):
            orch._loop(run, task, Strategy.DYNAMIC, {}, "/workspace")

        session.rollback.assert_called_once_with()
        budget.release.assert_called_once_with(DEFAULT_EST_TOKENS, DEFAULT_EST_COST)
        budget.settle.assert_not_called()

    def test_managed_runtime_releases_outer_reservation_without_duplicate_settlement(self):
        budget = MagicMock()
        orch = _make_orch()
        orch._managed_runtime_accounting = True

        orch._finalize_iteration_budget(
            budget,
            Strategy.DYNAMIC,
            DEFAULT_EST_TOKENS,
            DEFAULT_EST_COST,
            86_820,
            0.0,
        )

        budget.release.assert_called_once_with(DEFAULT_EST_TOKENS, DEFAULT_EST_COST)
        budget.settle.assert_not_called()

    def test_non_managed_runtime_retains_actual_usage_settlement(self):
        budget = MagicMock()
        orch = _make_orch()

        orch._finalize_iteration_budget(
            budget,
            Strategy.DYNAMIC,
            DEFAULT_EST_TOKENS,
            DEFAULT_EST_COST,
            12_345,
            0.25,
        )

        budget.settle.assert_called_once_with(
            DEFAULT_EST_TOKENS,
            DEFAULT_EST_COST,
            12_345,
            0.25,
        )
        budget.release.assert_not_called()


# ---------------------------------------------------------------------------
# 25. _ensure_workspace
# ---------------------------------------------------------------------------

class TestEnsureWorkspace:
    """_ensure_workspace：新 provision vs 已有 attach。"""

    def test_new_workspace_provision(self):
        session = MagicMock()
        ws_mgr = MagicMock()
        handle = MagicMock(container_id="new-ctr")
        ws_mgr.provision.return_value = handle

        orch = _make_orch(mock_session=session, workspace_manager=ws_mgr)
        run = _make_run(workspace_id=None)
        task = _make_task()

        result = orch._ensure_workspace(run, task, {})
        assert result is handle
        ws_mgr.provision.assert_called_once()
        assert run.workspace_id == "new-ctr"

    def test_existing_workspace_attach(self):
        session = MagicMock()
        ws_mgr = MagicMock()
        handle = MagicMock(container_id="existing-ctr")
        ws_mgr.attach.return_value = handle

        orch = _make_orch(mock_session=session, workspace_manager=ws_mgr)
        run = _make_run(workspace_id="existing-ctr")
        task = _make_task()

        result = orch._ensure_workspace(run, task, {})
        assert result is handle
        ws_mgr.attach.assert_called_once()
        ws_mgr.provision.assert_not_called()

    def test_workspace_manager_auto_created(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session, workspace_manager=None)
        run = _make_run(workspace_id=None)
        task = _make_task()

        with patch(
            "app.execution_engines.adapters.OpenHandsEngineAdapter.create_workspace_manager"
        ) as create_workspace_manager:
            mock_ws = create_workspace_manager.return_value
            mock_ws.provision.return_value = MagicMock(container_id="auto-ctr")
            orch._ensure_workspace(run, task, {})
            create_workspace_manager.assert_called_once()

    def test_full_access_team_without_worktree_fails_closed(self):
        session = MagicMock()
        ws_mgr = MagicMock()
        orch = _make_orch(mock_session=session, workspace_manager=ws_mgr)
        owner = MagicMock(worktree_enabled=False)
        orch._work_session = MagicMock(return_value=owner)
        run = _make_run(workspace_id=None)
        task = _make_task()

        with pytest.raises(WorkspaceError, match="server-generated worktree"):
            orch._ensure_workspace(
                run,
                task,
                {"folder_access": "full_access", "project_dir": "/tmp/project"},
            )
        ws_mgr.provision.assert_not_called()


# ---------------------------------------------------------------------------
# 26. _ensure_conversation
# ---------------------------------------------------------------------------

class TestEnsureConversation:
    """_ensure_conversation：新创建 vs 崩溃恢复。"""

    @staticmethod
    def _server_handle(**runtime_env):
        return MagicMock(
            working_dir="/ws",
            runtime_env={
                "OPENAI_BASE_URL": "http://host.docker.internal:8000/api/runtime/ai/v1",
                "OPENAI_API_KEY": "blrt1.scoped-capability.signature",
                "OPENAI_MODEL": "managed-model",
                "BUDGETLOOP_AI_MANAGED": "1",
                **runtime_env,
            },
        )

    def test_new_conversation_created(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        orch = _make_orch(mock_session=session, client=client)
        run = _make_run(conversation_id=None)
        task = _make_task()

        orch._ensure_conversation(run, task, Strategy.DYNAMIC, {}, self._server_handle())
        client.create_conversation.assert_called_once()
        call_kwargs = client.create_conversation.call_args.kwargs
        assert call_kwargs["llm_base_url"] == "http://host.docker.internal:8000/api/runtime/ai/v1"
        assert call_kwargs["llm_api_key"] == "blrt1.scoped-capability.signature"
        assert call_kwargs["model"] == "openai/managed-model"
        assert run.conversation_id is not None

    def test_crash_recovery_reuses_conversation(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        existing_cid = uuid.uuid4()
        orch = _make_orch(mock_session=session, client=client)
        run = _make_run(conversation_id=existing_cid)
        task = _make_task()

        orch._ensure_conversation(run, task, Strategy.DYNAMIC, {}, self._server_handle())
        client.create_conversation.assert_not_called()
        assert client.conversation_id == existing_cid
        assert orch._managed_runtime_accounting is True

    def test_strategy_none_no_snapshot(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        orch = _make_orch(mock_session=session, client=client)
        run = _make_run(conversation_id=None)
        task = _make_task()

        orch._ensure_conversation(run, task, Strategy.NONE, {}, self._server_handle())
        client.create_conversation.assert_called_once()
        # 验证 initial_message 不含预算行
        call_kwargs = client.create_conversation.call_args[1]
        assert "initial_message" in call_kwargs
        assert "不跟踪预算" in call_kwargs["initial_message"]

    def test_server_fails_closed_without_managed_runtime(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "server"
        orch = _make_orch(mock_session=session, client=client)

        with pytest.raises(WorkspaceError, match="managed AI runtime unavailable"):
            orch._ensure_conversation(
                _make_run(conversation_id=None),
                _make_task(),
                Strategy.DYNAMIC,
                {},
                self._server_handle(OPENAI_API_KEY="", BUDGETLOOP_AI_MANAGED="0"),
            )

        client.create_conversation.assert_not_called()

    def test_cli_conversation_keeps_empty_server_llm_arguments(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "cli"
        orch = _make_orch(mock_session=session, client=client)
        handle = MagicMock(working_dir="/ws", runtime_env={})

        orch._ensure_conversation(
            _make_run(conversation_id=None), _make_task(), Strategy.DYNAMIC, {}, handle
        )

        call_kwargs = client.create_conversation.call_args.kwargs
        assert call_kwargs["llm_base_url"] == ""
        assert call_kwargs["llm_api_key"] == ""
        assert orch._managed_runtime_accounting is False

    def test_managed_cli_uses_proxy_budget_accounting(self):
        session = MagicMock()
        client = MagicMock()
        client.transport = "cli"
        orch = _make_orch(mock_session=session, client=client)
        handle = MagicMock(working_dir="/ws", runtime_env={"BUDGETLOOP_AI_MANAGED": "1"})

        orch._ensure_conversation(
            _make_run(conversation_id=None), _make_task(), Strategy.DYNAMIC, {}, handle
        )

        assert orch._managed_runtime_accounting is True


# ---------------------------------------------------------------------------
# 27. _approval_gate
# ---------------------------------------------------------------------------

class TestApprovalGate:
    """_approval_gate：approved、rejected、timeout。"""

    def test_approved(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        # WAITING_APPROVAL is allowed from EXECUTING
        run = _make_run(status=RunStatus.EXECUTING.value)

        hit = risk_mod.RiskHit(ApprovalActionType.DANGEROUS_COMMAND, "rm -rf /tmp", "high")
        # 注入 approved status
        def refresh_side_effect(approval):
            approval.status = "approved"

        session.refresh.side_effect = refresh_side_effect

        result = orch._approval_gate(run, 1, [hit])
        assert result is True

    def test_rejected_sets_feedback(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run(status=RunStatus.EXECUTING.value)

        hit = risk_mod.RiskHit(ApprovalActionType.DELETE_FILE, "rm important.log", "medium")

        def refresh_side_effect(approval):
            approval.status = "rejected"
            approval.decision_note = "too dangerous"

        session.refresh.side_effect = refresh_side_effect

        result = orch._approval_gate(run, 1, [hit])
        assert result is False
        assert orch._feedback is not None
        assert "rejected" in orch._feedback.lower() or "拒绝" in orch._feedback

    def test_timeout(self):
        session = MagicMock()
        orch = _make_orch(
            mock_session=session,
            approval_timeout_seconds=0.01,
            approval_poll_interval=0.02,
        )
        run = _make_run(status=RunStatus.EXECUTING.value)

        hit = risk_mod.RiskHit(ApprovalActionType.DANGEROUS_COMMAND, "rm -rf", "high")
        # Ensure approval stays "pending" so timeout path is hit
        def refresh_side_effect(approval):
            approval.status = "pending"

        session.refresh.side_effect = refresh_side_effect

        result = orch._approval_gate(run, 1, [hit])
        assert result is False
        assert "超时" in orch._feedback


# ---------------------------------------------------------------------------
# 28. transition method on orchestrator
# ---------------------------------------------------------------------------

class TestOrchestratorTransition:
    """Orchestrator.transition：合法性校验 + 事件发射。"""

    def test_valid_transition_emits_event(self):
        session = MagicMock()
        mock_emit = MagicMock()
        orch = _make_orch(mock_session=session, emit_event=mock_emit)
        run = _make_run(status=RunStatus.PLANNING.value)

        result = orch.transition(run, RunStatus.EXECUTING)
        assert result == RunStatus.EXECUTING
        assert run.status == RunStatus.EXECUTING.value
        mock_emit.assert_called_once()

    def test_invalid_transition_raises(self):
        session = MagicMock()
        orch = _make_orch(mock_session=session)
        run = _make_run(status=RunStatus.EXECUTING.value)

        with pytest.raises(InvalidTransition):
            orch.transition(run, RunStatus.PLANNING)
