import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HandoffComposer } from "@/components/containers/HandoffComposer";
import { SessionTranscript } from "@/components/containers/SessionTranscript";
import {
  aggregateContainerCounts,
  availableHandoffRecipients,
  budgetRatio,
  filterContainers,
  incomingMessages,
  presentWorktreePath,
} from "@/lib/container-presentation";
import type { SessionTranscriptEntry, WorkContainer, WorkSessionSummary } from "@/lib/types";

const session = (id: string, role: string): WorkSessionSummary => ({
  id,
  container_id: "c1",
  role,
  goal: `${role}目标`,
  status: "EXECUTING",
  task_id: `task-${id}`,
  current_run_id: `run-${id}`,
  conversation_id: null,
  iteration: 2,
  worktree_enabled: false,
  worktree_branch: null,
  worktree_path: null,
  workspace_status: "READY",
  workspace_error: null,
  created_at: "2026-07-25T01:00:00Z",
  updated_at: "2026-07-25T01:00:00Z",
});

const container = (id: string, state: WorkContainer["lifecycle_state"]): WorkContainer => ({
  id,
  name: id === "c1" ? "多会话协作" : "结算服务",
  project_goal: id === "c1" ? "实现可审计 Handoff" : "提升稳定性",
  lifecycle_state: state,
  base_workdir: "/workspace/project",
  default_workspace_policy: "isolated",
  counts: { sessions: 2, running: 1, waiting: 0, attention: id === "c1" ? 1 : 0 },
  sessions: [],
  created_at: "2026-07-25T01:00:00Z",
  updated_at: "2026-07-25T01:00:00Z",
});

const handoff: SessionTranscriptEntry = {
  id: "handoff-018",
  entry_type: "handoff",
  author_type: "session",
  sender_session_id: "s1",
  sender_role: "架构设计",
  recipient_session_id: "s2",
  recipient_role: "后端实现",
  content: "请实现幂等接口",
  delivery_state: "delivered",
  metadata: {},
  created_at: "2026-07-25T01:00:00Z",
  delivered_at: "2026-07-25T01:00:01Z",
};

describe("Agent Team presentation", () => {
  it("aggregates only data-backed session state and combines filters", () => {
    const items = [container("c1", "active"), container("c2", "paused")];
    expect(aggregateContainerCounts(items)).toEqual({ containers: 2, running: 2, waiting: 0, attention: 1 });
    expect(filterContainers(items, "handoff", "active").map((item) => item.id)).toEqual(["c1"]);
    expect(filterContainers(items, "", "paused").map((item) => item.id)).toEqual(["c2"]);
  });

  it("keeps recipient and budget calculations bounded", () => {
    const sessions = [session("s1", "架构设计"), session("s2", "后端实现")];
    expect(availableHandoffRecipients(sessions, "s1").map((item) => item.id)).toEqual(["s2"]);
    expect(budgetRatio({ budget: { max_total_tokens: 100, used_tokens: 120 } })).toBe(1);
    expect(incomingMessages([handoff], "s2")).toEqual([handoff]);
    expect(presentWorktreePath("/workspace/project/.budgetloop/worktrees/session-1")).toBe(
      ".budgetloop/worktrees/session-1",
    );
    expect(presentWorktreePath("/workspace/custom/session-1")).toBe(
      "/workspace/custom/session-1",
    );
  });
});

describe("Agent Team collaboration components", () => {
  it("labels public Agent output separately from explicit handoff", () => {
    render(<SessionTranscript entries={[handoff, { ...handoff, id: "event-1", entry_type: "agent_output", author_type: "agent", content: "公开结果", delivery_state: "recorded" }]} />);
    expect(screen.getByText("Agent 输出")).toBeInTheDocument();
    expect(screen.getByText("公开 Agent 输出 · 不包含隐藏推理")).toBeInTheDocument();
    expect(screen.getByText("handoff-018")).toBeInTheDocument();
    expect(screen.getByText("已送达")).toBeInTheDocument();
  });

  it("sends operator messages to the selected session and handoffs to another session", async () => {
    const user = userEvent.setup();
    const sessions = [session("s1", "架构设计"), session("s2", "后端实现")];
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<HandoffComposer selected={sessions[0]} sessions={sessions} busy={false} onSend={onSend} />);
    await user.type(screen.getByPlaceholderText("输入消息，或将上下文移交给其他 Session…"), "明确上下文");
    await user.click(screen.getByRole("button", { name: "创建 Handoff" }));
    expect(onSend).toHaveBeenCalledWith("handoff", "明确上下文", "s2");
  });
});
