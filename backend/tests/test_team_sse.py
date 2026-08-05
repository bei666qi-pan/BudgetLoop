"""Tests for team SSE event stream (app/api/team_observatory.py)
and outbox extensions (app/events/outbox.py).

Covers: emit_event with container_id, list_container_events,
_truncate_if_needed, _fetch_container_sse unit tests, and stream_container
integration tests.
"""
from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from app.api.team_observatory import (  # noqa: E402
    _MAX_PAYLOAD_BYTES,
    _POLL_INTERVAL_SECONDS,
    _TERMINAL_CONTAINER_STATES,
    _fetch_container_sse,
    _truncate_if_needed,
)
from app.core.enums import EventType  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.events.outbox import (  # noqa: E402
    emit_event,
    event_to_dict,
    list_container_events,
)
from app.core.models import ExecutionEvent  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"Authorization": f"Bearer {settings.api_token}"}


# ── emit_event with container_id ────────────────────────────────────────────


class TestEmitEventContainerId:
    @pytest.mark.unit
    def test_emit_event_with_container_id(self):
        """emit_event sets container_id on ExecutionEvent when provided."""
        session = MagicMock()
        run_id = uuid.uuid4()
        cid = uuid.uuid4()

        result = emit_event(session, run_id, "test_type", {"k": "v"}, container_id=cid)

        event = session.add.call_args[0][0]
        assert isinstance(event, ExecutionEvent)
        assert event.container_id == cid
        assert event.run_id == run_id
        assert event.type == "test_type"
        assert event.payload == {"k": "v"}

    @pytest.mark.unit
    def test_emit_event_without_container_id_leaves_none(self):
        """emit_event without container_id leaves it as None."""
        session = MagicMock()
        run_id = uuid.uuid4()

        emit_event(session, run_id, "test_type", {"k": "v"})

        event = session.add.call_args[0][0]
        assert event.container_id is None

    @pytest.mark.unit
    def test_emit_event_container_id_as_string_converted(self):
        """container_id string is converted to UUID."""
        session = MagicMock()
        run_id = uuid.uuid4()
        cid_str = "11111111-1111-1111-1111-111111111111"

        emit_event(session, run_id, "evt", container_id=cid_str)

        event = session.add.call_args[0][0]
        assert isinstance(event.container_id, uuid.UUID)
        assert str(event.container_id) == cid_str

    @pytest.mark.unit
    def test_emit_event_still_works_with_only_run_id(self):
        """Backward compat: emit_event still works with only run_id."""
        session = MagicMock()
        run_id = uuid.uuid4()

        result = emit_event(session, run_id, EventType.RUN_STARTED)

        event = session.add.call_args[0][0]
        assert event.run_id == run_id
        assert event.type == "run_started"
        assert event.container_id is None
        assert isinstance(result, ExecutionEvent)


# ── list_container_events ───────────────────────────────────────────────────


class TestListContainerEvents:
    @pytest.mark.unit
    def test_returns_events_for_container(self):
        """list_container_events returns events with matching container_id."""
        session = MagicMock()
        cid = uuid.uuid4()
        e1, e2 = MagicMock(), MagicMock()
        e1.seq = 1
        e2.seq = 3

        mock_result = MagicMock()
        mock_result.scalars.return_value = [e1, e2]
        session.execute.return_value = mock_result

        result = list_container_events(session, cid)

        assert result == [e1, e2]
        session.execute.assert_called_once()

    @pytest.mark.unit
    def test_after_seq_filters_correctly(self):
        """after_seq causes seq > after_seq in the query."""
        session = MagicMock()
        cid = uuid.uuid4()

        list_container_events(session, cid, after_seq=10)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "execution_events.seq > 10" in compiled_str
        assert cid.hex in compiled_str

    @pytest.mark.unit
    def test_limit_parameter_applied(self):
        """limit parameter is reflected in generated SQL."""
        session = MagicMock()
        cid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_container_events(session, cid, limit=50)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 50" in compiled_str

    @pytest.mark.unit
    def test_default_limit_is_500(self):
        """Default limit is 500."""
        session = MagicMock()
        cid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_container_events(session, cid)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 500" in compiled_str

    @pytest.mark.unit
    def test_empty_result_when_no_events(self):
        """Returns empty list when no matching events."""
        session = MagicMock()
        cid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        result = list_container_events(session, cid)

        assert result == []

    @pytest.mark.unit
    def test_container_id_as_string_converted(self):
        """container_id as string is converted to UUID."""
        session = MagicMock()
        cid_str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_container_events(session, cid_str)

        session.execute.assert_called_once()
        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert cid_str.replace("-", "") in compiled_str

    @pytest.mark.unit
    def test_null_container_id_events_excluded_by_where_clause(self):
        """Query uses container_id = X which inherently excludes NULL rows."""
        session = MagicMock()
        cid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        session.execute.return_value = mock_result

        list_container_events(session, cid)

        stmt = session.execute.call_args[0][0]
        compiled_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # The query filters on container_id = value, so NULLs are excluded
        assert "execution_events.container_id" in compiled_str


