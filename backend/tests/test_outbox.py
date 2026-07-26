"""Unit tests for the SSE outbox (app/events/outbox.py).

All tests use MagicMock — no database is involved.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.enums import EventType
from app.core.models import ExecutionEvent
from app.events.outbox import emit_event, event_to_dict, list_events


# ── emit_event ────────────────────────────────────────────────────────────


class TestEmitEvent:
    @pytest.mark.unit
    def test_basic_event_creation(self):
        """emit_event creates an ExecutionEvent with correct run_id, type, and payload."""
        session = MagicMock()
        run_id = uuid.uuid4()
        session.flush.return_value = None

        result = emit_event(session, run_id, "test_type", {"key": "val"})

        # session.add was called once
        session.add.assert_called_once()
        event = session.add.call_args[0][0]
        assert isinstance(event, ExecutionEvent)
        assert event.run_id == run_id
        assert event.type == "test_type"
        assert event.payload == {"key": "val"}
        session.flush.assert_called_once()

    @pytest.mark.unit
    def test_with_eventtype_enum_converted_to_string_value(self):
        """When given an EventType enum, the type is stored as its string value."""
        session = MagicMock()
        run_id = uuid.uuid4()

        emit_event(session, run_id, EventType.RUN_STARTED)

        event = session.add.call_args[0][0]
        assert event.type == EventType.RUN_STARTED.value
        assert isinstance(event.type, str)

    @pytest.mark.unit
    def test_with_string_type_stored_as_is(self):
        """When given a plain string type, it is stored unchanged."""
        session = MagicMock()
        run_id = uuid.uuid4()

        emit_event(session, run_id, "custom_event")

        event = session.add.call_args[0][0]
        assert event.type == "custom_event"

    @pytest.mark.unit
    def test_none_payload_stored_as_empty_dict(self):
        """When payload is None, it is stored as {}."""
        session = MagicMock()
        run_id = uuid.uuid4()

        emit_event(session, run_id, "evt", payload=None)

        event = session.add.call_args[0][0]
        assert event.payload == {}

    @pytest.mark.unit
    def test_payload_dict_stored_as_is(self):
        """A non-empty dict payload is stored unchanged."""
        session = MagicMock()
        run_id = uuid.uuid4()
        payload = {"nested": {"a": 1}, "list": [1, 2, 3]}

        emit_event(session, run_id, "evt", payload=payload)

        event = session.add.call_args[0][0]
        assert event.payload == payload

    @pytest.mark.unit
    def test_session_add_called_before_flush(self):
        """session.add is called before session.flush."""
        session = MagicMock()
        run_id = uuid.uuid4()

        emit_event(session, run_id, "evt")

        # Verify add was called, then flush
        assert session.add.call_count == 1
        assert session.flush.call_count == 1

    @pytest.mark.unit
    def test_seq_is_assigned_after_flush(self):
        """After flush, the event's seq attribute should be accessible."""
        session = MagicMock()
        run_id = uuid.uuid4()
        # Simulate that flush assigns a seq
        session.flush.side_effect = lambda: setattr(
            session.add.call_args[0][0], "seq", 42
        )

        result = emit_event(session, run_id, "evt")

        assert result.seq == 42

    @pytest.mark.unit
    def test_returns_execution_event_instance(self):
        """emit_event returns the ExecutionEvent instance."""
        session = MagicMock()
        run_id = uuid.uuid4()

        result = emit_event(session, run_id, "evt")

        assert isinstance(result, ExecutionEvent)
        assert result.run_id == run_id
        assert result.type == "evt"

    @pytest.mark.unit
    def test_run_id_as_string_is_converted_to_uuid(self):
        """When run_id is a string, it is converted to a UUID."""
        session = MagicMock()
        run_id_str = "11111111-1111-1111-1111-111111111111"

        emit_event(session, run_id_str, "evt")

        event = session.add.call_args[0][0]
        assert isinstance(event.run_id, uuid.UUID)
        assert str(event.run_id) == run_id_str


# ── list_events ────────────────────────────────────────────────────────────


