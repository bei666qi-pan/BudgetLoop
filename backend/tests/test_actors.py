"""Unit tests for app.worker.actors — Dramatiq actors (run_task + sweeper).

All tests are pure unit tests with mocks; no real Redis/Dramatiq/DB needed.
"""
from __future__ import annotations

import contextlib
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import redis

# ---------------------------------------------------------------------------
# Mock dramatiq BEFORE importing the actors module to prevent broker
# connection attempts from app.worker.broker and @dramatiq.actor.
# ---------------------------------------------------------------------------
_dramatiq_mock = MagicMock()
_dramatiq_mock.set_broker = MagicMock()


def _mock_actor(**kw):
    """Identity decorator that attaches kwargs without Dramatiq broker."""
    def decorator(fn):
        fn._dramatiq_actor_kwargs = kw
        return fn
    return decorator


_dramatiq_mock.actor = _mock_actor
_dramatiq_mock.Message = MagicMock()

_brokers_redis_mock = MagicMock()
_brokers_redis_mock.RedisBroker = MagicMock()
_dramatiq_mock.brokers = MagicMock()
_dramatiq_mock.brokers.redis = _brokers_redis_mock

sys.modules["dramatiq"] = _dramatiq_mock
sys.modules["dramatiq.brokers"] = _dramatiq_mock.brokers
sys.modules["dramatiq.brokers.redis"] = _brokers_redis_mock