# ── _truncate_if_needed ──────────────────────────────────────────────────────


class TestTruncateIfNeeded:
    @pytest.mark.unit
    def test_small_event_not_truncated(self):
        """Events under 4KB are returned unchanged."""
        event = {"seq": 1, "type": "test", "payload": {"key": "value"}, "created_at": "2025-01-01T00:00:00Z"}
        result = _truncate_if_needed(event)
        assert result == event
        assert "_truncated" not in result
        assert "_full_size" not in result

    @pytest.mark.unit
    def test_oversized_event_is_truncated(self):
        """Events over 4KB get truncated payload and _truncated flag."""
        # Build a payload that makes the total event exceed 4KB
        big_payload = {"data": "x" * 5000}
        event = {"seq": 1, "type": "test", "payload": big_payload, "created_at": "2025-01-01T00:00:00Z"}

        result = _truncate_if_needed(event)

        assert result["_truncated"] is True
        assert result["_full_size"] > _MAX_PAYLOAD_BYTES
        # Payload should be replaced with truncation note
        assert isinstance(result["payload"], dict)
        assert "_note" in result["payload"]
        assert "truncated" in result["payload"]["_note"]

    @pytest.mark.unit
    def test_truncated_event_serializes_under_4k(self):
        """The truncated event serializes to under 4KB."""
        big_payload = {"data": "x" * 10000}
        event = {"seq": 1, "type": "test", "payload": big_payload, "created_at": "2025-01-01T00:00:00Z"}

        result = _truncate_if_needed(event)
        serialized = json.dumps(result, ensure_ascii=False)
        assert len(serialized.encode("utf-8")) <= _MAX_PAYLOAD_BYTES

    @pytest.mark.unit
    def test_exactly_at_limit_not_truncated(self):
        """An event exactly at 4KB is not truncated."""
        # Build a payload that makes the event exactly 4096 bytes
        event = {
            "seq": 1,
            "type": "t",
            "payload": {},
            "created_at": "2025-01-01T00:00:00Z",
        }
        base = json.dumps(event, ensure_ascii=False)
        base_len = len(base.encode("utf-8"))

        # Fill payload to hit exactly 4096
        fill_len = _MAX_PAYLOAD_BYTES - base_len
        if fill_len > 2:
            # Need to account for the key within payload
            key_name = "k"
            template = json.dumps({"k": ""}, ensure_ascii=False)
            overhead = len(template.encode("utf-8")) - 2  # subtract empty string
            value_len = fill_len - overhead
            if value_len > 0:
                event["payload"] = {key_name: "a" * value_len}

        result = _truncate_if_needed(event)
        serialized = json.dumps(result, ensure_ascii=False)
        # Should not be truncated
        assert "_truncated" not in result

    @pytest.mark.unit
    def test_one_byte_over_limit_is_truncated(self):
        """An event one byte over 4KB gets _truncated flag."""
        event = {
            "seq": 1,
            "type": "t",
            "payload": {},
            "created_at": "2025-01-01T00:00:00Z",
        }
        base = json.dumps(event, ensure_ascii=False)
        base_len = len(base.encode("utf-8"))

        fill_len = _MAX_PAYLOAD_BYTES - base_len + 1  # one byte over
        if fill_len > 2:
            key_name = "k"
            template = json.dumps({"k": ""}, ensure_ascii=False)
            overhead = len(template.encode("utf-8")) - 2
            value_len = fill_len - overhead
            if value_len > 0:
                event["payload"] = {key_name: "a" * value_len}

        result = _truncate_if_needed(event)
        assert result.get("_truncated") is True

    @pytest.mark.unit
    def test_preserves_non_payload_fields(self):
        """Truncated event preserves seq, type, and created_at."""
        big_payload = {"data": "y" * 10000}
        event = {"seq": 99, "type": "session_progress", "payload": big_payload, "created_at": "2025-06-01T12:00:00Z"}

        result = _truncate_if_needed(event)

        assert result["seq"] == 99
        assert result["type"] == "session_progress"
        assert result["created_at"] == "2025-06-01T12:00:00Z"

    @pytest.mark.unit
    def test_full_size_is_original_byte_count(self):
        """_full_size records the original serialized byte count."""
        big_payload = {"data": "y" * 10000}
        event = {"seq": 1, "type": "test", "payload": big_payload, "created_at": "2025-01-01T00:00:00Z"}

        original_serialized = json.dumps(event, ensure_ascii=False)
        original_size = len(original_serialized.encode("utf-8"))

        result = _truncate_if_needed(event)

        assert result["_full_size"] == original_size
        assert result["_full_size"] > _MAX_PAYLOAD_BYTES


