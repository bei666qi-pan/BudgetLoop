"""Agent coordination protocol — behavior constraints for container-owned sessions.

The protocol is injected into the agent's iteration instruction as a brief
addendum.  It does NOT grant tool access, permissions, or cross-session
context; it only constrains what the agent should do within its existing
boundaries.
"""

from __future__ import annotations

from app.core.enums import PressureMode

# ---------------------------------------------------------------------------
# Coordination protocol prompt fragment (Chinese, injected into system prompt)
# ---------------------------------------------------------------------------

COORDINATION_PROTOCOL_PROMPT = (
    "# Agent 协调协议\n"
    "你是 Agent Team 中的一个角色。请严格遵守以下协作规则"
    "（本协议仅约束行为，不授予任何额外权限或上下文）：\n\n"
    "## 目标边界\n"
    "- 只完成你被分配的角色目标，不要越界执行其他 Session 的职责。\n"
    "- 不要在消息中请求或推断其他 Session 的私有上下文"
    "（private_context、凭据、推理过程）。\n\n"
    "## 协作消息\n"
    "- 仅在必要时发送简短的协作消息，且**必须指定明确的接收方**（不要广播）。\n"
    "- 消息应包含可验证的事实，不含推测或冗余描述。\n"
    "- 禁止发送存活报告（心跳、\"仍在工作中\"、\"继续推进\"等）。\n"
    "- 收到消息后应在下一轮迭代中确认；"
    "若发送消息后**一轮未收到确认，立即升级给协调者/操作员**，不要反复重试。\n\n"
    "## 进度声明\n"
    "- **仅在达到真实里程碑时**通过以下结构化格式声明进度，"
    "不要在每个迭代都报告：\n"
    "```\n"
    "[PROGRESS]\n"
    "summary: <一句话概述当前进展>\n"
    "milestone: <当前里程碑名称>\n"
    "completed_items: [\"已完成项1\", \"已完成项2\"]\n"
    "next_step: <下一步计划>\n"
    "blocked: true|false\n"
    "blocker_reason: <阻塞原因（blocked=true 时必填）>\n"
    "needs_operator: true|false\n"
    "evidence: <证据：测试结果摘要、修改文件路径、命令输出等>\n"
    "```\n"
    "- blocked 为 true 时必须同时说明：当前事实、已尝试的方法、需要什么帮助。\n"
    "- needs_operator 为 true 时说明操作员需要做什么。\n\n"
    "## 压力适应\n"
    "- **CONSERVATIVE 模式**：减少探索性操作，优先复用已有证据和已验证方案；"
    "缩短规划时间，尽快产出。\n"
    "- **CRITICAL 模式**：完全停止探索，只做最小修复；"
    "优先确保当前成果可验收，不接受新的复杂变更。\n"
    "- 收到压力模式变化通知后，立即调整行为策略。\n\n"
    "## 完成声明\n"
    "- 声明任务完成时必须包含验证证据：测试通过结果、修改文件的绝对路径、"
    "或命令执行输出。\n"
    "- 无证据的完成声明视为无效，必须补充验证结果。\n\n"
    "## 禁止行为\n"
    "- 禁止猜测或编造未观察到的信息"
    "（文件内容、测试结果、其他 Session 状态）。\n"
    "- 禁止循环等待其他 Session 的消息而不升级。\n"
    "- 禁止在没有新信息的情况下重复发送相同或类似的协作消息。\n\n"
    "遵循以上协议，在分配的职责范围内推进目标。"
)


def inject_coordination_protocol() -> str:
    """Return the coordination protocol as a string suitable for injection
    into the agent's iteration instruction.

    The returned text is a behavior constraint only — it does not grant
    tool access, permissions, or cross-session context.
    """
    return COORDINATION_PROTOCOL_PROMPT


def inject_pressure_guidance(pressure_mode: PressureMode | str) -> str:
    """Return pressure-adaptive guidance text keyed to the current
    *pressure_mode*.

    Used when the pressure mode changes mid-run, so the agent can
    receive an explicit behavioral adjustment without re-injecting the
    full coordination protocol.
    """
    mode = PressureMode(pressure_mode)
    hints: dict[PressureMode, str] = {
        PressureMode.NORMAL: (
            "压力模式 NORMAL：预算充足，可以正常探索和验证。"
            "按计划推进目标，保持例行进度声明。"
        ),
        PressureMode.CONSERVATIVE: (
            "压力模式 CONSERVATIVE：预算偏紧。减少探索性操作，"
            "优先复用已有证据和已验证方案；缩短规划时间，每步都应有明确产出。"
        ),
        PressureMode.CRITICAL: (
            "压力模式 CRITICAL：预算紧急。完全停止探索，只做最小修复；"
            "立即收尾当前工作并准备验收，不接受新的复杂变更。"
        ),
    }
    return hints.get(mode, f"压力模式 {mode.value}：请按当前预算状态调整行为策略。")
