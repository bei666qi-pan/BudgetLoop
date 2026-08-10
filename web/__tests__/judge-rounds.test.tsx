import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JudgeRounds } from "@/components/containers/JudgeRounds";
import type { JudgeState, TeamChatMessage, WorkSessionSummary } from "@/lib/types";

const sessions = [
  { id: "judge", role: "汇总裁判", session_kind: "judge", system_managed: true },
  { id: "frontend", role: "前端", session_kind: "agent", system_managed: false },
  { id: "qa", role: "QA", session_kind: "agent", system_managed: false },
] as WorkSessionSummary[];

const messages = [
  {
    id: "feedback-1",
    sender_session_id: "judge",
    sender_role: "汇总裁判",
    recipient_session_id: "frontend",
    recipient_role: "前端",
    delivery_state: "acknowledged",
    content: "补充响应式证据",
    created_at: "2026-08-10T01:01:00Z",
    entry_type: "handoff",
    author_type: "session",
    metadata: {},
  },
  {
    id: "reply-1",
    sender_session_id: "frontend",
    sender_role: "前端",
    recipient_session_id: "judge",
    recipient_role: "汇总裁判",
    delivery_state: "acknowledged",
    content: "已补充 390px 截图",
    created_at: "2026-08-10T01:02:00Z",
    entry_type: "handoff",
    author_type: "session",
    metadata: {},
  },
] as TeamChatMessage[];

const judge = {
  enabled: true,
  state: "waiting_replies",
  session: { id: "judge", role: "汇总裁判", status: "WAITING_APPROVAL", system_managed: true, budget: {} },
  policy: { id: "policy", gates: [], model_config: {}, safety_limits: {} },
  pending_reply_session_ids: ["frontend", "qa"],
  current_round: {
    id: "round-2",
    sequence: 2,
    status: "waiting_replies",
    phase: "feedback",
    verdict: "rework",
    summary: "响应式证据不足",
    evidence_refs: ["desktop.png"],
    model_verdict: null,
    feedback_message_ids: ["feedback-1"],
    pending_session_ids: ["frontend", "qa"],
    gates: [{ id: "gate", gate_name: "tests_passed", passed: false, evidence: {}, failure_reason: "测试未通过" }],
    findings: [],
    created_at: "2026-08-10T01:00:00Z",
    updated_at: "2026-08-10T01:03:00Z",
  },
  rounds: [],
} as unknown as JudgeState;
judge.rounds = [judge.current_round!];

describe("JudgeRounds", () => {
  it("shows durable loading state before judge data arrives", () => {
    render(<JudgeRounds judge={null} messages={[]} sessions={[]} loading busy={false} onResume={vi.fn()} />);
    expect(screen.getByText("加载裁判数据库状态…")).toBeInTheDocument();
    expect(screen.getByText(/恢复轮次、门禁、消息送达/)).toBeInTheDocument();
  });

  it("groups one round's parallel requests, replies, gates and verdict", () => {
    render(<JudgeRounds judge={judge} messages={messages} sessions={sessions} loading={false} busy={false} onResume={vi.fn()} />);
    expect(screen.getByText("汇总裁判 · 第 2 轮")).toBeInTheDocument();
    expect(screen.getByText("等待 2 个 Agent 确认/回复")).toBeInTheDocument();
    expect(screen.getByText("裁判定向请求")).toBeInTheDocument();
    expect(screen.getByText("Agent 确认与回复")).toBeInTheDocument();
    expect(screen.getByText(/汇总裁判 → 前端/)).toBeInTheDocument();
    expect(screen.getByText(/前端 → 汇总裁判/)).toBeInTheDocument();
    expect(screen.getByText("响应式证据不足")).toBeInTheDocument();
    expect(screen.getByText("rework")).toBeInTheDocument();
  });
});
