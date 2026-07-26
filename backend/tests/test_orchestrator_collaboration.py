from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.worker.orchestrator import Orchestrator

pytestmark = pytest.mark.unit


def _message():
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind="handoff",
        content="explicit content",
        sender_session=SimpleNamespace(role="架构设计"),
        sender_session_id=uuid.uuid4(),
        recipient_session_id=uuid.uuid4(),
        delivery_state="queued",
        delivered_at=None,
    )


def test_failed_agent_send_leaves_inbox_queued():
    session = MagicMock()
    client = MagicMock()
    client.send_message.side_effect = RuntimeError("agent unavailable")
    emit = MagicMock()
    orchestrator = Orchestrator(
        session,
        uuid.uuid4(),
        client=client,
        emit_event=emit,
    )
    message = _message()

    with pytest.raises(RuntimeError, match="agent unavailable"):
        orchestrator._send_iteration_message(SimpleNamespace(), "instruction", [message])

    assert message.delivery_state == "queued"
    emit.assert_not_called()
    session.commit.assert_not_called()


def test_failed_server_run_leaves_inbox_queued():
    session = MagicMock()
    client = MagicMock()
    client.transport = "server"
    client.run_conversation.side_effect = RuntimeError("run unavailable")
    emit = MagicMock()
    orchestrator = Orchestrator(
        session,
        uuid.uuid4(),
        client=client,
        emit_event=emit,
    )
    message = _message()

    with pytest.raises(RuntimeError, match="run unavailable"):
        orchestrator._send_iteration_message(SimpleNamespace(), "instruction", [message])

    client.send_message.assert_called_once_with("instruction", run=False)
    client.run_conversation.assert_called_once_with()
    assert message.delivery_state == "queued"
    emit.assert_not_called()
    session.commit.assert_not_called()


def test_successful_server_send_and_run_marks_delivered():
    session = MagicMock()
    client = MagicMock()
    client.transport = "server"
    emit = MagicMock()
    run_id = uuid.uuid4()
    orchestrator = Orchestrator(session, run_id, client=client, emit_event=emit)
    message = _message()

    orchestrator._send_iteration_message(SimpleNamespace(), "instruction", [message])

    assert message.delivery_state == "delivered"
    client.send_message.assert_called_once_with("instruction", run=False)
    client.run_conversation.assert_called_once_with()
    session.commit.assert_called_once()
    payload = emit.call_args.args[3]
    assert payload["message_ids"] == [str(message.id)]
    assert "content" not in payload["messages"][0]


def test_cli_send_executes_directly_without_separate_run():
    session = MagicMock()
    client = MagicMock()
    client.transport = "cli"
    orchestrator = Orchestrator(session, uuid.uuid4(), client=client)

    orchestrator._send_iteration_message(SimpleNamespace(), "instruction", [])

    client.send_message.assert_called_once_with("instruction", run=True)
    client.run_conversation.assert_not_called()
