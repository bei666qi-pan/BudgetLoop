"""Unit tests for app.worker.openhands_client — AgentServerClient HTTP client for OpenHands agent-server.

Covers: AgentServerError, IDLE_STATUSES, __init__, context manager, _backoff,
_conversation_path, _request, create_conversation, send_message, run/pause,
get_conversation, search_events, execute_bash, git_diff, upload_file,
wait_until_idle, EVENTS_PAGE_LIMIT.
"""
from __future__ import annotations

import uuid
from unittest.mock import ANY, MagicMock, patch

import httpx
import pytest

from app.worker.openhands_client import (
    DEFAULT_CODING_TOOLS,
    EVENTS_PAGE_LIMIT,
    IDLE_STATUSES,
    AgentServerClient,
    AgentServerError,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_client(base_url="http://example.com", session_key="test-key", **kwargs):
    return AgentServerClient(base_url, session_key, **kwargs)


def make_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# ---------------------------------------------------------------------------
# AgentServerError
# ---------------------------------------------------------------------------


def test_agent_server_error_basic():
    err = AgentServerError("something went wrong")
    assert str(err) == "something went wrong"
    assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# IDLE_STATUSES
# ---------------------------------------------------------------------------


def test_idle_statuses_membership():
    expected = {"idle", "finished", "paused", "error", "stuck", "waiting_for_confirmation"}
    assert IDLE_STATUSES == frozenset(expected)
    for s in expected:
        assert s in IDLE_STATUSES


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_normalizes_url():
    client = AgentServerClient("http://example.com/", "key")
    assert client.base_url == "http://example.com"

    client2 = AgentServerClient("http://example.com", "key")
    assert client2.base_url == "http://example.com"


def test_init_defaults():
    client = make_client()
    assert client.max_retries == 3
    assert client.backoff_base == 0.5
    assert client.conversation_id is None
    assert client._client.headers.get("X-Session-API-Key") == "test-key"


def test_init_custom_params():
    client = AgentServerClient(
        "http://example.com", "key",
        timeout=30.0, max_retries=5, backoff_base=1.0,
    )
    assert client.max_retries == 5
    assert client.backoff_base == 1.0
    assert client.conversation_id is None


# ---------------------------------------------------------------------------
# context manager / close
# ---------------------------------------------------------------------------


def test_context_manager_and_close():
    client = make_client()
    with patch.object(client._client, "close") as mock_close:
        # __enter__
        assert client.__enter__() is client

        # __exit__
        client.__exit__(None, None, None)
        mock_close.assert_called_once()

    # close
    client2 = make_client()
    with patch.object(client2._client, "close") as mock_close2:
        client2.close()
        mock_close2.assert_called_once()


# ---------------------------------------------------------------------------
# _backoff
# ---------------------------------------------------------------------------


def test_backoff_attempt_0():
    client = make_client()
    with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
        client._backoff(0)
        mock_sleep.assert_called_once_with(0.5)  # 0.5 * 2^0


def test_backoff_attempt_1():
    client = make_client()
    with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
        client._backoff(1)
        mock_sleep.assert_called_once_with(1.0)  # 0.5 * 2^1


def test_backoff_attempt_2():
    client = make_client()
    with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
        client._backoff(2)
        mock_sleep.assert_called_once_with(2.0)  # 0.5 * 2^2


def test_backoff_at_max_retries():
    client = make_client(max_retries=3)
    with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
        client._backoff(3)  # attempt == max_retries → no sleep
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# _conversation_path
# ---------------------------------------------------------------------------


def test_conversation_path_with_stored_id():
    client = make_client()
    client.conversation_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    path = client._conversation_path()
    assert path == "/api/conversations/12345678-1234-5678-1234-567812345678"


def test_conversation_path_with_explicit_id():
    client = make_client()
    cid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    path = client._conversation_path(cid)
    assert path == "/api/conversations/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_conversation_path_no_id_raises():
    client = make_client()
    with pytest.raises(AgentServerError, match="conversation_id not set"):
        client._conversation_path()


# ---------------------------------------------------------------------------
# _request
# ---------------------------------------------------------------------------


def test_request_success_first_attempt():
    client = make_client()
    resp = make_response(200, {"ok": True})
    with patch.object(client._client, "request", return_value=resp) as mock_req:
        result = client._request("GET", "/test")
        assert result.status_code == 200
        assert result.json() == {"ok": True}
        mock_req.assert_called_once_with("GET", "/test")


def test_request_retry_on_429_then_success():
    client = make_client()
    resp_429 = make_response(429, {})
    resp_200 = make_response(200, {"ok": True})
    mock = MagicMock(side_effect=[resp_429, resp_200])
    with patch.object(client._client, "request", mock):
        with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
            result = client._request("GET", "/test")
            assert result.status_code == 200
            assert mock.call_count == 2
            mock_sleep.assert_called_once()


def test_request_retry_on_5xx_then_success():
    client = make_client()
    resp_500 = make_response(500, {})
    resp_200 = make_response(200, {"ok": True})
    mock = MagicMock(side_effect=[resp_500, resp_200])
    with patch.object(client._client, "request", mock):
        with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
            result = client._request("GET", "/test")
            assert result.status_code == 200
            assert mock.call_count == 2
            mock_sleep.assert_called_once()


def test_request_retry_on_transport_error():
    client = make_client()
    resp_200 = make_response(200, {"ok": True})
    mock = MagicMock(side_effect=[httpx.TransportError("conn failed"), resp_200])
    with patch.object(client._client, "request", mock):
        with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
            result = client._request("GET", "/test")
            assert result.status_code == 200
            assert mock.call_count == 2
            mock_sleep.assert_called_once()


def test_request_4xx_raises_immediately():
    client = make_client()
    resp_400 = make_response(400, {"error": "bad request"})
    with patch.object(client._client, "request", return_value=resp_400) as mock_req:
        with pytest.raises(AgentServerError, match="400"):
            client._request("GET", "/test")
        mock_req.assert_called_once()  # no retry


def test_request_max_retries_exhausted():
    client = make_client(max_retries=2)
    resp_500 = make_response(500, {})
    mock = MagicMock(return_value=resp_500)
    with patch.object(client._client, "request", mock):
        with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
            with pytest.raises(AgentServerError, match="failed after 3 attempts"):
                client._request("GET", "/test")
            assert mock.call_count == 3  # 2 retries + initial = 3
            assert mock_sleep.call_count == 2  # sleeps on attempt 0, 1; skipped on 2


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------


def test_create_conversation_minimal():
    client = make_client()
    resp = make_response(200, {"id": "22222222-2222-2222-2222-222222222222"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        info = client.create_conversation(
            model="gpt-4",
            llm_base_url="https://api.openai.com",
            llm_api_key="sk-test",
            working_dir="/workspace",
        )
        assert info == {"id": "22222222-2222-2222-2222-222222222222"}
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        body = kwargs["json"]
        assert body["agent"]["llm"]["model"] == "gpt-4"
        assert body["agent"]["llm"]["base_url"] == "https://api.openai.com"
        assert body["agent"]["llm"]["api_key"] == "sk-test"
        assert body["workspace"]["working_dir"] == "/workspace"
        assert body["max_iterations"] == 500
        assert "initial_message" not in body
        assert "conversation_id" not in body


def test_create_conversation_with_initial_message():
    client = make_client()
    resp = make_response(200, {"id": "33333333-3333-3333-3333-333333333333"})
    with patch.object(client, "_request", return_value=resp):
        info = client.create_conversation(
            model="gpt-4",
            llm_base_url="https://api.openai.com",
            llm_api_key="sk-test",
            working_dir="/workspace",
            initial_message="Hello, fix the bug",
        )
        assert info["id"] == "33333333-3333-3333-3333-333333333333"

        # verify body via the mock
        call_args = client._request.call_args  # type: ignore[attr-defined]
        body = call_args[1]["json"]
        assert body["initial_message"]["role"] == "user"
        assert body["initial_message"]["content"][0]["text"] == "Hello, fix the bug"
        assert body["initial_message"]["run"] is False


def test_create_conversation_with_extra_llm():
    client = make_client()
    resp = make_response(200, {"id": "44444444-4444-4444-4444-444444444444"})
    with patch.object(client, "_request", return_value=resp):
        client.create_conversation(
            model="gpt-4",
            llm_base_url="https://api.openai.com",
            llm_api_key="sk-test",
            working_dir="/workspace",
            extra_llm={"temperature": 0.2, "top_p": 0.9},
        )
        body = client._request.call_args[1]["json"]  # type: ignore[attr-defined]
        assert body["agent"]["llm"]["temperature"] == 0.2
        assert body["agent"]["llm"]["top_p"] == 0.9


def test_create_conversation_sets_conversation_id():
    client = make_client()
    conv_id = "55555555-5555-5555-5555-555555555555"
    resp = make_response(200, {"id": conv_id})
    with patch.object(client, "_request", return_value=resp):
        client.create_conversation(
            model="gpt-4",
            llm_base_url="https://api.openai.com",
            llm_api_key="sk-test",
            working_dir="/workspace",
        )
        assert client.conversation_id == uuid.UUID(conv_id)


def test_create_conversation_body_structure():
    client = make_client()
    conv_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    resp = make_response(200, {"id": "66666666-6666-6666-6666-666666666666"})
    with patch.object(client, "_request", return_value=resp):
        client.create_conversation(
            model="claude-3",
            llm_base_url="https://api.anthropic.com",
            llm_api_key="sk-ant-test",
            working_dir="/tmp/ws",
            conversation_id=conv_id,
            max_iterations=100,
            usage_id="test-usage",
        )
        args, kwargs = client._request.call_args  # type: ignore[attr-defined]
        assert args[0] == "POST"
        assert args[1] == "/api/conversations"
        body = kwargs["json"]
        assert body["agent"]["kind"] == "Agent"
        assert body["agent"]["llm"]["model"] == "claude-3"
        assert body["agent"]["llm"]["usage_id"] == "test-usage"
        assert body["agent"]["tools"] == list(DEFAULT_CODING_TOOLS)
        assert [tool["name"] for tool in body["agent"]["tools"]] == [
            "terminal",
            "file_editor",
            "task_tracker",
        ]
        assert body["workspace"]["kind"] == "LocalWorkspace"
        assert body["max_iterations"] == 100
        assert body["conversation_id"] == str(conv_id)


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


def test_send_message_default():
    client = make_client()
    client.conversation_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    resp = make_response(200, {"status": "ok"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.send_message("do something")
        assert result == {"status": "ok"}
        mock_req.assert_called_once()
        body = mock_req.call_args[1]["json"]
        assert body["role"] == "user"
        assert body["content"][0]["text"] == "do something"
        assert body["run"] is True


def test_send_message_run_false():
    client = make_client()
    client.conversation_id = uuid.UUID("88888888-8888-8888-8888-888888888888")
    resp = make_response(200, {"status": "ok"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        client.send_message("just a note", run=False)
        body = mock_req.call_args[1]["json"]
        assert body["run"] is False


def test_send_message_explicit_conversation_id():
    client = make_client()
    cid = uuid.UUID("99999999-9999-9999-9999-999999999999")
    resp = make_response(200, {"status": "ok"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        client.send_message("hello", conversation_id=cid)
        call_path = mock_req.call_args[0][1]
        assert str(cid) in call_path


# ---------------------------------------------------------------------------
# run_conversation / pause
# ---------------------------------------------------------------------------


def test_run_conversation():
    client = make_client()
    client.conversation_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    resp = make_response(200, {"status": "running"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.run_conversation()
        assert result == {"status": "running"}
        args = mock_req.call_args[0]
        assert args[0] == "POST"
        assert "/run" in args[1]


def test_run_conversation_accepts_already_running_conflict():
    client = make_client()
    client.conversation_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaab")
    resp = make_response(409, {"detail": "Conversation already running."})
    with patch.object(client._client, "request", return_value=resp):
        result = client.run_conversation()

    assert result == {"detail": "Conversation already running."}


def test_other_request_still_rejects_conflict():
    client = make_client()
    resp = make_response(409, {"detail": "conflict"})
    with patch.object(client._client, "request", return_value=resp):
        with pytest.raises(AgentServerError, match="409"):
            client._request("POST", "/other")


def test_pause():
    client = make_client()
    client.conversation_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    resp = make_response(200, {"status": "paused"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.pause()
        assert result == {"status": "paused"}
        args = mock_req.call_args[0]
        assert args[0] == "POST"
        assert "/pause" in args[1]


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------


def test_get_conversation():
    client = make_client()
    client.conversation_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    resp = make_response(200, {"id": "cccccccc-cccc-cccc-cccc-cccccccccccc", "execution_status": "finished"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        info = client.get_conversation()
        assert info["execution_status"] == "finished"
        args = mock_req.call_args[0]
        assert args[0] == "GET"
        assert str(client.conversation_id) in args[1]


# ---------------------------------------------------------------------------
# search_events
# ---------------------------------------------------------------------------


def test_search_events_single_page():
    client = make_client()
    client.conversation_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    items = [{"id": "evt-1"}, {"id": "evt-2"}]
    resp = make_response(200, {"items": items, "next_page_id": None})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.search_events()
        assert result == items
        mock_req.assert_called_once()
        params = mock_req.call_args[1]["params"]
        assert params["limit"] == EVENTS_PAGE_LIMIT
        assert params["sort_order"] == "TIMESTAMP"


def test_search_events_pagination():
    client = make_client()
    client.conversation_id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    page1 = make_response(200, {"items": [{"id": "evt-1"}], "next_page_id": "p2"})
    page2 = make_response(200, {"items": [{"id": "evt-2"}], "next_page_id": None})
    mock = MagicMock(side_effect=[page1, page2])
    with patch.object(client, "_request", mock):
        result = client.search_events()
        assert len(result) == 2
        assert result[0]["id"] == "evt-1"
        assert result[1]["id"] == "evt-2"
        assert mock.call_count == 2


def test_search_events_after_id_found():
    client = make_client()
    client.conversation_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    items = [
        {"id": "evt-1"},
        {"id": "evt-2"},
        {"id": "evt-3"},
    ]
    resp = make_response(200, {"items": items, "next_page_id": None})
    with patch.object(client, "_request", return_value=resp):
        result = client.search_events(after_id="evt-1")
        assert len(result) == 2
        assert result[0]["id"] == "evt-2"
        assert result[1]["id"] == "evt-3"


def test_search_events_after_id_not_found():
    client = make_client()
    client.conversation_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    items = [{"id": "evt-1"}, {"id": "evt-2"}]
    resp = make_response(200, {"items": items, "next_page_id": None})
    with patch.object(client, "_request", return_value=resp):
        result = client.search_events(after_id="evt-nonexistent")
        assert result == items  # returns all items


def test_search_events_with_filters():
    client = make_client()
    client.conversation_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    resp = make_response(200, {"items": [], "next_page_id": None})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        client.search_events(kind="change", source="agent")
        params = mock_req.call_args[1]["params"]
        assert params["kind"] == "change"
        assert params["source"] == "agent"


def test_search_events_empty():
    client = make_client()
    client.conversation_id = uuid.UUID("11111111-2222-3333-4444-666666666666")
    resp = make_response(200, {"items": [], "next_page_id": None})
    with patch.object(client, "_request", return_value=resp):
        result = client.search_events()
        assert result == []


# ---------------------------------------------------------------------------
# execute_bash
# ---------------------------------------------------------------------------


def test_execute_bash_basic():
    client = make_client()
    resp = make_response(200, {"exit_code": 0, "stdout": "hello\n", "stderr": ""})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.execute_bash("echo hello")
        assert result["exit_code"] == 0
        body = mock_req.call_args[1]["json"]
        assert body["command"] == "echo hello"
        assert body["timeout"] == 300
        assert "cwd" not in body


def test_execute_bash_with_cwd():
    client = make_client()
    resp = make_response(200, {"exit_code": 0})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        client.execute_bash("ls", cwd="/tmp")
        body = mock_req.call_args[1]["json"]
        assert body["cwd"] == "/tmp"


# ---------------------------------------------------------------------------
# git_diff
# ---------------------------------------------------------------------------


def test_git_diff():
    client = make_client()
    resp = make_response(200, {"modified": "new content", "original": "old content"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.git_diff("/workspace/main.py")
        assert result["modified"] == "new content"
        assert result["original"] == "old content"
        args = mock_req.call_args[0]
        assert args[0] == "GET"
        assert "/api/git/diff//workspace/main.py" in args[1]


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


def test_upload_file():
    client = make_client()
    resp = make_response(200, {"status": "ok"})
    with patch.object(client, "_request", return_value=resp) as mock_req:
        result = client.upload_file("/workspace/test.py", b"print(1)")
        assert result == {"status": "ok"}
        args = mock_req.call_args[0]
        assert args[0] == "POST"
        assert "/api/file/upload//workspace/test.py" in args[1]
        assert mock_req.call_args[1]["files"] == {"file": b"print(1)"}


# ---------------------------------------------------------------------------
# wait_until_idle
# ---------------------------------------------------------------------------


def test_wait_until_idle_immediately():
    client = make_client()
    client.conversation_id = uuid.UUID("11223344-5566-7788-9900-aabbccddeeff")
    info = {"execution_status": "idle", "stats": {}}
    with patch.object(client, "get_conversation", return_value=info) as mock_get:
        with patch("app.worker.openhands_client.time.monotonic", return_value=0.0):
            result = client.wait_until_idle()
            assert result["execution_status"] == "idle"
            mock_get.assert_called_once()


def test_wait_until_idle_after_polling():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-aabbccddeeff")
    running_info = {"execution_status": "running"}
    idle_info = {"execution_status": "finished", "stats": {"iterations": 5}}
    mock_get = MagicMock(side_effect=[running_info, idle_info])

    # monotonic called: once for deadline, then once per loop iteration
    monotonic_values = [0.0, 10.0, 20.0]  # all < 300.0 deadline

    with patch.object(client, "get_conversation", mock_get):
        with patch("app.worker.openhands_client.time.monotonic") as mock_mono:
            with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
                mock_mono.side_effect = monotonic_values
                result = client.wait_until_idle()
                assert result["execution_status"] == "finished"
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once_with(2.0)


def test_wait_until_idle_ignores_pre_start_idle():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-bbccddeeff00")
    mock_get = MagicMock(
        side_effect=[
            {"execution_status": "idle", "stats": {}},
            {"execution_status": "running", "stats": {}},
            {"execution_status": "idle", "stats": {"iterations": 1}},
        ]
    )

    with patch.object(client, "get_conversation", mock_get):
        with patch("app.worker.openhands_client.time.monotonic") as mock_mono:
            with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
                mock_mono.side_effect = [0.0, 0.0, 1.0, 2.0]
                result = client.wait_until_idle(require_execution_start=True)

    assert result["execution_status"] == "idle"
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


def test_wait_until_idle_ignores_stale_finished_before_running():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-ccddee001122")
    mock_get = MagicMock(
        side_effect=[
            {"execution_status": "finished", "stats": {}},
            {"execution_status": "running", "stats": {}},
            {"execution_status": "finished", "stats": {}},
        ]
    )

    with (
        patch.object(client, "get_conversation", mock_get),
        patch(
            "app.worker.openhands_client.time.monotonic",
            side_effect=[0.0, 0.0, 1.0, 2.0],
        ),
        patch("app.worker.openhands_client.time.sleep") as mock_sleep,
    ):
        result = client.wait_until_idle(require_execution_start=True)

    assert result["execution_status"] == "finished"
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


def test_wait_until_idle_accepts_instant_unambiguous_terminal():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-cdffee001122")

    with (
        patch.object(
            client,
            "get_conversation",
            return_value={"execution_status": "error", "stats": {}},
        ),
        patch("app.worker.openhands_client.time.monotonic", side_effect=[0.0, 0.0]),
    ):
        result = client.wait_until_idle(require_execution_start=True)

    assert result["execution_status"] == "error"


def test_wait_until_idle_accepts_usage_backed_idle_completion():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-ddee00112233")
    info = {
        "execution_status": "idle",
        "stats": {
            "usage_to_metrics": {
                "agent": {"token_usages": [{"prompt_tokens": 10, "completion_tokens": 2}]}
            }
        },
    }

    with patch.object(client, "get_conversation", return_value=info):
        with patch("app.worker.openhands_client.time.monotonic", side_effect=[0.0, 0.0]):
            result = client.wait_until_idle(require_execution_start=True)

    assert result is info


def test_wait_until_idle_rejects_latency_and_cost_without_token_usage():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-deee00112233")
    info = {
        "execution_status": "finished",
        "stats": {
            "usage_to_metrics": {
                "agent": {"token_usages": [], "costs": [0.0], "response_latencies": [0.01]}
            }
        },
    }

    with (
        patch.object(client, "get_conversation", return_value=info) as mock_get,
        patch(
            "app.worker.openhands_client.time.monotonic",
            side_effect=[0.0, 0.0, 16.0],
        ),
        patch("app.worker.openhands_client.time.sleep") as mock_sleep,
    ):
        with pytest.raises(AgentServerError, match="did not start"):
            client.wait_until_idle(
                require_execution_start=True,
                start_timeout_seconds=15.0,
            )

    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


def test_wait_until_idle_fails_when_execution_never_starts():
    client = make_client()
    client.conversation_id = uuid.UUID("22334455-6677-8899-0011-ee0011223344")
    idle_info = {"execution_status": "idle", "stats": {}}

    with patch.object(client, "get_conversation", return_value=idle_info) as mock_get:
        with patch("app.worker.openhands_client.time.monotonic") as mock_mono:
            with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
                mock_mono.side_effect = [0.0, 0.0, 16.0]
                with pytest.raises(AgentServerError, match="did not start"):
                    client.wait_until_idle(
                        require_execution_start=True,
                        start_timeout_seconds=15.0,
                    )

    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


def test_wait_until_idle_timeout():
    client = make_client()
    client.conversation_id = uuid.UUID("33445566-7788-9900-1122-aabbccddeeff")
    running_info = {"execution_status": "running"}
    mock_get = MagicMock(return_value=running_info)

    # monotonic called: once for deadline, then once per loop iteration
    # 0 (deadline calc), 0 (loop 1, < 300), 301 (loop 2, > 300 → break → raise)
    monotonic_values = [0.0, 0.0, 301.0]

    with patch.object(client, "get_conversation", mock_get):
        with patch("app.worker.openhands_client.time.monotonic") as mock_mono:
            with patch("app.worker.openhands_client.time.sleep") as mock_sleep:
                mock_mono.side_effect = monotonic_values
                with pytest.raises(AgentServerError, match="still running"):
                    client.wait_until_idle(timeout_seconds=300.0)
                assert mock_get.call_count >= 1
                mock_sleep.assert_called_once_with(2.0)


# ---------------------------------------------------------------------------
# EVENTS_PAGE_LIMIT
# ---------------------------------------------------------------------------


def test_events_page_limit():
    assert EVENTS_PAGE_LIMIT == 100
    assert isinstance(EVENTS_PAGE_LIMIT, int)
