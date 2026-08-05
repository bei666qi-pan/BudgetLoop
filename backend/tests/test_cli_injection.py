"""CLI safety-checkpoint injection: injection timing, state transitions,
progress signal extraction, and message injection into CLI prompt templates."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from app.collaboration.service import (
    mark_messages_acknowledged,
    mark_messages_injected,
)
from app.core.enums import MessageDeliveryState
from app.execution_engines.adapters import (
    ExtractedProgressSignal,
    InjectionPoint,
    NormalizedEngineEvent,
    adapter_for,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# check_injection_point — iteration boundary detection
# ---------------------------------------------------------------------------


def test_check_injection_point_empty_events_is_start():
    """No events yet → engine is ready to start a fresh iteration."""
    adapter = adapter_for("codex")
    assert adapter.check_injection_point([]) == InjectionPoint.ITERATION_START


def test_check_injection_point_terminal_event_is_end():
    """A terminal event (turn.completed) signals iteration end."""
    adapter = adapter_for("codex")
    events = [
        NormalizedEngineEvent(
            "turn.completed", None, None, {}, terminal=True
        ),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.ITERATION_END


def test_check_injection_point_start_followed_by_output_is_none():
    """Events in the middle of an active iteration → no boundary."""
    adapter = adapter_for("codex")
    events = [
        NormalizedEngineEvent(
            "thread.started", None, None, {"thread_id": "t1"}
        ),
        NormalizedEngineEvent(
            "message", "doing work", None, {}
        ),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.NONE


def test_check_injection_point_start_only_is_start():
    """Only a start event → still at iteration start."""
    adapter = adapter_for("codex")
    events = [
        NormalizedEngineEvent(
            "thread.started", None, None, {"thread_id": "t1"}
        ),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.ITERATION_START


def test_check_injection_point_gemini_terminal():
    """Gemini CLI 'result' event is terminal."""
    adapter = adapter_for("gemini-cli")
    events = [
        NormalizedEngineEvent("result", None, None, {}, terminal=True),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.ITERATION_END


def test_check_injection_point_gemini_init_is_start():
    """Gemini CLI 'init' event is a start signal."""
    adapter = adapter_for("gemini-cli")
    events = [
        NormalizedEngineEvent("init", None, None, {"session_id": "s1"}),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.ITERATION_START


def test_check_injection_point_opencode_step_finish_is_end():
    """OpenCode 'step_finish' event signals iteration end."""
    adapter = adapter_for("opencode")
    events = [
        NormalizedEngineEvent(
            "step_finish", None, None, {}, terminal=True
        ),
    ]
    assert adapter.check_injection_point(events) == InjectionPoint.ITERATION_END


# ---------------------------------------------------------------------------
# mark_messages_injected — queued → injected transition
# ---------------------------------------------------------------------------


def _message(state: str = "queued", msg_id: str | None = None):
    mid = msg_id or str(uuid.uuid4())
    return SimpleNamespace(
        id=uuid.UUID(mid) if "-" in mid else uuid.uuid4(),
        kind="message",
        content="注入测试消息",
        sender_session=SimpleNamespace(role="操作员"),
        sender_session_id=None,
        recipient_session_id=uuid.uuid4(),
        delivery_state=state,
        delivered_at=None,
        acknowledged_at=None,
    )


def test_mark_messages_injected_transitions_queued_only():
    """Only queued messages transition to injected; others stay unchanged."""
    q1 = _message("queued")
    q2 = _message("queued")
    already_acked = _message("acknowledged")

    mark_messages_injected([q1, q2, already_acked])

    assert q1.delivery_state == MessageDeliveryState.INJECTED.value
    assert q1.delivered_at is not None
    assert q2.delivery_state == MessageDeliveryState.INJECTED.value
    assert q2.delivered_at is not None
    # Already acknowledged must not be changed
    assert already_acked.delivery_state == MessageDeliveryState.ACKNOWLEDGED.value
    assert already_acked.acknowledged_at is None  # was pre-set


def test_mark_messages_injected_empty_list_no_error():
    """Empty list should be a no-op."""
    mark_messages_injected([])


# ---------------------------------------------------------------------------
# No premature acknowledged — acknowledged only via agent confirmation
# ---------------------------------------------------------------------------


def test_mark_messages_injected_does_not_acknowledge():
    """Injected messages stay injected; acknowledged is only set later."""
    msg = _message("queued")
    mark_messages_injected([msg])
    assert msg.delivery_state == MessageDeliveryState.INJECTED.value
    assert getattr(msg, "acknowledged_at", None) is None


def test_mark_messages_acknowledged_only_transitions_injected():
    """Only injected messages with matching IDs transition to acknowledged."""
    mid1 = "11111111-1111-1111-1111-111111111111"
    mid2 = "22222222-2222-2222-2222-222222222222"
    queued = _message("queued", mid1)
    injected = _message("injected", mid2)

    count = mark_messages_acknowledged([queued, injected], {mid1, mid2})

    # Queued message (not injected yet) must NOT be acknowledged
    assert queued.delivery_state == MessageDeliveryState.QUEUED.value
    assert getattr(queued, "acknowledged_at", None) is None
    # Injected message with matching ID transitions to acknowledged
    assert injected.delivery_state == MessageDeliveryState.ACKNOWLEDGED.value
    assert injected.acknowledged_at is not None
    assert count == 1


def test_mark_messages_acknowledged_unknown_ids_noop():
    """Acknowledging IDs not in the message list is a no-op."""
    msg = _message("injected", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    count = mark_messages_acknowledged([msg], {"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"})
    assert msg.delivery_state == MessageDeliveryState.INJECTED.value
    assert count == 0


# ---------------------------------------------------------------------------
# extract_progress_signal — structured progress parsing
# ---------------------------------------------------------------------------


def test_extract_progress_signal_json_block():
    """Agent output containing [PROGRESS] JSON block → full signal."""
    adapter = adapter_for("codex")
    text = (
        "完成了一些工作。\n"
        '[PROGRESS] {"summary": "实现了API路由", "milestone": "后端实现完成", '
        '"completed_items": ["数据模型", "迁移", "API路由"], '
        '"next_step": "编写测试", "blocked": false, "needs_operator": false, '
        '"evidence": "backend/app/api/routes.py L42"}'
    )
    signal = adapter.extract_progress_signal(text)
    assert signal is not None
    assert signal.summary == "实现了API路由"
    assert signal.milestone == "后端实现完成"
    assert signal.completed_items == ["数据模型", "迁移", "API路由"]
    assert signal.next_step == "编写测试"
    assert signal.blocked is False
    assert signal.needs_operator is False
    assert signal.evidence == "backend/app/api/routes.py L42"


def test_extract_progress_signal_json_block_blocked():
    """Agent declares blocked state with a reason."""
    adapter = adapter_for("codex")
    text = (
        '[PROGRESS] {"summary": "卡在API cors配置", "blocked": true, '
        '"blocker_reason": "等待运维配置CORS白名单", "needs_operator": true}'
    )
    signal = adapter.extract_progress_signal(text)
    assert signal is not None
    assert signal.blocked is True
    assert signal.blocker_reason == "等待运维配置CORS白名单"
    assert signal.needs_operator is True


def test_extract_progress_signal_inline_kv():
    """Agent output with PROGRESS:key value pairs → parsed signal."""
    adapter = adapter_for("codex")
    text = (
        "PROGRESS:summary 前端页面已完成\n"
        "PROGRESS:milestone 前端开发完成\n"
        "PROGRESS:completed_items 登录页, 仪表盘, 设置页\n"
        "PROGRESS:next_step 对接后端API\n"
        "PROGRESS:blocked false\n"
    )
    signal = adapter.extract_progress_signal(text)
    assert signal is not None
    assert signal.summary == "前端页面已完成"
    assert signal.milestone == "前端开发完成"
    assert signal.completed_items == ["登录页", "仪表盘", "设置页"]
    assert signal.next_step == "对接后端API"
    assert signal.blocked is False


def test_extract_progress_signal_raw_json_object():
    """Raw JSON object with progress keys → parsed signal."""
    adapter = adapter_for("codex")
    text = (
        '{"summary": "测试覆盖到85%", "milestone": "测试编写", '
        '"completed_items": ["单元测试", "集成测试"], "blocked": false, '
        '"needs_operator": false}'
    )
    signal = adapter.extract_progress_signal(text)
    assert signal is not None
    assert signal.summary == "测试覆盖到85%"
    assert signal.milestone == "测试编写"
    assert signal.completed_items == ["单元测试", "集成测试"]


def test_extract_progress_signal_no_signal():
    """Plain text without any progress signal returns None."""
    adapter = adapter_for("codex")
    assert adapter.extract_progress_signal("只是一段普通文本。") is None
    assert adapter.extract_progress_signal("") is None
    assert adapter.extract_progress_signal(None) is None


def test_extract_progress_signal_empty_json_block():
    """Empty [PROGRESS] {} block → signal with defaults."""
    adapter = adapter_for("codex")
    text = "[PROGRESS] {}"
    signal = adapter.extract_progress_signal(text)
    assert signal is not None
    assert signal.summary is None
    assert signal.blocked is False
    assert signal.needs_operator is False
    assert signal.completed_items == []


def test_extract_progress_signal_malformed_json():
    """Malformed JSON after [PROGRESS] is handled gracefully."""
    adapter = adapter_for("codex")
    text = "[PROGRESS] {not valid json!!!}"
    signal = adapter.extract_progress_signal(text)
    assert signal is None


# ---------------------------------------------------------------------------
# detect_message_acknowledgement
# ---------------------------------------------------------------------------


def test_detect_ack_from_send_message_tool_input():
    """Agent confirms via tool_input.acknowledging_message_id."""
    adapter = adapter_for("codex")
    mid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    events = [
        NormalizedEngineEvent(
            "tool",
            None,
            "send_message",
            {},
            tool_input={"acknowledging_message_id": mid},
        ),
    ]
    acked = adapter.detect_message_acknowledgement(events)
    assert mid in acked


def test_detect_ack_from_public_text():
    """Agent mentions acknowledged_message_id in public text."""
    adapter = adapter_for("codex")
    mid = "11111111-2222-3333-4444-555555555555"
    text = f"已确认收到消息 acknowledged_message_id: {mid}"
    events = [
        NormalizedEngineEvent("message", text, None, {}),
    ]
    acked = adapter.detect_message_acknowledgement(events)
    assert mid in acked


def test_detect_ack_from_raw_payload():
    """Raw event payload carries acknowledged_message_id."""
    adapter = adapter_for("codex")
    mid = "deadbeef-dead-beef-dead-beefdeadbeef"
    events = [
        NormalizedEngineEvent(
            "custom",
            None,
            None,
            {"acknowledged_message_id": mid},
        ),
    ]
    acked = adapter.detect_message_acknowledgement(events)
    assert mid in acked


def test_detect_ack_list_form():
    """Agent acknowledges multiple messages in a list."""
    adapter = adapter_for("codex")
    mid1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mid2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    events = [
        NormalizedEngineEvent(
            "tool",
            None,
            "send_message",
            {},
            tool_input={"acknowledged_messages": [mid1, mid2]},
        ),
    ]
    acked = adapter.detect_message_acknowledgement(events)
    assert mid1 in acked
    assert mid2 in acked


def test_detect_ack_no_acknowledgement_returns_empty():
    """Events without any acknowledgement data return empty set."""
    adapter = adapter_for("codex")
    events = [
        NormalizedEngineEvent("message", "just some text", None, {}),
        NormalizedEngineEvent("tool", None, "execute_bash", {}, tool_input={"command": "ls"}),
    ]
    acked = adapter.detect_message_acknowledgement(events)
    assert acked == set()


# ---------------------------------------------------------------------------
# Message injection into CLI prompt template
# ---------------------------------------------------------------------------


def test_injected_messages_appear_in_instruction():
    """When messages are injected, they appear in the formatted inbox as
    part of the instruction text sent to the CLI engine."""
    from app.collaboration.service import format_agent_inbox

    msg = _message("injected", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    msg.kind = "message"
    msg.content = "请优先修复登录页面的bug"
    msg.sender_session = SimpleNamespace(role="测试工程师")

    instruction_base = "分析并修复代码问题。"
    inbox = format_agent_inbox([msg])

    full_instruction = f"{instruction_base}\n\n{inbox}"
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in full_instruction
    assert "请优先修复登录页面的bug" in full_instruction
    assert "测试工程师" in full_instruction
    assert "Session 收件箱" in full_instruction


def test_injected_messages_not_marked_delivered():
    """CLI-injected messages use 'injected' state, NOT 'delivered' (server only)."""
    msg = _message("queued", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # Simulate CLI injection path
    mark_messages_injected([msg])
    assert msg.delivery_state == MessageDeliveryState.INJECTED.value
    assert msg.delivery_state != MessageDeliveryState.DELIVERED.value

    # Acknowledge only after agent confirmation
    mark_messages_acknowledged([msg], {"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})
    assert msg.delivery_state == MessageDeliveryState.ACKNOWLEDGED.value
    assert msg.acknowledged_at is not None


def test_injected_messages_preserved_across_state_transitions():
    """Full lifecycle: queued → injected → acknowledged without premature delivery."""
    msg = _message("queued", "cccccccc-cccc-cccc-cccc-cccccccccccc")

    # Step 1: queued state
    assert msg.delivery_state == MessageDeliveryState.QUEUED.value

    # Step 2: injected (CLI safety checkpoint)
    mark_messages_injected([msg])
    assert msg.delivery_state == MessageDeliveryState.INJECTED.value
    assert getattr(msg, "acknowledged_at", None) is None  # NOT acknowledged yet

    # Step 3: acknowledged (agent confirms)
    count = mark_messages_acknowledged([msg], {"cccccccc-cccc-cccc-cccc-cccccccccccc"})
    assert count == 1
    assert msg.delivery_state == MessageDeliveryState.ACKNOWLEDGED.value
    assert msg.acknowledged_at is not None


# ---------------------------------------------------------------------------
# ExtractedProgressSignal serialization
# ---------------------------------------------------------------------------


def test_extracted_progress_signal_to_dict():
    """to_dict() serializes all fields correctly."""
    signal = ExtractedProgressSignal(
        summary="完成数据库迁移",
        milestone="后端实现",
        completed_items=["schema.sql", "migrations/"],
        next_step="实现API路由",
        blocked=False,
        blocker_reason=None,
        needs_operator=False,
        evidence="models.py L45",
    )
    d = signal.to_dict()
    assert d["summary"] == "完成数据库迁移"
    assert d["milestone"] == "后端实现"
    assert d["completed_items"] == ["schema.sql", "migrations/"]
    assert d["next_step"] == "实现API路由"
    assert d["blocked"] is False
    assert d["blocker_reason"] is None
    assert d["needs_operator"] is False
    assert d["evidence"] == "models.py L45"


def test_progress_signal_defaults():
    """Default signal has sane empty values."""
    signal = ExtractedProgressSignal()
    assert signal.summary is None
    assert signal.milestone is None
    assert signal.completed_items == []
    assert signal.blocked is False
    assert signal.needs_operator is False


# ---------------------------------------------------------------------------
# InjectionPoint enum values
# ---------------------------------------------------------------------------


def test_injection_point_values():
    """InjectionPoint enum has the expected three states."""
    assert InjectionPoint.NONE.value == "none"
    assert InjectionPoint.ITERATION_START.value == "iteration_start"
    assert InjectionPoint.ITERATION_END.value == "iteration_end"
    assert len(InjectionPoint) == 3
