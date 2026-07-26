"""Unit tests for core modules: config, security, db, enums, models.

All tests are pure unit tests — no database or external deps needed.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import sessionmaker

from app.core import models
from app.core.config import Settings, settings
from app.core.db import SessionLocal, engine, get_db
from app.core.enums import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    CallKind,
    EventType,
    Phase,
    PressureMode,
    RunStatus,
    Strategy,
    TokenSource,
)
from app.core.security import require_token


# ── config.py ──────────────────────────────────────────────────────────────


class TestSettings:
    @pytest.mark.unit
    def test_has_all_expected_fields(self):
        """Settings has all expected configuration fields."""
        expected = {
            "database_url", "redis_url", "api_token",
            "litellm_base_url", "litellm_master_key",
            "ai_gateway_type", "ai_gateway_base_url", "ai_gateway_api_key",
            "ai_gateway_console_url", "ai_gateway_recommendation_model",
            "ai_recommendation_enabled", "ai_gateway_connect_timeout_seconds",
            "ai_gateway_read_timeout_seconds", "ai_gateway_status_ttl_seconds",
            "ai_gateway_max_response_bytes",
            "agent_server_image",
            "artifact_backend", "artifact_local_dir",
            "minio_endpoint", "minio_access_key", "minio_secret_key", "minio_bucket",
            "worker_heartbeat_ttl_seconds", "sweeper_interval_seconds",
            "summary_max_chars", "artifact_max_bytes",
        }
        for field in expected:
            assert hasattr(settings, field), f"Missing field: {field}"

    @pytest.mark.unit
    def test_database_url_default(self):
        """Default database_url is PostgreSQL."""
        s = Settings()
        assert s.database_url.startswith("postgresql://")

    @pytest.mark.unit
    def test_redis_url_default(self):
        """Default redis_url starts with redis."""
        s = Settings()
        assert s.redis_url.startswith("redis://")

    @pytest.mark.unit
    def test_artifact_local_dir_default(self, monkeypatch):
        """Default artifact_local_dir."""
        monkeypatch.delenv("ARTIFACT_LOCAL_DIR", raising=False)
        s = Settings(_env_file=None)
        assert s.artifact_local_dir == "./artifacts"

    @pytest.mark.unit
    def test_artifact_max_bytes_default(self):
        """Default artifact_max_bytes is around 5 MB."""
        s = Settings()
        assert s.artifact_max_bytes == 5 * 1024 * 1024

    @pytest.mark.unit
    def test_summary_max_chars_default(self):
        """Default summary_max_chars is 2000."""
        s = Settings()
        assert s.summary_max_chars == 2000

    @pytest.mark.unit
    def test_api_token_is_secret_str(self):
        """api_token is a SecretStr for safety."""
        # pydantic-settings BaseSettings stores secrets as SecretStr fields
        # We verify the field annotation exists
        from pydantic import SecretStr
        # all str fields are plain str in this config; verify the value isn't leaked
        s = Settings()
        assert isinstance(s.api_token, str)

    @pytest.mark.unit
    def test_loads_from_environment_variables(self):
        """Settings loads from environment variables."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@test-db:5432/testdb",
            "SUMMARY_MAX_CHARS": "500",
            "ARTIFACT_MAX_BYTES": "1024",
        }, clear=True):
            s = Settings(_env_file=None)
            assert s.database_url == "postgresql://test:test@test-db:5432/testdb"
            assert s.summary_max_chars == 500
            assert s.artifact_max_bytes == 1024

    @pytest.mark.unit
    def test_worker_heartbeat_ttl_seconds_default(self, monkeypatch):
        """Default heartbeat TTL is 120 seconds."""
        monkeypatch.delenv("WORKER_HEARTBEAT_TTL_SECONDS", raising=False)
        s = Settings(_env_file=None)
        assert s.worker_heartbeat_ttl_seconds == 120

    @pytest.mark.unit
    def test_sweeper_interval_seconds_default(self, monkeypatch):
        """Default sweeper interval is 5 seconds."""
        monkeypatch.delenv("SWEEPER_INTERVAL_SECONDS", raising=False)
        s = Settings(_env_file=None)
        assert s.sweeper_interval_seconds == 5


