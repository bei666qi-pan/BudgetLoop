"""Tests for the SSE stream endpoint (app/api/stream.py).

Covers _fetch unit tests and stream_run integration tests.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from app.api.stream import _POLL_INTERVAL_SECONDS, _fetch  # noqa: E402
from app.core.enums import EventType, RunStatus  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"Authorization": f"Bearer {settings.api_token}"}


# ── POLL_INTERVAL constant ──────────────────────────────────────────────────


class TestPollInterval:
    def test_poll_interval_is_one_second(self):
        """POLL_INTERVAL_SECONDS must be exactly 1.0."""
        assert _POLL_INTERVAL_SECONDS == 1.0

    def test_poll_interval_is_positive_float(self):
        """Sanity: value is a positive float."""
        assert isinstance(_POLL_INTERVAL_SECONDS, float)
        assert _POLL_INTERVAL_SECONDS > 0


# ── Unit tests for _fetch ───────────────────────────────────────────────────


class TestFetch:
    """Unit tests for the synchronous _fetch helper."""

    @pytest.mark.unit
    def test_fetch_valid_run_returns_events_and_status(self):
        """_fetch with a valid run_id returns an events list and the run status."""
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.status = "PENDING"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_run

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events", return_value=[]) as mock_list, \
             patch("app.api.stream.event_to_dict", side_effect=lambda e: {"seq": e.seq, "type": e.type}):
            events, status = _fetch(run_id, 0)

        assert events == []
        assert status == "PENDING"
        mock_session.get.assert_called_once()
        mock_session.close.assert_called_once()
        mock_list.assert_called_once_with(mock_session, run_id, 0)

    @pytest.mark.unit
    def test_fetch_nonexistent_run_returns_empty_list_none_status(self):
        """_fetch with a non-existent run_id returns [] and status=None."""
        run_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.get.return_value = None

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events", return_value=[]):
            events, status = _fetch(run_id, 0)

        assert events == []
        assert status is None
        mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_fetch_with_after_seq_passed_to_list_events(self):
        """_fetch forwards after_seq to list_events for filtering."""
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.status = "EXECUTING"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_run

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events") as mock_list, \
             patch("app.api.stream.event_to_dict", side_effect=lambda e: {"seq": e.seq, "type": e.type}):
            _fetch(run_id, 42)

        mock_list.assert_called_once_with(mock_session, run_id, 42)

    @pytest.mark.unit
    def test_fetch_session_closed_when_get_raises(self):
        """Session is closed even when session.get() raises an exception."""
        run_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.get.side_effect = RuntimeError("db connection lost")

        with patch("app.api.stream.SessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError, match="db connection lost"):
                _fetch(run_id, 0)

        mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_fetch_session_closed_when_list_events_raises(self):
        """Session is closed even when list_events raises an exception."""
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.status = "EXECUTING"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_run

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events", side_effect=ValueError("query failed")):
            with pytest.raises(ValueError, match="query failed"):
                _fetch(run_id, 0)

        mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_fetch_multiple_events_converted_and_returned(self):
        """_fetch converts all ExecutionEvent rows via event_to_dict."""
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.status = "EXECUTING"

        seq_calls = []

        def fake_event_to_dict(e):
            seq_calls.append(e.seq)
            return {"seq": e.seq, "type": e.type}

        mock_events = [MagicMock(seq=1, type="run_started"),
                       MagicMock(seq=2, type="state_changed"),
                       MagicMock(seq=3, type="llm_call")]
        mock_session = MagicMock()
        mock_session.get.return_value = mock_run

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events", return_value=mock_events), \
             patch("app.api.stream.event_to_dict", side_effect=fake_event_to_dict):
            events, status = _fetch(run_id, 0)

        assert len(events) == 3
        assert [e["seq"] for e in events] == [1, 2, 3]
        assert [e["type"] for e in events] == ["run_started", "state_changed", "llm_call"]
        assert status == "EXECUTING"
        # Each event was passed through event_to_dict exactly once, in order
        assert seq_calls == [1, 2, 3]

    @pytest.mark.unit
    def test_fetch_with_uuid_run_id_passed_through(self):
        """_fetch forwards the UUID run_id to list_events without mutation."""
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.status = "PENDING"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_run

        with patch("app.api.stream.SessionLocal", return_value=mock_session), \
             patch("app.api.stream.list_events", return_value=[]) as mock_list:
            _fetch(run_id, 0)

        # list_events should receive the exact same UUID object
        call_args = mock_list.call_args[0]
        assert call_args[0] is mock_session
        assert call_args[1] == run_id
        assert call_args[2] == 0


# ── Integration tests for stream_run endpoint ───────────────────────────────


@pytest.fixture()
def stream_client():
    """TestClient with auth bypassed for the stream endpoint.

    Returns a tuple of (client, mock_fetch).  mock_fetch is a callable you can
    configure with .return_value or .side_effect before making the request.
    """
    from app.core.security import require_token
    mock_fetch = MagicMock(return_value=([], "PENDING"))

    app.dependency_overrides[require_token] = lambda: None
    with patch("app.api.stream._fetch", mock_fetch), \
         patch("app.api.stream.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        from starlette.testclient import TestClient
        with TestClient(app) as client:
            yield client, mock_fetch, mock_sleep
    app.dependency_overrides.clear()


class TestStreamRunEndpoint:
    """Integration tests for the GET /api/runs/{run_id}/stream endpoint."""

    @pytest.mark.integration
    def test_valid_run_returns_sse_content_type(self, stream_client):
        """A valid run returns 200 with text/event-stream content type."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "PENDING"),      # initial check
            ([], "COMPLETED"),    # first poll → terminal
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.integration
    def test_nonexistent_run_returns_404(self, stream_client):
        """A non-existent run returns 404."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        mock_fetch.return_value = ([], None)  # run not found

        response = client.get(f"/api/runs/{run_id}/stream", headers=AUTH)
        assert response.status_code == 404

    @pytest.mark.integration
    def test_event_generator_yields_sse_format(self, stream_client):
        """Events are yielded with proper id, event, and data SSE fields."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        event_data = {"seq": 1, "type": "run_started", "payload": {}, "created_at": "2025-01-01T00:00:00+00:00"}
        mock_fetch.side_effect = [
            ([], "PENDING"),                       # initial check
            ([event_data], "EXECUTING"),           # first poll → has event
            ([], "COMPLETED"),                     # second poll → terminal
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        # Should have at least the event data line
        data_lines = [line for line in lines if line.startswith("data:")]
        event_lines = [line for line in lines if line.startswith("event:")]
        id_lines = [line for line in lines if line.startswith("id:")]

        assert len(data_lines) >= 1
        assert len(event_lines) >= 1
        assert len(id_lines) >= 1

        # Verify the first event content
        parsed = json.loads(data_lines[0].removeprefix("data: "))
        assert parsed["seq"] == 1
        assert parsed["type"] == "run_started"

    @pytest.mark.integration
    def test_event_generator_stops_at_terminal_with_run_finished_event(self, stream_client):
        """When the run reaches a terminal status and a RUN_FINISHED event is
        present in the event stream, the generator stops after yielding it."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        run_finished_event = {
            "seq": 1,
            "type": "run_finished",
            "payload": {"status": "COMPLETED"},
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        mock_fetch.side_effect = [
            ([], "PENDING"),
            ([run_finished_event], "COMPLETED"),
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        # Should contain exactly one run_finished (no synthetic duplicate)
        run_finished_count = sum(1 for line in event_lines if "run_finished" in line)
        assert run_finished_count == 1

    @pytest.mark.integration
    def test_synthetic_run_finished_when_terminal_but_no_finish_event(self, stream_client):
        """When the run is terminal but no RUN_FINISHED event exists in the
        stream, the generator emits a synthetic one and then returns."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        started_event = {
            "seq": 1,
            "type": "run_started",
            "payload": {},
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        # Run is COMPLETED but the only event is run_started (no run_finished)
        mock_fetch.side_effect = [
            ([], "PENDING"),
            ([started_event], "COMPLETED"),
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        assert any("run_finished" in line for line in event_lines)

        # Verify the synthetic event's data contains the run status
        data_lines = [line for line in lines if line.startswith("data:")]
        synthetic_data = [
            json.loads(line.removeprefix("data: "))
            for line in data_lines
            if "run_finished" in line
        ]
        assert len(synthetic_data) >= 1
        # The synthetic event carries the terminal status in its payload
        found = False
        for d in synthetic_data:
            if d.get("payload", {}).get("status") == "COMPLETED":
                found = True
                break
        assert found, f"Synthetic run_finished should contain status=COMPLETED, got {synthetic_data}"

    @pytest.mark.integration
    def test_event_generator_handles_client_disconnect(self, stream_client):
        """The generator exits gracefully when request.is_disconnected() is True."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        # The generator checks is_disconnected at the top of each loop.
        # We need to make the request object report it as disconnected.
        # We do this by mocking Request.is_disconnected.
        # Since stream_run receives request as a parameter, we patch the
        # starlette Request.is_disconnected at a low level.

        with patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock) as mock_disc:
            # First call: not disconnected yet, returns initial data
            # Second call (in the generator loop): disconnected
            mock_disc.side_effect = [False, True]

            mock_fetch.side_effect = [
                ([], "PENDING"),        # initial check
                ([], "EXECUTING"),      # poll returns non-terminal
            ]

            with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
                lines = list(response.iter_lines())

        # Since is_disconnected returned True on the second call, the generator
        # should return without emitting the terminal synthetic event.
        # The stream may be empty or have minimal content.
        event_lines = [line for line in lines if line.startswith("event:")]
        assert len(event_lines) == 0  # No events emitted after disconnect

    @pytest.mark.integration
    def test_last_event_id_header_sets_after_seq(self, stream_client):
        """The last-event-id header is parsed and used as after_seq for
        reconnection support."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "PENDING"),        # initial check (after_seq=0, ignored for header test)
            ([], "COMPLETED"),      # first poll
        ]

        headers = {**AUTH, "last-event-id": "42"}

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=headers) as response:
            list(response.iter_lines())

        # Verify _fetch was called with after_seq=42 during the polling loop
        # The second call (first poll in generator) should use last_seq=42
        calls = mock_fetch.call_args_list
        # call 0: initial check (_fetch(run_id, 0))
        # call 1: first poll (_fetch(run_id, 42))
        assert len(calls) >= 2
        assert calls[1][0][1] == 42  # after_seq arg

    @pytest.mark.integration
    def test_last_event_id_non_digit_ignored(self, stream_client):
        """Non-digit last-event-id values are ignored and after_seq stays 0."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        mock_fetch.side_effect = [
            ([], "PENDING"),
            ([], "COMPLETED"),
        ]

        headers = {**AUTH, "last-event-id": "not-a-number"}

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=headers) as response:
            list(response.iter_lines())

        # The second call should use after_seq=0 (non-digit ignored)
        calls = mock_fetch.call_args_list
        assert len(calls) >= 2
        assert calls[1][0][1] == 0

    @pytest.mark.integration
    def test_multiple_events_in_one_poll(self, stream_client):
        """When multiple events are returned in a single poll cycle,
        each one is yielded as an individual SSE message."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        event1 = {"seq": 1, "type": "run_started", "payload": {}, "created_at": "..."}
        event2 = {"seq": 2, "type": "state_changed", "payload": {}, "created_at": "..."}
        event3 = {"seq": 3, "type": "phase_changed", "payload": {}, "created_at": "..."}
        finish = {"seq": 4, "type": "run_finished", "payload": {"status": "COMPLETED"}, "created_at": "..."}

        mock_fetch.side_effect = [
            ([], "PENDING"),
            ([event1, event2, event3, finish], "COMPLETED"),
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            lines = list(response.iter_lines())

        event_lines = [line for line in lines if line.startswith("event:")]
        event_types = [line.removeprefix("event: ").strip() for line in event_lines]
        assert event_types == ["run_started", "state_changed", "phase_changed", "run_finished"]

    @pytest.mark.integration
    def test_run_finished_event_stops_stream_immediately(self, stream_client):
        """When a RUN_FINISHED event appears in the stream, the generator
        stops after yielding it, without polling again."""
        client, mock_fetch, _ = stream_client
        run_id = uuid.uuid4()

        finish_event = {
            "seq": 1,
            "type": "run_finished",
            "payload": {"status": "COMPLETED"},
            "created_at": "...",
        }
        mock_fetch.side_effect = [
            ([], "PENDING"),
            ([finish_event], "COMPLETED"),
            # If there's a third call, the test should still pass
            # (polling should not happen after run_finished)
        ]

        with client.stream("GET", f"/api/runs/{run_id}/stream", headers=AUTH) as response:
            list(response.iter_lines())

        # _fetch should only be called twice: initial check + one poll
        assert mock_fetch.call_count == 2