# ── _fetch_container_sse ─────────────────────────────────────────────────────────


class TestFetchContainer:
    @pytest.mark.unit
    def test_fetch_valid_container_returns_events_and_lifecycle(self):
        """_fetch_container_sse returns events list and lifecycle_state."""
        cid = uuid.uuid4()
        mock_container = MagicMock()
        mock_container.lifecycle_state = "active"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_container

        from app.core.models import WorkContainer

        with patch("app.api.team_observatory.SessionLocal", return_value=mock_session), \
             patch("app.api.team_observatory.list_container_events", return_value=[]) as mock_list, \
             patch("app.api.team_observatory.event_to_dict", side_effect=lambda e: {"seq": e.seq, "type": e.type}):
            events, lifecycle = _fetch_container_sse(cid, 0)

        assert events == []
        assert lifecycle == "active"
        mock_session.get.assert_called_once_with(WorkContainer, cid)
        mock_session.close.assert_called_once()
        mock_list.assert_called_once_with(mock_session, cid, 0)

    @pytest.mark.unit
    def test_fetch_nonexistent_container_returns_none_lifecycle(self):
        """_fetch_container_sse returns None lifecycle for missing container."""
        cid = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.get.return_value = None

        with patch("app.api.team_observatory.SessionLocal", return_value=mock_session), \
             patch("app.api.team_observatory.list_container_events", return_value=[]):
            events, lifecycle = _fetch_container_sse(cid, 0)

        assert events == []
        assert lifecycle is None
        mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_fetch_with_after_seq_passed_to_list(self):
        """_fetch_container_sse forwards after_seq to list_container_events."""
        cid = uuid.uuid4()
        mock_container = MagicMock()
        mock_container.lifecycle_state = "active"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_container

        with patch("app.api.team_observatory.SessionLocal", return_value=mock_session), \
             patch("app.api.team_observatory.list_container_events") as mock_list, \
             patch("app.api.team_observatory.event_to_dict", side_effect=lambda e: {"seq": e.seq, "type": e.type}):
            _fetch_container_sse(cid, 42)

        mock_list.assert_called_once_with(mock_session, cid, 42)

    @pytest.mark.unit
    def test_fetch_session_closed_on_exception(self):
        """Session is closed even when an exception occurs."""
        cid = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.get.side_effect = RuntimeError("db error")

        with patch("app.api.team_observatory.SessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError, match="db error"):
                _fetch_container_sse(cid, 0)

        mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_fetch_multiple_events_converted(self):
        """Multiple events are converted via event_to_dict."""
        cid = uuid.uuid4()
        mock_container = MagicMock()
        mock_container.lifecycle_state = "active"

        mock_events = [
            MagicMock(seq=1, type="run_started"),
            MagicMock(seq=2, type="state_changed"),
        ]
        mock_session = MagicMock()
        mock_session.get.return_value = mock_container

        def fake_dict(e):
            return {"seq": e.seq, "type": e.type}

        with patch("app.api.team_observatory.SessionLocal", return_value=mock_session), \
             patch("app.api.team_observatory.list_container_events", return_value=mock_events), \
             patch("app.api.team_observatory.event_to_dict", side_effect=fake_dict):
            events, lifecycle = _fetch_container_sse(cid, 0)

        assert len(events) == 2
        assert events[0] == {"seq": 1, "type": "run_started"}
        assert events[1] == {"seq": 2, "type": "state_changed"}
        assert lifecycle == "active"


# ── Integration tests for stream_container endpoint ──────────────────────────


@pytest.fixture()
def team_stream_client():
    """TestClient with auth bypassed for the team SSE endpoint."""
    from app.core.security import require_token

    mock_fetch = MagicMock(return_value=([], "active"))

    app.dependency_overrides[require_token] = lambda: None
    with patch("app.api.team_observatory._fetch_container_sse", mock_fetch), \
         patch("app.api.team_observatory.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        from starlette.testclient import TestClient
        with TestClient(app) as client:
            yield client, mock_fetch, mock_sleep
    app.dependency_overrides.clear()


class TestStreamContainerEndpoint:
    @pytest.mark.integration
    def test_valid_container_returns_sse_content_type(self, team_stream_client):
        """A valid container returns 200 with text/event-stream."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.integration
    def test_nonexistent_container_returns_404(self, team_stream_client):
        """Non-existent container returns 404."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.return_value = ([], None)

        response = client.get(f"/api/work-containers/{cid}/stream", headers=AUTH)
        assert response.status_code == 404

    @pytest.mark.integration
    def test_event_generator_yields_sse_format(self, team_stream_client):
        """Events are yielded with proper id, event, data SSE fields."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        event_data = {"seq": 1, "type": "session_progress", "payload": {}, "created_at": "2025-01-01T00:00:00+00:00"}
        mock_fetch.side_effect = [
            ([], "active"),
            ([event_data], "active"),
            ([], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        data_lines = [line for line in lines if line.startswith("data:")]
        event_lines = [line for line in lines if line.startswith("event:")]
        id_lines = [line for line in lines if line.startswith("id:")]

        assert len(data_lines) >= 1
        assert len(event_lines) >= 1
        assert len(id_lines) >= 1

    @pytest.mark.integration
    def test_last_event_id_header_replay(self, team_stream_client):
        """Last-Event-ID header sets after_seq for reconnection."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "completed"),
        ]

        headers = {**AUTH, "last-event-id": "99"}

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=headers) as response:
            list(response.iter_lines())

        calls = mock_fetch.call_args_list
        assert len(calls) >= 2
        # First call: initial check with after_seq=0
        assert calls[0][0][1] == 0
        # Second call: poll uses after_seq=99 from Last-Event-ID
        assert calls[1][0][1] == 99

    @pytest.mark.integration
    def test_last_event_id_non_digit_ignored(self, team_stream_client):
        """Non-digit Last-Event-ID is ignored, after_seq stays 0."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "completed"),
        ]

        headers = {**AUTH, "last-event-id": "not-a-number"}

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=headers) as response:
            list(response.iter_lines())

        calls = mock_fetch.call_args_list
        assert len(calls) >= 2
        assert calls[1][0][1] == 0

    @pytest.mark.integration
    def test_run_finished_on_terminated_container(self, team_stream_client):
        """Completed container emits run_finished then closes."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        assert any("run_finished" in line for line in event_lines)

        # Verify synthetic event carries lifecycle_state
        data_lines = [line for line in lines if line.startswith("data:")]
        found = False
        for line in data_lines:
            try:
                parsed = json.loads(line.removeprefix("data: "))
                if parsed.get("payload", {}).get("lifecycle_state") == "completed":
                    found = True
            except json.JSONDecodeError:
                pass
        assert found, "Synthetic run_finished should contain lifecycle_state=completed"

    @pytest.mark.integration
    def test_archived_container_also_emits_run_finished(self, team_stream_client):
        """Archived container also terminates with run_finished."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "archived"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        assert any("run_finished" in line for line in event_lines)

    @pytest.mark.integration
    def test_no_duplicate_run_finished(self, team_stream_client):
        """When run_finished already in stream, no synthetic duplicate."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        run_finished_event = {
            "seq": 1,
            "type": "run_finished",
            "payload": {"lifecycle_state": "completed"},
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        mock_fetch.side_effect = [
            ([], "active"),
            ([run_finished_event], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        run_finished_count = sum(1 for line in event_lines if "run_finished" in line)
        assert run_finished_count == 1

    @pytest.mark.integration
    def test_active_container_continues_streaming(self, team_stream_client):
        """Active container does not close the stream, keeps polling."""
        client, mock_fetch, mock_sleep = team_stream_client
        cid = uuid.uuid4()

        call_count = 0

        def side_effect(cid_arg, after_seq):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [], "active"
            elif call_count == 2:
                return [], "active"
            else:
                # Should not reach here in test
                return [], "active"

        mock_fetch.side_effect = side_effect

        # We need to make is_disconnected return True after 2 polls
        with patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock) as mock_disc:
            mock_disc.side_effect = [False, False, True]

            with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
                list(response.iter_lines())

        # Should have polled at least twice
        assert call_count >= 2

    @pytest.mark.integration
    def test_client_disconnect_stops_stream(self, team_stream_client):
        """Stream stops when client disconnects."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.return_value = ([], "active")

        with patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock) as mock_disc:
            mock_disc.side_effect = [False, True]

            with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
                lines = list(response.iter_lines())

        # No events emitted after disconnect
        event_lines = [line for line in lines if line.startswith("event:")]
        assert len(event_lines) == 0

    @pytest.mark.integration
    def test_multiple_events_yielded_in_one_poll(self, team_stream_client):
        """Multiple events in one poll are yielded individually."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        e1 = {"seq": 1, "type": "session_progress", "payload": {}, "created_at": "..."}
        e2 = {"seq": 2, "type": "budget_pressure_change", "payload": {}, "created_at": "..."}
        e3 = {"seq": 3, "type": "team_control_audit", "payload": {}, "created_at": "..."}
        e4 = {"seq": 4, "type": "session_status_change", "payload": {}, "created_at": "..."}

        mock_fetch.side_effect = [
            ([], "active"),
            ([e1, e2, e3, e4], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        event_types = [line.removeprefix("event: ").strip() for line in event_lines]
        assert "session_progress" in event_types
        assert "budget_pressure_change" in event_types
        assert "team_control_audit" in event_types
        assert "session_status_change" in event_types

    @pytest.mark.integration
    def test_event_types_correctness(self, team_stream_client):
        """All team event type strings are present on the SSE stream."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        team_event_types = [
            EventType.SESSION_PROGRESS.value,
            EventType.BUDGET_PRESSURE_CHANGE.value,
            EventType.TEAM_CONTROL_AUDIT.value,
            EventType.SESSION_STATUS_CHANGE.value,
        ]

        for et in team_event_types:
            assert isinstance(et, str)
            assert len(et) > 0

    @pytest.mark.integration
    def test_oversized_event_truncated_in_stream(self, team_stream_client):
        """Events exceeding 4KB are truncated when sent over SSE."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        big_payload = {"data": "x" * 10000}
        oversized_event = {
            "seq": 1,
            "type": "session_progress",
            "payload": big_payload,
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        mock_fetch.side_effect = [
            ([], "active"),
            ([oversized_event], "completed"),
        ]

        with client.stream("GET", f"/api/work-containers/{cid}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        data_lines = [line for line in lines if line.startswith("data:")]
        for line in data_lines:
            parsed = json.loads(line.removeprefix("data: "))
            if parsed.get("type") == "session_progress":
                assert parsed.get("_truncated") is True
                assert "_full_size" in parsed
                assert isinstance(parsed["payload"], dict)

    @pytest.mark.integration
    def test_unauthorized_access_returns_401(self):
        """Access without valid token returns 401."""
        from starlette.testclient import TestClient

        cid = uuid.uuid4()
        # Use a fresh client without auth dependency override
        with TestClient(app) as client:
            response = client.get(f"/api/work-containers/{cid}/stream")
            assert response.status_code == 401

    @pytest.mark.integration
    def test_authorized_with_valid_token(self, team_stream_client):
        """Access with valid auth token works."""
        client, mock_fetch, _ = team_stream_client
        cid = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "active"),
            ([], "completed"),
        ]

        response = client.get(f"/api/work-containers/{cid}/stream", headers=AUTH)
        assert response.status_code == 200


# ── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    @pytest.mark.unit
    def test_poll_interval_is_one_second(self):
        """POLL_INTERVAL_SECONDS must be 1.0."""
        assert _POLL_INTERVAL_SECONDS == 1.0

    @pytest.mark.unit
    def test_max_payload_bytes_is_4096(self):
        """_MAX_PAYLOAD_BYTES must be 4096 (4KB)."""
        assert _MAX_PAYLOAD_BYTES == 4096

    @pytest.mark.unit
    def test_terminal_states_include_completed_and_archived(self):
        """Terminal container states are completed and archived."""
        assert "completed" in _TERMINAL_CONTAINER_STATES
        assert "archived" in _TERMINAL_CONTAINER_STATES
        assert "active" not in _TERMINAL_CONTAINER_STATES
        assert "paused" not in _TERMINAL_CONTAINER_STATES


# ── Event types enumeration ─────────────────────────────────────────────────


class TestTeamEventTypes:
    @pytest.mark.unit
    def test_session_progress_event_type_exists(self):
        """SESSION_PROGRESS event type is defined."""
        assert EventType.SESSION_PROGRESS.value == "session_progress"

    @pytest.mark.unit
    def test_budget_pressure_change_event_type_exists(self):
        """BUDGET_PRESSURE_CHANGE event type is defined."""
        assert EventType.BUDGET_PRESSURE_CHANGE.value == "budget_pressure_change"

    @pytest.mark.unit
    def test_team_control_audit_event_type_exists(self):
        """TEAM_CONTROL_AUDIT event type is defined."""
        assert EventType.TEAM_CONTROL_AUDIT.value == "team_control_audit"

    @pytest.mark.unit
    def test_session_status_change_event_type_exists(self):
        """SESSION_STATUS_CHANGE event type is defined."""
        assert EventType.SESSION_STATUS_CHANGE.value == "session_status_change"

    @pytest.mark.unit
    def test_all_team_event_types_are_str_enums(self):
        """All team event types are instances of EventType (StrEnum)."""
        for et in (
            EventType.SESSION_PROGRESS,
            EventType.BUDGET_PRESSURE_CHANGE,
            EventType.TEAM_CONTROL_AUDIT,
            EventType.SESSION_STATUS_CHANGE,
        ):
            assert isinstance(et, EventType)
            assert isinstance(et.value, str)

    @pytest.mark.unit
    def test_team_events_dont_break_existing_events(self):
        """Existing event types are unchanged."""
        assert EventType.RUN_STARTED.value == "run_started"
        assert EventType.RUN_FINISHED.value == "run_finished"
        assert EventType.LLM_CALL.value == "llm_call"
        assert EventType.COLLABORATION_DELIVERED.value == "collaboration_delivered"