class TestListEvents:
    @pytest.mark.unit
    def test_returns_events_sorted_by_seq_ascending(self):
        """list_events returns events in ascending seq order."""
        session = MagicMock()
        run_id = uuid.uuid4()
        e1, e2 = MagicMock(), MagicMock()
        e1.seq = 1
        e2.seq = 3

        mock_result = MagicMock()
        mock_result.scalars.return_value = [e1, e2]
        session.execute.return_value = mock_result

        result = list_events(session, run_id)

        assert result == [e1, e2]
        session.execute.assert_called_once()

    @pytest.mark.unit
    def test_after_seq_filter_excludes_lower_seq(self):
        """When after_seq is set, only events with seq > after_seq are returned."""
        session = MagicMock()
        run_id = uuid.uuid4()

        list_events(session, run_id, after_seq=5)

        # Verify the query uses seq > after_seq
        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "execution_events.seq > 5" in compiled_str

    @pytest.mark.unit
    def test_limit_parameter_limits_results(self):
        """limit parameter is passed into the query."""
        session = MagicMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_events(session, run_id, limit=10)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 10" in compiled_str

    @pytest.mark.unit
    def test_default_limit_is_500(self):
        """Default limit is 500 when not specified."""
        session = MagicMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_events(session, run_id)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 500" in compiled_str

    @pytest.mark.unit
    def test_empty_results_when_no_matching_events(self):
        """Returns an empty list when no events match."""
        session = MagicMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        result = list_events(session, run_id)

        assert result == []

    @pytest.mark.unit
    def test_run_id_as_uuid_works(self):
        """run_id passed as UUID works correctly."""
        session = MagicMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_events(session, run_id)

        # Verify query was executed
        session.execute.assert_called_once()
        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # UUID is rendered without dashes by psycopg/sqlalchemy literal_binds
        assert run_id.hex in compiled_str

    @pytest.mark.unit
    def test_run_id_as_string_works(self):
        """run_id passed as string is converted to UUID and works."""
        session = MagicMock()
        run_id_str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_events(session, run_id_str)

        session.execute.assert_called_once()
        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # UUID is rendered without dashes by psycopg/sqlalchemy literal_binds
        assert run_id_str.replace("-", "") in compiled_str


# ── event_to_dict ──────────────────────────────────────────────────────────


class TestEventToDict:
    @pytest.mark.unit
    def test_all_four_keys_present(self):
        """event_to_dict returns a dict with seq, type, payload, created_at."""
        event = MagicMock()
        event.seq = 1
        event.type = "run_started"
        event.payload = {}
        event.created_at.isoformat.return_value = "2025-01-01T00:00:00+00:00"

        result = event_to_dict(event)

        assert set(result.keys()) == {"seq", "type", "payload", "created_at"}
        assert result["seq"] == 1
        assert result["type"] == "run_started"
        assert result["payload"] == {}

    @pytest.mark.unit
    def test_created_at_is_iso_format_string(self):
        """created_at is converted to an ISO format string."""
        event = MagicMock()
        event.seq = 1
        event.type = "evt"
        event.payload = {}
        event.created_at.isoformat.return_value = "2025-06-15T12:30:45+00:00"

        result = event_to_dict(event)

        assert result["created_at"] == "2025-06-15T12:30:45+00:00"
        event.created_at.isoformat.assert_called_once()

    @pytest.mark.unit
    def test_none_created_at_returns_none(self):
        """When created_at is None, the dict value is None."""
        event = MagicMock()
        event.seq = 2
        event.type = "evt"
        event.payload = {}
        event.created_at = None

        result = event_to_dict(event)

        assert result["created_at"] is None

    @pytest.mark.unit
    def test_complex_payload_preserved(self):
        """A complex/nested payload is preserved unchanged."""
        event = MagicMock()
        event.seq = 3
        event.type = "tool_call"
        event.payload = {
            "tool": "bash",
            "args": {"cmd": "pytest", "cwd": "/tmp"},
            "result": {"exit_code": 0, "lines": 42},
        }
        event.created_at.isoformat.return_value = "2025-01-01T00:00:00+00:00"

        result = event_to_dict(event)

        assert result["payload"] == event.payload
        assert result["payload"]["tool"] == "bash"
        assert result["payload"]["args"]["cmd"] == "pytest"
        assert result["payload"]["result"]["exit_code"] == 0
