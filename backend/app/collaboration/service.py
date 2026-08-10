"""Recipient-scoped inbox loading and delivery state transitions."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.enums import MessageDeliveryState
from app.core.models import (
    ExecutionEvent,
    SessionMessage,
    TeamAuditEvent,
    WorkSession,
    utcnow,
)

MAX_INBOX_MESSAGES = 20

# --- Anti-runaway defaults ---
DEFAULT_MAX_TEAM_MESSAGES_PER_MINUTE = 30
DEFAULT_MAX_AUTO_REPLY_ROUNDS = 5
DEFAULT_INBOX_TOKEN_RATIO = 0.05

# Valid message state transitions (PostgreSQL-enforced).
ALLOWED_MESSAGE_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    MessageDeliveryState.QUEUED.value: frozenset({MessageDeliveryState.INJECTED.value}),
    MessageDeliveryState.INJECTED.value: frozenset(
        {MessageDeliveryState.ACKNOWLEDGED.value, MessageDeliveryState.FAILED.value}
    ),
    MessageDeliveryState.ACKNOWLEDGED.value: frozenset(),
    MessageDeliveryState.FAILED.value: frozenset(),
    MessageDeliveryState.DELIVERED.value: frozenset(),  # legacy alias
}

TERMINAL_SESSION_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def queued_messages_for_run(
    session: Session, run_id: uuid.UUID, *, limit: int = MAX_INBOX_MESSAGES
) -> list[SessionMessage]:
    """Return pending messages for the work session that owns ``run_id``.

    Injected messages remain eligible for bounded re-injection after a failed
    run, so switching or retrying an execution engine cannot silently lose a
    judge request before a real acknowledgement is recorded.
    """
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
                SessionMessage.delivery_state.in_(
                    [
                        MessageDeliveryState.QUEUED.value,
                        MessageDeliveryState.INJECTED.value,
                    ]
                ),
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


MAX_INJECTION_ATTEMPTS = 3


def mark_messages_injected(messages: Sequence[SessionMessage]) -> None:
    """Transition queued messages → injected (CLI safety-checkpoint injection).

    Only messages in ``queued`` state are transitioned; already-injected or
    acknowledged messages are left untouched.  Each injection increments
    ``injection_count``.  Messages that have already been injected
    ``MAX_INJECTION_ATTEMPTS`` times without acknowledgment are atomically
    transitioned to ``failed``.

    The caller is responsible for committing the session.
    """
    now = utcnow()
    for message in messages:
        if message.delivery_state == MessageDeliveryState.QUEUED.value:
            message.delivery_state = MessageDeliveryState.INJECTED.value
            message.delivered_at = now
            message.injection_count = 1
        elif message.delivery_state == MessageDeliveryState.INJECTED.value:
            # Already injected — this is a re-injection attempt.
            if message.injection_count >= MAX_INJECTION_ATTEMPTS:
                message.delivery_state = MessageDeliveryState.FAILED.value
            else:
                message.injection_count += 1


def mark_messages_acknowledged(
    messages: Sequence[SessionMessage],
    acknowledged_ids: set[str],
) -> int:
    """Transition injected messages → acknowledged when the agent confirms receipt.

    Only messages whose ``id`` appears in ``acknowledged_ids`` and are
    currently in ``injected`` state are transitioned.  Returns the count of
    messages that were actually acknowledged.
    """
    now = utcnow()
    count = 0
    for message in messages:
        if (
            str(message.id) in acknowledged_ids
            and message.delivery_state == MessageDeliveryState.INJECTED.value
        ):
            message.delivery_state = MessageDeliveryState.ACKNOWLEDGED.value
            message.acknowledged_at = now
            count += 1
    return count


def mark_messages_failed(
    session: Session,
    container_id: uuid.UUID,
) -> int:
    """Atomically UPDATE delivery_state='failed' for messages that have been
    injected ``MAX_INJECTION_ATTEMPTS`` or more times without acknowledgment.

    Only messages currently in ``injected`` state are considered.  Returns the
    number of messages that were transitioned.

    The caller is responsible for committing the session.
    """
    stmt = (
        update(SessionMessage)
        .where(
            SessionMessage.container_id == container_id,
            SessionMessage.delivery_state == MessageDeliveryState.INJECTED.value,
            SessionMessage.injection_count >= MAX_INJECTION_ATTEMPTS,
        )
        .values(delivery_state=MessageDeliveryState.FAILED.value)
    )
    result = session.execute(stmt)
    return result.rowcount


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


# ---------------------------------------------------------------------------
# Message state machine: atomic transitions inside PostgreSQL
# ---------------------------------------------------------------------------


def transition_message_state(
    session: Session,
    message_id: uuid.UUID,
    new_state: str,
    *,
    expected_states: frozenset[str] | None = None,
) -> SessionMessage | None:
    """Atomically transition a message to *new_state* only if it is in one of
    *expected_states*.  Uses a single UPDATE … WHERE … RETURNING to avoid
    races, then refreshes the ORM object in the same transaction.

    Returns the updated ``SessionMessage`` on success, or ``None`` if no row
    matched.
    """
    if expected_states is None:
        valid_from = ALLOWED_MESSAGE_STATE_TRANSITIONS
        expected_states = frozenset(
            old for old, targets in valid_from.items() if new_state in targets
        )

    stmt = (
        update(SessionMessage)
        .where(
            SessionMessage.id == message_id,
            SessionMessage.delivery_state.in_(list(expected_states)),
        )
        .values(
            delivery_state=new_state,
            acknowledged_at=utcnow() if new_state == MessageDeliveryState.ACKNOWLEDGED.value else None,
        )
        .returning(SessionMessage)
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is not None:
        session.expire(row)
        session.refresh(row)
    return row


def acknowledge_message(
    session: Session,
    message_id: uuid.UUID,
    acknowledging_session_id: uuid.UUID,
) -> SessionMessage | None:
    """Atomically transition to 'acknowledged' only if currently 'injected'
    AND the message belongs to the acknowledging session."""
    stmt = (
        update(SessionMessage)
        .where(
            SessionMessage.id == message_id,
            SessionMessage.delivery_state == MessageDeliveryState.INJECTED.value,
            SessionMessage.recipient_session_id == acknowledging_session_id,
        )
        .values(
            delivery_state=MessageDeliveryState.ACKNOWLEDGED.value,
            acknowledged_at=utcnow(),
        )
        .returning(SessionMessage)
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is not None:
        session.expire(row)
        session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Anti-runaway: hard limits enforced at the control plane
# ---------------------------------------------------------------------------

_REDIS_CLIENT = None


def _get_redis():
    """Lazy-import Redis client so tests / dev without Redis don't crash."""
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        try:
            import redis as redis_lib

            from app.core.config import settings

            _REDIS_CLIENT = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            _REDIS_CLIENT = False  # type: ignore[assignment]
    return _REDIS_CLIENT if _REDIS_CLIENT is not False else None


