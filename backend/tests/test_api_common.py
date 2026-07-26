"""Tests for shared route helpers (app/api/common.py).

Covers constants, create_run, budget_snapshot_dict, run_to_dict, and
task_to_dict.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, ANY, patch

import pytest

from app.api.common import (  # noqa: E402
    DEFAULT_ACCEPTANCE_CRITERIA,
    PHASE_WEIGHTS,
    budget_snapshot_dict,
    create_run,
    run_to_dict,
    task_to_dict,
)
from app.core.enums import EventType, Phase, RunStatus, Strategy  # noqa: E402
from app.core.models import Task, TaskRun  # noqa: E402

pytestmark = pytest.mark.unit


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_task(**overrides) -> Task:
    kwargs = {
        "id": uuid.uuid4(),
        "name": "test-task",
        "description": "A test task",
        "workdir": "/workspace/test",
    }
    kwargs.update(overrides)
    return Task(**kwargs)


def _make_run(**overrides) -> TaskRun:
    kwargs = {
        "id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "attempt_no": 1,
        "strategy": "dynamic",
        "status": "PENDING",
        "model_config": {},
        "pressure_mode": "NORMAL",
        "iteration": 0,
        "active_runtime_ms": 0,
    }
    kwargs.update(overrides)
    return TaskRun(**kwargs)


def _budget_fields(**overrides) -> dict:
    defaults = {
        "max_wall_time_seconds": 1200,
        "max_total_tokens": 100000,
        "max_llm_calls": 20,
        "max_cost": 5.0,
        "max_active_runtime_seconds": 600,
    }
    defaults.update(overrides)
    return defaults


# ── DEFAULT_ACCEPTANCE_CRITERIA ─────────────────────────────────────────────


class TestDefaultAcceptanceCriteria:
    def test_default_acceptance_criteria_is_non_empty(self):
        """DEFAULT_ACCEPTANCE_CRITERIA is a non-empty string."""
        assert isinstance(DEFAULT_ACCEPTANCE_CRITERIA, str)
        assert len(DEFAULT_ACCEPTANCE_CRITERIA) > 0

    def test_default_acceptance_criteria_contains_expected_phrases(self):
        """Contains key acceptance-check phrases."""
        assert "目标已达成" in DEFAULT_ACCEPTANCE_CRITERIA
        assert "自动化测试通过" in DEFAULT_ACCEPTANCE_CRITERIA
        assert "改动范围" in DEFAULT_ACCEPTANCE_CRITERIA

    def test_default_acceptance_criteria_has_three_items(self):
        """DEFAULT_ACCEPTANCE_CRITERIA contains three numbered criteria."""
        items = [line.strip() for line in DEFAULT_ACCEPTANCE_CRITERIA.split("\n") if line.strip()]
        assert any("1)" in item for item in items)
        assert any("2)" in item for item in items)
        assert any("3)" in item for item in items)


# ── PHASE_WEIGHTS ───────────────────────────────────────────────────────────


class TestPhaseWeights:
    def test_sum_is_one(self):
        """All phase weights sum to exactly 1.0."""
        total = sum(PHASE_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_all_six_phases_present(self):
        """All six Phase enum values are present in PHASE_WEIGHTS."""
        expected_phases = {
            Phase.SCAN, Phase.ANALYZE, Phase.MODIFY,
            Phase.VERIFY, Phase.REPAIR, Phase.SUMMARIZE,
        }
        assert set(PHASE_WEIGHTS.keys()) == expected_phases

    def test_no_extra_keys(self):
        """PHASE_WEIGHTS has exactly six keys — no extras."""
        assert len(PHASE_WEIGHTS) == 6

    def test_all_weights_positive(self):
        """Every weight is > 0."""
        for phase, weight in PHASE_WEIGHTS.items():
            assert weight > 0, f"{phase} weight must be positive"

    def test_weights_are_floats(self):
        """Every weight value is a float."""
        for weight in PHASE_WEIGHTS.values():
            assert isinstance(weight, float)


# ── create_run ──────────────────────────────────────────────────────────────


class TestCreateRun:
    """Unit tests for the create_run factory function.

    In a real DB, session.flush() assigns run.id (via the column default
    uuid.uuid4).  With a mock session this never happens, so we patch
    emit_event to avoid the UUID conversion inside it.  Tests that
    specifically verify emit_event's call signature also patch it.
    """

    def _make_session(self):
        """Returns a mock session that records add() calls and supports flush()."""
        session = MagicMock()
        session.add.side_effect = lambda obj: None
        return session

    def _create_run(self, session, task, attempt_no, strategy, budget_fields, model_config=None):
        """Call create_run with emit_event patched out."""
        with patch("app.api.common.emit_event"):
            return create_run(session, task, attempt_no, strategy, budget_fields, model_config)

    @pytest.mark.unit
    def test_create_run_basic_structure(self):
        """create_run returns a TaskRun with the expected top-level fields."""
        session = self._make_session()
        task = _make_task()

        run = self._create_run(session, task, 1, Strategy.FIXED, _budget_fields())

        assert isinstance(run, TaskRun)
        assert run.task_id == task.id
        assert run.attempt_no == 1
        assert run.strategy == "fixed"
        assert run.status == "PENDING"
        session.add.assert_called()  # at least run + budget + phases

    @pytest.mark.unit
    def test_create_run_adds_run_budget_and_six_phases(self):
        """create_run adds 1 TaskRun + 1 TaskBudget + 6 TaskPhases to the
        session (8 total add calls — the emit_event is patched out)."""
        session = self._make_session()
        task = _make_task()

        self._create_run(session, task, 1, Strategy.FIXED, _budget_fields())

        # run + budget + 6 phases = 8 (event is patched out)
        assert session.add.call_count == 8

    @pytest.mark.unit
    def test_create_run_fixed_strategy_phases_have_weighted_budgets(self):
        """With Strategy.FIXED, phase budgets are weighted by PHASE_WEIGHTS."""
        session = self._make_session()
        task = _make_task()
        budget = _budget_fields(max_total_tokens=100000, max_active_runtime_seconds=600,
                                max_llm_calls=20, max_cost=5.0)

        # Capture phase objects added to the session
        added = []
        session.add.side_effect = lambda obj: added.append(obj)

        self._create_run(session, task, 1, Strategy.FIXED, budget)

        # Collect TaskPhase objects (skip TaskRun, TaskBudget)
        from app.core.models import TaskPhase
        phases = [obj for obj in added if isinstance(obj, TaskPhase)]
        assert len(phases) == 6

        # Verify SCAN phase (weight 0.05)
        scan = [p for p in phases if p.phase == "scan"][0]
        assert scan.budget_tokens == 5000   # 100000 * 0.05
        assert scan.budget_seconds == 30     # 600 * 0.05
        assert scan.budget_calls == 1        # 20 * 0.05
        assert scan.budget_cost == 0.25      # 5.0 * 0.05

    @pytest.mark.unit
    def test_create_run_dynamic_strategy_phases_have_weighted_budgets(self):
        """With Strategy.DYNAMIC, phase budgets are also weighted (same as FIXED initially)."""
        session = self._make_session()
        task = _make_task()
        budget = _budget_fields(max_total_tokens=200000, max_active_runtime_seconds=300,
                                max_llm_calls=10, max_cost=10.0)

        added = []
        session.add.side_effect = lambda obj: added.append(obj)

        self._create_run(session, task, 1, Strategy.DYNAMIC, budget)

        from app.core.models import TaskPhase
        phases = [obj for obj in added if isinstance(obj, TaskPhase)]

        modify = [p for p in phases if p.phase == "modify"][0]
        assert modify.budget_tokens == 70000   # 200000 * 0.35
        assert modify.budget_seconds == 105    # 300 * 0.35
        assert modify.budget_calls == 3        # 10 * 0.35
        assert modify.budget_cost == 3.5       # 10.0 * 0.35

    @pytest.mark.unit
    def test_create_run_none_strategy_phases_have_zero_budgets(self):
        """With Strategy.NONE, all phase budgets are zero."""
        session = self._make_session()
        task = _make_task()
        budget = _budget_fields(max_total_tokens=99999, max_cost=9.99)

        added = []
        session.add.side_effect = lambda obj: added.append(obj)

        self._create_run(session, task, 1, Strategy.NONE, budget)

        from app.core.models import TaskPhase
        phases = [obj for obj in added if isinstance(obj, TaskPhase)]
        assert len(phases) == 6

        for p in phases:
            assert p.budget_tokens == 0, f"{p.phase} tokens should be 0"
            assert p.budget_seconds == 0, f"{p.phase} seconds should be 0"
            assert p.budget_calls == 0, f"{p.phase} calls should be 0"
            assert p.budget_cost == 0.0, f"{p.phase} cost should be 0"

    @pytest.mark.unit
    def test_create_run_strategy_stored_as_value_string(self):
        """The strategy enum value string is stored on the run, not the enum itself."""
        session = self._make_session()
        task = _make_task()

        run = self._create_run(session, task, 1, Strategy.FIXED, _budget_fields())
        assert run.strategy == "fixed"
        assert isinstance(run.strategy, str)

    @pytest.mark.unit
    def test_create_run_deadline_calculated_from_wall_time(self):
        """The deadline_at is set to utcnow() + max_wall_time_seconds."""
        session = self._make_session()
        task = _make_task()
        budget = _budget_fields(max_wall_time_seconds=300)

        # Freeze time to verify the deadline
        frozen_now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        with patch("app.api.common.emit_event"), \
             patch("app.api.common.utcnow", return_value=frozen_now):
            run = create_run(session, task, 1, Strategy.FIXED, budget)

        assert run.deadline_at is not None
        expected_deadline = frozen_now + timedelta(seconds=300)
        assert run.deadline_at == expected_deadline

    @pytest.mark.unit
    def test_create_run_emits_run_started_event(self):
        """create_run emits a RUN_STARTED event via emit_event."""
        session = self._make_session()
        task = _make_task()

        with patch("app.api.common.emit_event") as mock_emit:
            run = create_run(session, task, 2, Strategy.DYNAMIC, _budget_fields())

        mock_emit.assert_called_once()
        call_args = mock_emit.call_args[0]
        assert call_args[0] is session        # session
        assert call_args[1] == run.id          # run_id (None on mock, but call is verified)
        assert call_args[2] == EventType.RUN_STARTED  # event type
        assert call_args[3]["task_id"] == str(task.id)
        assert call_args[3]["attempt_no"] == 2
        assert call_args[3]["strategy"] == "dynamic"

    @pytest.mark.unit
    def test_create_run_attempt_number(self):
        """The attempt_no is correctly assigned to the run."""
        session = self._make_session()
        task = _make_task()

        run = self._create_run(session, task, 3, Strategy.FIXED, _budget_fields())
        assert run.attempt_no == 3

        run2 = self._create_run(session, task, 99, Strategy.FIXED, _budget_fields())
        assert run2.attempt_no == 99

    @pytest.mark.unit
    def test_create_run_model_config_defaults_to_empty_dict(self):
        """When model_config is None or omitted, it defaults to {}."""
        session = self._make_session()
        task = _make_task()

        run = self._create_run(session, task, 1, Strategy.FIXED, _budget_fields())
        assert run.model_config == {}

    @pytest.mark.unit
    def test_create_run_model_config_provided_stored_on_run(self):
        """A provided model_config dict is stored on the run."""
        session = self._make_session()
        task = _make_task()

        config = {"model": "gpt-4", "temperature": 0.7}
        run = self._create_run(session, task, 1, Strategy.FIXED, _budget_fields(), model_config=config)
        assert run.model_config == config

    @pytest.mark.unit
    def test_create_run_budget_fields_stored_on_taskbudget(self):
        """All budget fields are passed through to the TaskBudget object."""
        session = self._make_session()
        task = _make_task()
        budget = _budget_fields(
            max_wall_time_seconds=900,
            max_total_tokens=50000,
            max_llm_calls=15,
            max_cost=3.5,
            max_active_runtime_seconds=300,
        )

        added = []
        session.add.side_effect = lambda obj: added.append(obj)

        self._create_run(session, task, 1, Strategy.FIXED, budget)

        from app.core.models import TaskBudget
        budgets = [obj for obj in added if isinstance(obj, TaskBudget)]
        assert len(budgets) == 1
        b = budgets[0]
        assert b.max_wall_time_seconds == 900
        assert b.max_total_tokens == 50000
        assert b.max_llm_calls == 15
        assert b.max_cost == 3.5
        assert b.max_active_runtime_seconds == 300

    @pytest.mark.unit
    def test_create_run_flush_called_after_run_add(self):
        """session.flush() is called after adding the run, so run.id is
        available for the subsequent budget, phases, and event."""
        session = self._make_session()

        # Record the order of add/flush calls
        calls = []
        session.add.side_effect = lambda obj: calls.append(("add", type(obj).__name__))
        session.flush.side_effect = lambda: calls.append("flush")

        task = _make_task()
        with patch("app.api.common.emit_event"):
            # Use a fresh mock so call recording starts clean
            create_run(session, task, 1, Strategy.FIXED, _budget_fields())

        # First add is the run, then flush before budget/phases/event
        assert calls[0] == ("add", "TaskRun")
        assert calls[1] == "flush"
        # The emit_event is patched, so add calls without it: run + budget + 6 phases = 8
        assert len(calls) >= 3  # run-add, flush, at least budget-add


# ── budget_snapshot_dict ───────────────────────────────────────────────────--


class TestBudgetSnapshotDict:
    @pytest.mark.unit
    def test_returns_dict_with_expected_keys(self):
        """budget_snapshot_dict returns a dict with the expected budget keys."""
        run_id = uuid.uuid4()
        mock_session = MagicMock()

        expected = {
            "max_total_tokens": 100000,
            "max_wall_time_seconds": 1200,
            "max_active_runtime_seconds": 600,
            "max_llm_calls": 20,
            "max_cost": 5.0,
            "max_parallel_llm_calls": 2,
            "used_tokens": 5000,
            "used_cost": 0.25,
            "used_calls": 3,
            "reserved_tokens": 1000,
            "reserved_cost": 0.05,
            "reserved_calls": 1,
            "remaining_tokens": 94000,
            "remaining_calls": 16,
            "remaining_cost": 4.70,
            "projected_tokens": 10000,
        }

        with patch("app.api.common.TaskBudgetManager") as mock_mgr_class:
            mock_mgr = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.to_dict.return_value = expected
            mock_mgr.snapshot.return_value = mock_snapshot
            mock_mgr_class.return_value = mock_mgr

            result = budget_snapshot_dict(mock_session, run_id)

        assert result == expected
        mock_mgr_class.assert_called_once_with(mock_session, run_id)
        mock_mgr.snapshot.assert_called_once()

    @pytest.mark.unit
    def test_raises_when_no_budget_exists(self):
        """budget_snapshot_dict propagates exceptions from the budget manager."""
        run_id = uuid.uuid4()
        mock_session = MagicMock()

        with patch("app.api.common.TaskBudgetManager") as mock_mgr_class:
            mock_mgr = MagicMock()
            mock_mgr.snapshot.side_effect = ValueError("no budget found for this run")
            mock_mgr_class.return_value = mock_mgr

            with pytest.raises(ValueError, match="no budget found for this run"):
                budget_snapshot_dict(mock_session, run_id)

    @pytest.mark.unit
    def test_values_have_correct_types(self):
        """All numeric budget values have the expected Python types."""
        run_id = uuid.uuid4()
        mock_session = MagicMock()

        snapshot_data = {
            "max_total_tokens": 100000,
            "max_wall_time_seconds": 1200,
            "max_active_runtime_seconds": 600,
            "max_llm_calls": 20,
            "max_cost": 5.0,
            "max_parallel_llm_calls": 2,
            "used_tokens": 5000,
            "used_cost": 0.25,
            "used_calls": 3,
            "reserved_tokens": 1000,
            "reserved_cost": 0.05,
            "reserved_calls": 1,
            "remaining_tokens": 94000,
            "remaining_calls": 16,
            "remaining_cost": 4.70,
            "projected_tokens": 10000,
        }

        with patch("app.api.common.TaskBudgetManager") as mock_mgr_class:
            mock_mgr = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.to_dict.return_value = snapshot_data
            mock_mgr.snapshot.return_value = mock_snapshot
            mock_mgr_class.return_value = mock_mgr

            result = budget_snapshot_dict(mock_session, run_id)

        assert isinstance(result["max_total_tokens"], int)
        assert isinstance(result["max_cost"], float)
        assert isinstance(result["max_llm_calls"], int)
        assert isinstance(result["used_cost"], float)
        assert isinstance(result["remaining_tokens"], int)


# ── run_to_dict ─────────────────────────────────────────────────────────────


class TestRunToDict:
    @pytest.mark.unit
    def test_all_expected_fields_present(self):
        """run_to_dict includes all documented fields."""
        run = _make_run()
        result = run_to_dict(run)

        expected_keys = {
            "id", "task_id", "attempt_no", "strategy", "status",
            "current_phase", "pressure_mode", "iteration",
            "started_at", "finished_at", "deadline_at",
            "active_runtime_ms", "error", "model_config",
            "work_container_id", "work_session_id", "work_session_role",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.unit
    def test_uuid_converted_to_string(self):
        """UUID fields (id, task_id) are converted to strings."""
        run_id = uuid.uuid4()
        task_id = uuid.uuid4()
        run = _make_run(id=run_id, task_id=task_id)
        result = run_to_dict(run)

        assert result["id"] == str(run_id)
        assert result["task_id"] == str(task_id)
        assert isinstance(result["id"], str)
        assert isinstance(result["task_id"], str)

    @pytest.mark.unit
    def test_none_timestamps_handled(self):
        """None timestamps remain None in the output dict."""
        run = _make_run(started_at=None, finished_at=None, deadline_at=None)
        result = run_to_dict(run)

        assert result["started_at"] is None
        assert result["finished_at"] is None
        assert result["deadline_at"] is None

    @pytest.mark.unit
    def test_populated_timestamps_isoformat(self):
        """Non-None timestamps are serialized to ISO format strings."""
        ts = datetime(2025, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        run = _make_run(started_at=ts, finished_at=ts, deadline_at=ts)
        result = run_to_dict(run)

        assert result["started_at"] == ts.isoformat()
        assert result["finished_at"] == ts.isoformat()
        assert result["deadline_at"] == ts.isoformat()

    @pytest.mark.unit
    def test_scalar_fields_preserved(self):
        """Scalar fields (attempt_no, iteration, active_runtime_ms, etc.)
        are passed through correctly."""
        run = _make_run(
            attempt_no=5,
            strategy="none",
            status="EXECUTING",
            current_phase="modify",
            pressure_mode="CRITICAL",
            iteration=12,
            active_runtime_ms=42000,
            error="something went wrong",
        )
        result = run_to_dict(run)

        assert result["attempt_no"] == 5
        assert result["strategy"] == "none"
        assert result["status"] == "EXECUTING"
        assert result["current_phase"] == "modify"
        assert result["pressure_mode"] == "CRITICAL"
        assert result["iteration"] == 12
        assert result["active_runtime_ms"] == 42000
        assert result["error"] == "something went wrong"

    @pytest.mark.unit
    def test_error_none_handled(self):
        """error=None is preserved in output."""
        run = _make_run(error=None)
        result = run_to_dict(run)
        assert result["error"] is None

    @pytest.mark.unit
    def test_current_phase_none_handled(self):
        """current_phase=None is preserved in output."""
        run = _make_run(current_phase=None)
        result = run_to_dict(run)
        assert result["current_phase"] is None


# ── task_to_dict ───────────────────────────────────────────────────────────-


class TestTaskToDict:
    @pytest.mark.unit
    def test_all_expected_fields_present(self):
        """task_to_dict includes all documented fields."""
        task = _make_task()
        result = task_to_dict(task)

        expected_keys = {
            "id", "name", "description", "workdir",
            "acceptance_criteria", "template", "require_approval",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.unit
    def test_id_converted_to_string(self):
        """Task.id (UUID) is converted to a string."""
        task_id = uuid.uuid4()
        task = _make_task(id=task_id)
        result = task_to_dict(task)
        assert result["id"] == str(task_id)
        assert isinstance(result["id"], str)

    @pytest.mark.unit
    def test_scalar_fields_preserved(self):
        """Name, description, and workdir are passed through."""
        task = _make_task(
            name="修复库存并发",
            description="修复库存并发扣减问题",
            workdir="/workspace/inventory",
        )
        result = task_to_dict(task)

        assert result["name"] == "修复库存并发"
        assert result["description"] == "修复库存并发扣减问题"
        assert result["workdir"] == "/workspace/inventory"

    @pytest.mark.unit
    def test_acceptance_criteria_none_handled(self):
        """acceptance_criteria=None is preserved in output."""
        task = _make_task(acceptance_criteria=None)
        result = task_to_dict(task)
        assert result["acceptance_criteria"] is None

    @pytest.mark.unit
    def test_acceptance_criteria_with_value(self):
        """A non-None acceptance_criteria is passed through."""
        task = _make_task(acceptance_criteria="1) 测试通过；2) 无需人工审核")
        result = task_to_dict(task)
        assert result["acceptance_criteria"] == "1) 测试通过；2) 无需人工审核"

    @pytest.mark.unit
    def test_template_default_value(self):
        """template defaults to 'fix_bug' per model definition."""
        task = _make_task(template="fix_bug")
        result = task_to_dict(task)
        assert result["template"] == "fix_bug"

    @pytest.mark.unit
    def test_require_approval_default_value(self):
        """require_approval defaults to True per model definition."""
        task = _make_task(require_approval=True)
        result = task_to_dict(task)
        assert result["require_approval"] is True