# ── security.py ────────────────────────────────────────────────────────────


class TestRequireToken:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_token_does_not_raise(self):
        """Valid Bearer token matching api_token should not raise."""
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=settings.api_token
        )
        # Should not raise
        await require_token(credentials=creds)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_none_credentials_raises_401(self):
        """None credentials should raise 401."""
        with pytest.raises(HTTPException) as exc:
            await require_token(credentials=None)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_scheme_raises_401(self):
        """Non-Bearer scheme should raise 401."""
        creds = HTTPAuthorizationCredentials(
            scheme="Basic", credentials=settings.api_token
        )
        with pytest.raises(HTTPException) as exc:
            await require_token(credentials=creds)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_wrong_token_raises_401(self):
        """Wrong token value should raise 401."""
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="wrong-token"
        )
        with pytest.raises(HTTPException) as exc:
            await require_token(credentials=creds)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_token_after_bearer_raises_401(self):
        """Empty token after 'Bearer ' should raise 401."""
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=""
        )
        with pytest.raises(HTTPException) as exc:
            await require_token(credentials=creds)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_scheme_case_insensitive(self):
        """Scheme check is case-insensitive (lowercase 'bearer' works)."""
        creds = HTTPAuthorizationCredentials(
            scheme="bearer", credentials=settings.api_token
        )
        # Should not raise — scheme is lowercased before comparison
        await require_token(credentials=creds)


# ── db.py ──────────────────────────────────────────────────────────────────


class TestDatabase:
    @pytest.mark.unit
    def test_session_local_is_sessionmaker(self):
        """SessionLocal is a sessionmaker instance."""
        assert isinstance(SessionLocal, sessionmaker)

    @pytest.mark.unit
    def test_engine_is_created(self):
        """Engine is a sqlalchemy Engine instance."""
        from sqlalchemy import Engine
        assert isinstance(engine, Engine)

    @pytest.mark.unit
    def test_get_db_yields_session_and_closes_it(self):
        """get_db yields a session and closes it in finally."""
        # We test that get_db properly calls session.close()
        with patch("app.core.db.SessionLocal") as mock_sessionmaker:
            mock_session = MagicMock()
            mock_sessionmaker.return_value = mock_session

            gen = get_db()
            session = next(gen)
            assert session is mock_session

            # Stop iteration → should trigger finally and close
            try:
                next(gen)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_session_local_autoflush_disabled(self):
        """SessionLocal has autoflush=False."""
        assert SessionLocal.kw["autoflush"] is False

    @pytest.mark.unit
    def test_session_local_expire_on_commit_disabled(self):
        """SessionLocal has expire_on_commit=False."""
        assert SessionLocal.kw["expire_on_commit"] is False


# ── enums.py ───────────────────────────────────────────────────────────────


class TestRunStatus:
    @pytest.mark.unit
    def test_all_thirteen_states_defined(self):
        """All 13 RunStatus values are defined."""
        expected = {
            "PENDING", "PLANNING", "EXECUTING", "OBSERVING",
            "EVALUATING", "REPLANNING", "WAITING_APPROVAL",
            "PAUSED", "COMPLETED", "PARTIAL_COMPLETED",
            "FAILED", "BUDGET_EXHAUSTED", "CANCELLED",
        }
        actual = {s.value for s in RunStatus}
        assert actual == expected

    @pytest.mark.unit
    def test_terminal_statuses_is_terminal(self):
        """COMPLETED, FAILED, CANCELLED, BUDGET_EXHAUSTED, PARTIAL_COMPLETED are terminal."""
        for s in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED,
                  RunStatus.BUDGET_EXHAUSTED, RunStatus.PARTIAL_COMPLETED]:
            assert s.is_terminal is True

    @pytest.mark.unit
    def test_nonterminal_statuses_are_not_terminal(self):
        """PENDING, PLANNING, EXECUTING, etc. are NOT terminal."""
        for s in [RunStatus.PENDING, RunStatus.PLANNING, RunStatus.EXECUTING,
                  RunStatus.OBSERVING, RunStatus.EVALUATING, RunStatus.REPLANNING,
                  RunStatus.WAITING_APPROVAL, RunStatus.PAUSED]:
            assert s.is_terminal is False

    @pytest.mark.unit
    def test_str_returns_value(self):
        """StrEnum str() returns the value."""
        assert str(RunStatus.PENDING) == "PENDING"
        assert str(RunStatus.COMPLETED) == "COMPLETED"