def _check_rate_limit(
    container_id: uuid.UUID,
    max_per_minute: int = DEFAULT_MAX_TEAM_MESSAGES_PER_MINUTE,
) -> bool:
    """Return True if the container is still under the per-minute message cap.

    Uses a Valkey/Redis string key with a 60-second TTL as a sliding-window
    counter.  If the key does not exist it is created with value 1; otherwise
    it is incremented and the result compared against *max_per_minute*.
    """
    redis = _get_redis()
    if redis is False:
        return True  # Redis unavailable → allow (best-effort)
    if redis is None:
        return True

    key = f"budgetloop:rate_limit:container_msgs:{container_id}"
    try:
        current = redis.incr(key)
        if current == 1:
            redis.expire(key, 60)
        return current <= max_per_minute
    except Exception:
        return True  # Redis transient error → allow


def _write_audit_event(
    session: Session,
    container_id: uuid.UUID,
    action: str,
    *,
    session_id: uuid.UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    operator: str = "system",
) -> None:
    """Persist an audit event in the same DB transaction."""
    session.add(
        TeamAuditEvent(
            container_id=container_id,
            session_id=session_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            operator=operator,
        )
    )


def _emit_notification_event(
    session: Session,
    container_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
    *,
    run_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> None:
    """Emit an execution_event with *container_id* set for the team SSE stream."""
    effective_run_id = run_id
    if effective_run_id is None and session_id is not None:
        result = session.execute(
            select(WorkSession.current_run_id).where(WorkSession.id == session_id)
        ).scalar_one_or_none()
        if result is not None:
            effective_run_id = result

    session.add(
        ExecutionEvent(
            run_id=effective_run_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            container_id=container_id,
            type=event_type,
            payload=payload or {},
        )
    )


def validate_message_sender(
    session: Session,
    container_id: uuid.UUID,
    sender_session_id: uuid.UUID | None,
    recipient_session_id: uuid.UUID,
) -> None:
    """Raise ``ValueError`` if sender validation fails.

    Checks:
    - Self-send rejection
    - Cross-container rejection
    - Delivery to terminated sessions
    """
    if sender_session_id is not None and sender_session_id == recipient_session_id:
        raise ValueError("cannot-send-to-self")

    # Verify both sender and recipient belong to the same container.
    if sender_session_id is not None:
        sender = session.get(WorkSession, sender_session_id)
        if sender is None or str(sender.container_id) != str(container_id):
            raise ValueError("cross-container-delivery-forbidden")

    recipient = session.get(WorkSession, recipient_session_id)
    if recipient is None or str(recipient.container_id) != str(container_id):
        raise ValueError("cross-container-delivery-forbidden")

    if recipient.status in TERMINAL_SESSION_STATUSES:
        raise ValueError("recipient-session-terminal")


def validate_anti_runaway(
    session: Session,
    container_id: uuid.UUID,
    recipient_session_id: uuid.UUID,
    sender_session_id: uuid.UUID | None,
) -> None:
    """Check anti-runaway hard limits; raise ``ValueError`` on breach.

    1. Rate limit: max messages per minute (Valkey TTL key).
    2. Auto-reply round limit per trigger chain (per-session counter,
       stored as a simple key in Redis for now).
    3. Inbox Token cap at 5 % of recipient's max_total_tokens.
    4. Anti-broadcast: each message must have exactly one recipient (caller
       guarantees this by construction).

    On limit breach: write audit event + notification event inside the
    caller's transaction (caller must commit).
    """
    # 1. Rate limit
    if not _check_rate_limit(container_id):
        _write_audit_event(
            session,
            container_id,
            "anti-runaway-rate-limit-hit",
            session_id=recipient_session_id,
            new_value={"threshold": DEFAULT_MAX_TEAM_MESSAGES_PER_MINUTE},
        )
        _emit_notification_event(
            session,
            container_id,
            "budget_pressure_change",
            {"reason": "anti-runaway-rate-limit-hit", "container_id": str(container_id)},
            session_id=recipient_session_id,
        )
        raise ValueError("rate-limit-exceeded")

    # 2. Auto-reply round limit (only applies when sender is a session)
    if sender_session_id is not None:
        redis = _get_redis()
        if redis and redis is not False:
            round_key = f"budgetloop:auto_reply_rounds:{recipient_session_id}"
            try:
                rounds = redis.incr(round_key)
                if rounds == 1:
                    redis.expire(round_key, 86400)  # daily reset
                if rounds > DEFAULT_MAX_AUTO_REPLY_ROUNDS:
                    _write_audit_event(
                        session,
                        container_id,
                        "anti-runaway-round-limit-hit",
                        session_id=recipient_session_id,
                        new_value={"threshold": DEFAULT_MAX_AUTO_REPLY_ROUNDS},
                    )
                    _emit_notification_event(
                        session,
                        container_id,
                        "budget_pressure_change",
                        {
                            "reason": "anti-runaway-round-limit-hit",
                            "session_id": str(recipient_session_id),
                            "container_id": str(container_id),
                        },
                        session_id=recipient_session_id,
                    )
                    raise ValueError("auto-reply-round-limit-exceeded")
            except Exception:
                pass  # Redis transient → allow

    # 3. Inbox Token cap
    try:
        from app.core.models import TaskBudget, TaskRun

        run = session.execute(
            select(TaskRun).where(
                TaskRun.id == select(WorkSession.current_run_id).where(
                    WorkSession.id == recipient_session_id
                ).scalar_subquery()
            )
        ).scalar_one_or_none()
        if run is not None:
            budget = session.get(TaskBudget, run.id)
            if budget is not None:
                token_cap = int(budget.max_total_tokens * DEFAULT_INBOX_TOKEN_RATIO)
                # Count queued + injected message tokens for this recipient.
                # We estimate token count by content length / 4.
                inbox_messages = list(
                    session.execute(
                        select(SessionMessage).where(
                            SessionMessage.recipient_session_id == recipient_session_id,
                            SessionMessage.delivery_state.in_(
                                [
                                    MessageDeliveryState.QUEUED.value,
                                    MessageDeliveryState.INJECTED.value,
                                ]
                            ),
                        )
                    ).scalars()
                )
                inbox_tokens = sum(
                    (len(msg.content) // 4 if msg.content else 0) for msg in inbox_messages
                )
                if inbox_tokens > token_cap:
                    _write_audit_event(
                        session,
                        container_id,
                        "anti-runaway-inbox-token-cap-hit",
                        session_id=recipient_session_id,
                        new_value={
                            "inbox_tokens": inbox_tokens,
                            "token_cap": token_cap,
                        },
                    )
                    _emit_notification_event(
                        session,
                        container_id,
                        "budget_pressure_change",
                        {
                            "reason": "anti-runaway-inbox-token-cap-hit",
                            "session_id": str(recipient_session_id),
                            "container_id": str(container_id),
                        },
                        session_id=recipient_session_id,
                    )
                    raise ValueError("inbox-token-cap-exceeded")
    except ValueError:
        raise
    except Exception:
        pass  # Budget query unavailable → best-effort allow


# Allowed handoff content fields
ALLOWED_HANDOFF_FIELDS: frozenset[str] = frozenset(
    {"conclusion", "evidence", "open_questions", "next_step"}
)

FORBIDDEN_HANDOFF_FIELDS: frozenset[str] = frozenset(
    {"hidden_reasoning", "private_context", "credentials", "api_keys"}
)


def validate_handoff_content(content: str) -> str:
    """Validate and sanitize handoff content JSON.

    Enforces the following constraints:
    - Content must be valid JSON (object).
    - Fields in *FORBIDDEN_HANDOFF_FIELDS* are rejected with a specific error code.
    - At least one field in *ALLOWED_HANDOFF_FIELDS* must be present.
    - Extra unknown fields are silently stripped (only allowed fields are kept).

    Returns the sanitized JSON string.

    Raises ``ValueError`` with a structured error code when validation fails.
    """
    import json

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("handoff-content-invalid: content must be valid JSON")

    if not isinstance(data, dict):
        raise ValueError("handoff-content-invalid: content must be a JSON object")

    # Reject forbidden fields
    for field in FORBIDDEN_HANDOFF_FIELDS:
        if field in data:
            raise ValueError(f"handoff-content-invalid: forbidden field '{field}' is not allowed")

    # Check at least one allowed field is present
    present_allowed = [k for k in ALLOWED_HANDOFF_FIELDS if k in data]
    if not present_allowed:
        raise ValueError(
            "handoff-content-invalid: must contain at least one of: "
            + ", ".join(sorted(ALLOWED_HANDOFF_FIELDS))
        )

    # Strip unknown fields — keep only allowed fields
    cleaned = {k: v for k, v in data.items() if k in ALLOWED_HANDOFF_FIELDS}

    return json.dumps(cleaned, ensure_ascii=False)


def create_message_with_validation(
    session: Session,
    container_id: uuid.UUID,
    recipient_session_id: uuid.UUID,
    content: str,
    *,
    sender_session_id: uuid.UUID | None = None,
    kind: str = "message",
    message_type: str = "message",
    idempotency_key: str | None = None,
    metadata: dict | None = None,
    author_type: str = "operator",
) -> tuple[SessionMessage, bool]:
    """Create a SessionMessage with full validation and anti-runaway checks.

    Returns ``(message, created)`` where *created* is ``False`` when an
    idempotency-key match was found.

    All checks run inside the caller's transaction (caller must commit).
    """
    # 1. Idempotency
    if idempotency_key:
        existing = session.execute(
            select(SessionMessage)
            .options(
                selectinload(SessionMessage.sender_session),
                selectinload(SessionMessage.recipient_session),
            )
            .where(
                SessionMessage.container_id == container_id,
                SessionMessage.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

    # 2. Sender validation
    validate_message_sender(
        session, container_id, sender_session_id, recipient_session_id
    )

    # 3. Anti-runaway
    validate_anti_runaway(
        session, container_id, recipient_session_id, sender_session_id
    )

    # 4. Create
    message = SessionMessage(
        container_id=container_id,
        sender_session_id=sender_session_id,
        recipient_session_id=recipient_session_id,
        author_type=author_type,
        kind=kind,
        message_type=message_type,
        content=content,
        delivery_state=MessageDeliveryState.QUEUED.value,
        idempotency_key=idempotency_key,
        message_metadata=metadata or {},
    )
    session.add(message)
    session.flush()
    return message, True
