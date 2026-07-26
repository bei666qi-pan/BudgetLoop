from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.collaboration.service import format_agent_inbox, mark_messages_delivered

pytestmark = pytest.mark.unit


def _message(content: str = "请实现接口"):
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        kind="handoff",
        content=content,
        sender_session=SimpleNamespace(role="架构设计"),
        sender_session_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        recipient_session_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        delivery_state="queued",
        delivered_at=None,
    )


def test_format_agent_inbox_is_deterministic_and_id_labelled():
    message = _message()
    text = format_agent_inbox([message])
    assert "HANDOFF 11111111-1111-1111-1111-111111111111" in text
    assert "来自 架构设计" in text
    assert "请实现接口" in text
    assert "私有上下文" in text


def test_mark_delivered_changes_state_only_after_explicit_call():
    message = _message()
    assert message.delivery_state == "queued"
    mark_messages_delivered([message])
    assert message.delivery_state == "delivered"
    assert message.delivered_at is not None