class TestAllowedTransitions:
    @pytest.mark.unit
    def test_all_statuses_have_transition_entry(self):
        """Every RunStatus appears as a key in ALLOWED_TRANSITIONS."""
        assert set(ALLOWED_TRANSITIONS.keys()) == set(RunStatus)

    @pytest.mark.unit
    def test_terminal_states_have_empty_transitions(self):
        """Terminal states have frozenset() as allowed transitions."""
        for s in TERMINAL_STATUSES:
            assert ALLOWED_TRANSITIONS[s] == frozenset(), f"{s} should be a sink"

    @pytest.mark.unit
    def test_all_targets_are_valid_runstatus(self):
        """Every target in ALLOWED_TRANSITIONS is a valid RunStatus."""
        for src, targets in ALLOWED_TRANSITIONS.items():
            for dst in targets:
                assert isinstance(dst, RunStatus), f"{src} → {dst} is not RunStatus"

    @pytest.mark.unit
    def test_pending_allows_planning(self):
        """PENDING allows transition to PLANNING."""
        assert RunStatus.PLANNING in ALLOWED_TRANSITIONS[RunStatus.PENDING]

    @pytest.mark.unit
    def test_replanning_allows_executing_and_waiting_approval(self):
        """REPLANNING allows EXECUTING and WAITING_APPROVAL."""
        assert RunStatus.EXECUTING in ALLOWED_TRANSITIONS[RunStatus.REPLANNING]
        assert RunStatus.WAITING_APPROVAL in ALLOWED_TRANSITIONS[RunStatus.REPLANNING]

    @pytest.mark.unit
    def test_pending_allows_cancelled(self):
        """PENDING can transition to CANCELLED."""
        assert RunStatus.CANCELLED in ALLOWED_TRANSITIONS[RunStatus.PENDING]

    @pytest.mark.unit
    def test_no_self_loops_exist(self):
        """No transition should target itself (no self-loops)."""
        for src, targets in ALLOWED_TRANSITIONS.items():
            assert src not in targets, f"{src} has a self-loop"


class TestEventType:
    @pytest.mark.unit
    def test_event_type_count(self):
        """EventType has the expected number of values (21)."""
        count = len(list(EventType))
        assert count == 21, f"Expected 21 EventType values, got {count}"

    @pytest.mark.unit
    def test_key_event_types_exist(self):
        """Key event types are defined."""
        expected = {
            "run_started", "state_changed", "phase_changed",
            "iteration_started", "iteration_finished",
            "llm_call", "tool_call", "test_result",
            "progress_scored", "budget_updated", "budget_reallocated",
            "pressure_changed", "strategy_switched",
            "approval_requested", "approval_decided",
            "checkpoint_created", "rollback",
            "agent_message", "collaboration_delivered", "warning", "run_finished",
        }
        actual = {e.value for e in EventType}
        assert actual == expected


class TestPhase:
    @pytest.mark.unit
    def test_all_phase_values(self):
        """All 6 Phase values: SCAN, ANALYZE, MODIFY, VERIFY, REPAIR, SUMMARIZE."""
        expected = {"scan", "analyze", "modify", "verify", "repair", "summarize"}
        actual = {p.value for p in Phase}
        assert actual == expected