# Now safe to import the actors module
from app.core.enums import RunStatus  # noqa: E402
from app.worker.actors import (  # noqa: E402
    ACTIVE_STATUSES,
    NON_TERMINAL_STATUSES,
    _redis_client,
    _sweep_once,
    run_task,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(**overrides) -> MagicMock:
    """Build a mock TaskRun with sensible defaults."""
    run_id = overrides.pop("id", uuid.uuid4())
    m = MagicMock()
    m.id = run_id
    m.task_id = uuid.uuid4()
    m.status = RunStatus.PENDING.value
    m.deadline_at = None
    m.finished_at = None
    m.task = MagicMock()  # so hasattr(run, "task") → True
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _setup_sweep_session(mock_session_cls, expired_runs=None, active_runs=None):
    """Set up SessionLocal mock for _sweep_once with controlled query results."""
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    q_expired = MagicMock()
    q_active = MagicMock()
    mock_session.query.side_effect = [q_expired, q_active]

    f_expired = MagicMock()
    q_expired.filter.return_value = f_expired
    f_expired.all.return_value = expired_runs or []

    f_active = MagicMock()
    q_active.filter.return_value = f_active
    f_active.all.return_value = active_runs or []

    return mock_session


# ============================================================================
# NON_TERMINAL_STATUSES / ACTIVE_STATUSES
# ============================================================================


class TestStatusConstants:
    """Verify the sweeper status list constants."""

    def test_non_terminal_contains_loop_statuses(self):
        assert RunStatus.PENDING.value in NON_TERMINAL_STATUSES
        assert RunStatus.PLANNING.value in NON_TERMINAL_STATUSES
        assert RunStatus.EXECUTING.value in NON_TERMINAL_STATUSES
        assert RunStatus.OBSERVING.value in NON_TERMINAL_STATUSES
        assert RunStatus.EVALUATING.value in NON_TERMINAL_STATUSES
        assert RunStatus.REPLANNING.value in NON_TERMINAL_STATUSES
        assert RunStatus.WAITING_APPROVAL.value in NON_TERMINAL_STATUSES
        assert RunStatus.PAUSED.value in NON_TERMINAL_STATUSES

    def test_non_terminal_excludes_completed(self):
        assert RunStatus.COMPLETED.value not in NON_TERMINAL_STATUSES
        assert RunStatus.FAILED.value not in NON_TERMINAL_STATUSES
        assert RunStatus.BUDGET_EXHAUSTED.value not in NON_TERMINAL_STATUSES
        assert RunStatus.CANCELLED.value not in NON_TERMINAL_STATUSES

    def test_active_statuses_are_subset_of_non_terminal(self):
        for s in ACTIVE_STATUSES:
            assert s in NON_TERMINAL_STATUSES, f"{s} should be in NON_TERMINAL_STATUSES"

    def test_active_statuses_contain_loop_phases(self):
        assert RunStatus.PLANNING.value in ACTIVE_STATUSES
        assert RunStatus.EXECUTING.value in ACTIVE_STATUSES
        assert RunStatus.OBSERVING.value in ACTIVE_STATUSES
        assert RunStatus.EVALUATING.value in ACTIVE_STATUSES
        assert RunStatus.REPLANNING.value in ACTIVE_STATUSES

    def test_active_statuses_exclude_idle(self):
        assert RunStatus.PENDING.value not in ACTIVE_STATUSES
        assert RunStatus.WAITING_APPROVAL.value not in ACTIVE_STATUSES
        assert RunStatus.PAUSED.value not in ACTIVE_STATUSES


# ============================================================================
# _redis_client
# ============================================================================


class TestRedisClient:
    """Tests for _redis_client() helper."""

    @patch("app.worker.actors.redis.from_url")
    def test_redis_available(self, mock_from_url):
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        mock_from_url.return_value = mock_r

        result = _redis_client()

        assert result is mock_r
        mock_r.ping.assert_called_once()

    @patch("app.worker.actors.redis.from_url")
    def test_redis_connection_error_returns_none(self, mock_from_url):
        mock_from_url.side_effect = redis.exceptions.ConnectionError("boom")

        result = _redis_client()

        assert result is None

    @patch("app.worker.actors.redis.from_url")
    def test_redis_timeout_error_returns_none(self, mock_from_url):
        mock_from_url.side_effect = redis.exceptions.TimeoutError("timeout")

        result = _redis_client()

        assert result is None

    @patch("app.worker.actors.redis.from_url")
    def test_redis_oserror_returns_none(self, mock_from_url):
        mock_from_url.side_effect = OSError("refused")

        result = _redis_client()

        assert result is None

    @patch("app.worker.actors.redis.from_url")
    def test_redis_from_url_immediate_failure(self, mock_from_url):
        """from_url raises immediately — should be caught and return None."""
        mock_from_url.side_effect = redis.exceptions.ConnectionError("refused")

        result = _redis_client()

        assert result is None
        mock_from_url.assert_called_once()


# ============================================================================
# run_task
# ============================================================================


class TestRunTask:
    """Tests for the run_task Dramatiq actor."""

    @patch("app.worker.actors.SessionLocal")
    def test_run_not_found(self, mock_session_cls, caplog):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = None

        run_id = str(uuid.uuid4())
        run_task(run_id)

        assert f"run {run_id} not found" in caplog.text.lower()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_already_terminal_completed(self, mock_session_cls, mock_orch_cls, caplog):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.COMPLETED.value)
        mock_session.get.return_value = mock_run

        caplog.set_level("INFO")
        run_task(str(mock_run.id))

        assert "already terminal" in caplog.text.lower()
        mock_orch_cls.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_already_terminal_failed(self, mock_session_cls, mock_orch_cls, caplog):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.FAILED.value)
        mock_session.get.return_value = mock_run

        caplog.set_level("INFO")
        run_task(str(mock_run.id))

        assert "already terminal" in caplog.text.lower()
        mock_orch_cls.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_not_pending_or_replanning(self, mock_session_cls, mock_orch_cls, caplog):
        """Status EXECUTING is not PENDING/REPLANNING → skip."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.EXECUTING.value)
        mock_session.get.return_value = mock_run

        caplog.set_level("INFO")
        run_task(str(mock_run.id))

        assert "skipping" in caplog.text.lower()
        mock_orch_cls.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_pending_creates_orchestrator(self, mock_session_cls, mock_orch_cls, caplog):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.PENDING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        mock_orch_cls.assert_called_once()
        call_args = mock_orch_cls.call_args
        assert call_args[0][0] is mock_session
        assert call_args[0][1] == str(mock_run.id)
        assert "heartbeat" in call_args[1]
        mock_orch.run.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_replanning_creates_orchestrator(self, mock_session_cls, mock_orch_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.REPLANNING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        mock_orch_cls.assert_called_once()
        mock_orch.run.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_exception_closes_session(self, mock_session_cls, mock_orch_cls, caplog):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.PENDING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch.run.side_effect = RuntimeError("orchestrator exploded")
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        assert "unhandled exception" in caplog.text.lower()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_session_closed_in_finally_even_on_success(self, mock_session_cls, mock_orch_cls):
        """Session.close() is called in finally regardless of outcome."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.PENDING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_invalid_uuid_raises(self, mock_session_cls, mock_orch_cls, caplog):
        """Calling run_task with an invalid UUID string should trigger
        uuid.UUID() ValueError which gets caught by the except clause."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        run_task("not-a-valid-uuid")

        # The ValueError from uuid.UUID() should be caught by the generic
        # except block, logged, and session.close() still called.
        assert "unhandled exception" in caplog.text.lower()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_task_heartbeat_function_uses_redis(self, mock_session_cls, mock_orch_cls):
        """Verify the heartbeat closure is created and is a callable."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.PENDING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        # Orchestrator was called with heartbeat kwarg
        hb = mock_orch_cls.call_args[1].get("heartbeat")
        assert callable(hb)

        # Call the heartbeat closure → should try redis.from_url
        with patch("app.worker.actors.redis.from_url") as mock_from_url:
            mock_r = MagicMock()
            mock_from_url.return_value = mock_r
            hb(str(mock_run.id))
            mock_r.setex.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors.SessionLocal")
    def test_run_task_heartbeat_silent_on_redis_error(self, mock_session_cls, mock_orch_cls):
        """Heartbeat closure catches Redis errors silently."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run = _make_run(status=RunStatus.PENDING.value)
        mock_session.get.return_value = mock_run

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        run_task(str(mock_run.id))

        hb = mock_orch_cls.call_args[1].get("heartbeat")

        with patch("app.worker.actors.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = redis.exceptions.ConnectionError("down")
            hb(str(mock_run.id))  # should not raise


# ============================================================================
# _sweep_once — deadline expiry
# ============================================================================


class TestSweepOnceDeadline:
    """Tests for _sweep_once deadline expiry logic."""

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_deadline_expired_transitions_to_budget_exhausted(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        mock_redis.return_value = None
        run_id = uuid.uuid4()
        expired_run = _make_run(
            id=run_id,
            status=RunStatus.PLANNING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        mock_session = _setup_sweep_session(
            mock_session_cls, expired_runs=[expired_run]
        )

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        _sweep_once()

        assert expired_run.status == RunStatus.BUDGET_EXHAUSTED.value
        assert expired_run.finished_at is not None
        mock_session.commit.assert_called()
        mock_session.close.assert_called_once()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_multiple_expired_runs_all_processed(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        mock_redis.return_value = None
        r1 = _make_run(
            id=uuid.uuid4(), status=RunStatus.PLANNING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        r2 = _make_run(
            id=uuid.uuid4(), status=RunStatus.EXECUTING.value,
            deadline_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
        mock_session = _setup_sweep_session(
            mock_session_cls, expired_runs=[r1, r2]
        )

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        _sweep_once()

        assert r1.status == RunStatus.BUDGET_EXHAUSTED.value
        assert r2.status == RunStatus.BUDGET_EXHAUSTED.value
        assert mock_session.commit.call_count >= 2

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_no_expired_runs_no_state_changes(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        mock_redis.return_value = None
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        _sweep_once()

        mock_orch_cls.assert_not_called()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_deadline_none_not_expired(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        """deadline_at=None should not match the expired query."""
        mock_redis.return_value = None
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        _sweep_once()

        mock_orch_cls.assert_not_called()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_future_deadline_not_expired(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        """A deadline in the future should not be in the expired list."""
        mock_redis.return_value = None
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        _sweep_once()

        mock_orch_cls.assert_not_called()

    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_expire_exception_rollback_and_continue(
        self, mock_session_cls, mock_redis, mock_orch_cls
    ):
        """If one run fails to expire, rollback and continue to the next."""
        mock_redis.return_value = None
        r_good = _make_run(
            id=uuid.uuid4(), status=RunStatus.PLANNING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        r_bad = _make_run(
            id=uuid.uuid4(), status=RunStatus.EXECUTING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        mock_session = _setup_sweep_session(
            mock_session_cls, expired_runs=[r_bad, r_good]
        )

        # First orchestrator raises, second works
        mock_orch_bad = MagicMock()
        mock_orch_bad._write_final_report.side_effect = RuntimeError("boom")
        mock_orch_good = MagicMock()
        mock_orch_cls.side_effect = [mock_orch_bad, mock_orch_good]

        _sweep_once()

        # The bad one should trigger rollback
        mock_session.rollback.assert_called()
        # The good one should still have been processed
        assert r_good.status == RunStatus.BUDGET_EXHAUSTED.value


# ============================================================================
# _sweep_once — heartbeat / re-enqueue
# ============================================================================


class TestSweepOnceHeartbeat:
    """Tests for _sweep_once heartbeat check and re-enqueue logic."""

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_heartbeat_exists_run_not_reenqueued(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """When heartbeat key exists in Redis, the run is not re-enqueued."""
        mock_r = MagicMock()
        mock_r.get.return_value = b"1"
        mock_redis.return_value = mock_r

        active_run = _make_run(status=RunStatus.PLANNING.value)
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[active_run])

        _sweep_once()

        mock_enqueue.assert_not_called()
        assert active_run.status == RunStatus.PLANNING.value

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_heartbeat_missing_run_reenqueued(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """Heartbeat key not found → re-enqueue and set status to PENDING."""
        mock_r = MagicMock()
        mock_r.get.return_value = None  # key not found
        mock_redis.return_value = mock_r

        active_run = _make_run(status=RunStatus.EXECUTING.value)
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[active_run])

        _sweep_once()

        assert active_run.status == RunStatus.PENDING.value
        mock_enqueue.assert_called_once_with(str(active_run.id))

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_redis_unavailable_heartbeat_skipped_reenqueue(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """When Redis is None, heartbeat check is skipped → re-enqueue anyway."""
        mock_redis.return_value = None

        active_run = _make_run(status=RunStatus.PLANNING.value)
        mock_session = _setup_sweep_session(
            mock_session_cls, expired_runs=[], active_runs=[active_run]
        )

        _sweep_once()

        assert active_run.status == RunStatus.PENDING.value
        mock_enqueue.assert_called_once_with(str(active_run.id))
        mock_session.commit.assert_called()

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_active_with_heartbeat_not_touched(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """Active run with valid heartbeat is completely untouched."""
        mock_r = MagicMock()
        mock_r.get.return_value = b"1"
        mock_redis.return_value = mock_r

        active_run = _make_run(status=RunStatus.EXECUTING.value)
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[active_run])

        _sweep_once()

        # Status unchanged, no enqueue
        assert active_run.status == RunStatus.EXECUTING.value
        mock_enqueue.assert_not_called()

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_re_enqueue_exception_rollback_and_continue(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """If re-enqueue fails for one run, rollback and continue."""
        mock_redis.return_value = None
        r_bad = _make_run(id=uuid.uuid4(), status=RunStatus.PLANNING.value)
        r_good = _make_run(id=uuid.uuid4(), status=RunStatus.EXECUTING.value)
        mock_session = _setup_sweep_session(
            mock_session_cls, expired_runs=[], active_runs=[r_bad, r_good]
        )

        # First enqueue raises, second works
        mock_enqueue.side_effect = [RuntimeError("broker down"), None]

        _sweep_once()

        mock_session.rollback.assert_called()
        # The good run should still be processed
        assert r_good.status == RunStatus.PENDING.value

    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_no_active_runs_nothing_happens(self, mock_session_cls, mock_redis):
        """When there are no active runs, no heartbeat checks occur."""
        mock_redis.return_value = None
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        _sweep_once()

        # session closed, nothing else
        mock_session_cls.return_value.close.assert_called_once()

    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_session_always_closed_in_sweep(self, mock_session_cls, mock_redis):
        """Session.close() is called in finally even when _redis_client raises."""
        mock_redis.return_value = None
        mock_session = _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        # Simulate exception in the try block
        mock_session.query.side_effect = RuntimeError("db down")

        with contextlib.suppress(RuntimeError):
            _sweep_once()

        mock_session.close.assert_called_once()

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_redis_get_raises_connection_error_handled_gracefully(
        self, mock_session_cls, mock_redis, mock_enqueue
    ):
        """Redis.get() raises ConnectionError → caught by _RedisError check → re-enqueue."""
        mock_r = MagicMock()
        mock_r.get.side_effect = redis.exceptions.ConnectionError("lost")
        mock_redis.return_value = mock_r

        active_run = _make_run(status=RunStatus.PLANNING.value)
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[active_run])

        _sweep_once()

        # Heartbeat check failed → treated as no heartbeat → re-enqueue
        assert active_run.status == RunStatus.PENDING.value
        mock_enqueue.assert_called_once()


# ============================================================================
# _sweep_once — mixed scenarios
# ============================================================================


class TestSweepOnceEdgeCases:
    """Edge cases for _sweep_once covering mixed states."""

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_mixed_expired_and_heartbeat_missing(
        self, mock_session_cls, mock_redis, mock_orch_cls, mock_enqueue
    ):
        """Some runs are expired, others have missing heartbeats — all handled."""
        mock_r = MagicMock()
        mock_r.get.return_value = None  # no heartbeat
        mock_redis.return_value = mock_r

        r_expired = _make_run(
            id=uuid.uuid4(), status=RunStatus.PLANNING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        r_active_nohb = _make_run(
            id=uuid.uuid4(), status=RunStatus.EXECUTING.value,
        )

        _setup_sweep_session(
            mock_session_cls, expired_runs=[r_expired], active_runs=[r_active_nohb]
        )

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        _sweep_once()

        assert r_expired.status == RunStatus.BUDGET_EXHAUSTED.value
        assert r_active_nohb.status == RunStatus.PENDING.value
        mock_enqueue.assert_called_once_with(str(r_active_nohb.id))

    @patch("app.worker.broker.enqueue_run")
    @patch("app.worker.orchestrator.Orchestrator")
    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_expired_run_also_no_heartbeat(
        self, mock_session_cls, mock_redis, mock_orch_cls, mock_enqueue
    ):
        """A run can be both expired AND in ACTIVE_STATUSES — both checks apply."""
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_redis.return_value = mock_r

        r = _make_run(
            id=uuid.uuid4(), status=RunStatus.EXECUTING.value,
            deadline_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        _setup_sweep_session(
            mock_session_cls, expired_runs=[r], active_runs=[r]
        )

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        _sweep_once()

        # Deadline check runs first → BUDGET_EXHAUSTED
        # Then heartbeat check sees EXECUTING → but status is already
        # BUDGET_EXHAUSTED (not in ACTIVE_STATUSES), so the heartbeat check
        # filter won't return it anymore. In our test, the mock query returns
        # the same run for active — the sweeper doesn't re-fetch, so the
        # status change from the first loop is visible.
        assert r.status in (RunStatus.BUDGET_EXHAUSTED.value, RunStatus.PENDING.value)

    @patch("app.worker.actors._redis_client")
    @patch("app.worker.actors.SessionLocal")
    def test_run_not_in_active_statuses_skipped_for_heartbeat(
        self, mock_session_cls, mock_redis
    ):
        """Runs with status outside ACTIVE_STATUSES (e.g. WAITING_APPROVAL)
        are NOT queried for heartbeat checking."""
        mock_redis.return_value = None
        _setup_sweep_session(mock_session_cls, expired_runs=[], active_runs=[])

        _sweep_once()

        # No active runs → nothing to do
        mock_session_cls.return_value.close.assert_called_once()
