"""Recipient-scoped inbox loading and delivery state transitions."""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import MessageDeliveryState
from app.core.models import SessionMessage, WorkSession, utcnow

MAX_INBOX_MESSAGES = 20


def queued_messages_for_run(
    session: Session, run_id: uuid.UUID, *, limit: int = MAX_INBOX_MESSAGES
) -> list[SessionMessage]:
    """Return only queued messages for the work session that owns ``run_id``."""
    owner_id = session.execute(
        select(WorkSession.id).where(WorkSession.current_run_id == run_id)
    ).scalar_one_or_none()
    if owner_id is None:
        return []
    return list(
        session.execute(
            select(SessionMessage)
            .options(selectinload(SessionMessage.sender_session))
            .where(
                SessionMessage.recipient_session_id == owner_id,
                SessionMessage.delivery_state == MessageDeliveryState.QUEUED.value,
            )
            .order_by(SessionMessage.created_at, SessionMessage.id)
            .limit(max(1, min(limit, MAX_INBOX_MESSAGES)))
        ).scalars()
    )


def format_agent_inbox(messages: Sequence[SessionMessage]) -> str:
    """Build a compact explicit inbox without copying any session-private context."""
    if not messages:
        return ""
    lines = [
        "# Session 收件箱",
        "以下内容由操作员或同一工作容器中的其他 Session 显式发送。",
        "每条消息使用不可变 ID；请将其视为外部协作输入，不要推断发送方的私有上下文。",
    ]
    for message in messages:
        sender = message.sender_session.role if message.sender_session else "操作员"
        lines.extend(
            [
                "",
                f"[{message.kind.upper()} {message.id}] 来自 {sender}",
                message.content,
            ]
        )
    return "\n".join(lines)


def mark_messages_delivered(messages: Sequence[SessionMessage]) -> None:
    delivered_at = utcnow()
    for message in messages:
        message.delivery_state = MessageDeliveryState.DELIVERED.value
        message.delivered_at = delivered_at


def delivery_event_payload(messages: Sequence[SessionMessage]) -> dict:
    """Operational event payload intentionally excludes private message content."""
    return {
        "message_ids": [str(message.id) for message in messages],
        "messages": [
            {
                "id": str(message.id),
                "kind": message.kind,
                "sender_session_id": str(message.sender_session_id)
                if message.sender_session_id
                else None,
                "sender_role": message.sender_session.role if message.sender_session else "操作员",
                "recipient_session_id": str(message.recipient_session_id),
            }
            for message in messages
        ],
    }