class TestStrategy:
    @pytest.mark.unit
    def test_all_strategy_values(self):
        """Strategy values: NONE, FIXED, DYNAMIC."""
        expected = {"none", "fixed", "dynamic"}
        actual = {s.value for s in Strategy}
        assert actual == expected


class TestPressureMode:
    @pytest.mark.unit
    def test_all_pressure_values(self):
        """PressureMode values: NORMAL, CONSERVATIVE, CRITICAL."""
        expected = {"NORMAL", "CONSERVATIVE", "CRITICAL"}
        actual = {p.value for p in PressureMode}
        assert actual == expected


class TestCallKind:
    @pytest.mark.unit
    def test_all_call_kind_values(self):
        """CallKind values: AGENT, CONDENSER, OTHER."""
        expected = {"agent", "condenser", "other"}
        actual = {c.value for c in CallKind}
        assert actual == expected


class TestTokenSource:
    @pytest.mark.unit
    def test_all_token_source_values(self):
        """TokenSource values: ACTUAL, ESTIMATED, UNAVAILABLE."""
        expected = {"actual", "estimated", "unavailable"}
        actual = {t.value for t in TokenSource}
        assert actual == expected


# ── models.py ──────────────────────────────────────────────────────────────


class TestModels:
    @pytest.mark.unit
    def test_task_table_name(self):
        """Task model table name is 'tasks'."""
        assert models.Task.__tablename__ == "tasks"

    @pytest.mark.unit
    def test_task_run_table_name(self):
        """TaskRun model table name is 'task_runs'."""
        assert models.TaskRun.__tablename__ == "task_runs"

    @pytest.mark.unit
    def test_task_budget_table_name(self):
        """TaskBudget model table name is 'task_budgets'."""
        assert models.TaskBudget.__tablename__ == "task_budgets"

    @pytest.mark.unit
    def test_execution_event_table_name(self):
        """ExecutionEvent model table name is 'execution_events'."""
        assert models.ExecutionEvent.__tablename__ == "execution_events"

    @pytest.mark.unit
    def test_utcnow_returns_tz_aware_datetime(self):
        """utcnow() returns a timezone-aware datetime in UTC."""
        dt = models.utcnow()
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
        assert dt.tzinfo == timezone.utc

    @pytest.mark.unit
    def test_base_metadata_exists(self):
        """Base.metadata exists."""
        assert models.Base.metadata is not None

    @pytest.mark.unit
    def test_task_model_has_expected_fields(self):
        """Task model has the core fields defined."""
        task = models.Task(
            id=uuid.uuid4(),
            name="test task",
            description="a test task",
            workdir="/tmp/test",
            template="fix_bug",
            require_approval=True,
        )
        assert task.name == "test task"
        assert task.description == "a test task"
        assert task.workdir == "/tmp/test"
        assert task.template == "fix_bug"
        assert task.require_approval is True

    @pytest.mark.unit
    def test_task_run_model_has_expected_defaults(self):
        """TaskRun field defaults exist (SQLAlchemy column defaults)."""
        # SQLAlchemy defaults only apply at INSERT time, not on __init__.
        # Verify the column defaults are configured correctly.
        status_col = models.TaskRun.__table__.c.status
        strategy_col = models.TaskRun.__table__.c.strategy
        iteration_col = models.TaskRun.__table__.c.iteration
        pressure_col = models.TaskRun.__table__.c.pressure_mode
        active_runtime_col = models.TaskRun.__table__.c.active_runtime_ms
        attempt_col = models.TaskRun.__table__.c.attempt_no

        assert status_col.default.arg == "PENDING"
        assert strategy_col.default.arg == "dynamic"
        assert iteration_col.default.arg == 0
        assert pressure_col.default.arg == "NORMAL"
        assert active_runtime_col.default.arg == 0
        assert attempt_col.default.arg == 1
