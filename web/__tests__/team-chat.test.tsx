import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TeamChannel } from "@/components/containers/TeamChannel";
import type {
  ContainerLifecycle,
  TeamChatMessage,
  WorkSessionSummary,
} from "@/lib/types";

/* ── 工厂函数 ── */

function session(id: string, role: string, extra?: Partial<WorkSessionSummary>): WorkSessionSummary {
  return {
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
    ...extra,
  };
}

function msg(
  overrides: Partial<TeamChatMessage> & { id: string },
): TeamChatMessage {
  return {
    entry_type: "message",
    author_type: "session",
    sender_session_id: "s1",
    sender_role: "测试Sender",
    recipient_session_id: null,
    recipient_role: null,
    content: "测试消息内容",
    delivery_state: "acknowledged",
    metadata: {},
    created_at: "2026-07-25T01:00:00Z",
    idempotency_key: null,
    delivered_at: null,
    ...overrides,
  };
}

const DEFAULT_SESSIONS = [
  session("s1", "后端实现"),
  session("s2", "前端开发"),
  session("s3", "测试编写"),
];

describe("TeamChannel message rendering by type", () => {
  it("renders a normal message (💬) with content and sender role", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "m1", entry_type: "message", content: "大家好" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("大家好")).toBeInTheDocument();
    expect(screen.getByText("测试Sender")).toBeInTheDocument();
  });

  it("renders a handoff (📤) with structured sections from metadata", () => {
    render(
      <TeamChannel
        messages={[
          msg({
            id: "h1",
            entry_type: "handoff",
            sender_role: "架构设计",
            recipient_role: "后端实现",
            content: "原始内容",
            delivery_state: "acknowledged",
            metadata: {
              conclusion: "接口定义已完成，使用POST /api/tasks",
              evidence: "api-contract.md L42",
              open_questions: ["是否需要分页？", "是否需要认证？"],
              next_step: "实现POST /api/tasks端点",
            },
          }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("架构设计")).toBeInTheDocument();
    expect(screen.getByText("→ 后端实现")).toBeInTheDocument();
    expect(screen.getByText("接口定义已完成，使用POST /api/tasks")).toBeInTheDocument();
    expect(screen.getByText("api-contract.md L42")).toBeInTheDocument();
    expect(screen.getByText("是否需要分页？")).toBeInTheDocument();
    expect(screen.getByText("是否需要认证？")).toBeInTheDocument();
    expect(screen.getByText("实现POST /api/tasks端点")).toBeInTheDocument();

    // sections labels
    expect(screen.getByText("结论")).toBeInTheDocument();
    expect(screen.getByText("证据")).toBeInTheDocument();
    expect(screen.getByText("未决问题")).toBeInTheDocument();
    expect(screen.getByText("下一步")).toBeInTheDocument();
  });

  it("handoff falls back to content when no structured metadata", () => {
    render(
      <TeamChannel
        messages={[
          msg({
            id: "h2",
            entry_type: "handoff",
            sender_role: "A",
            recipient_role: "B",
            content: "纯文本handoff内容",
            delivery_state: "acknowledged",
            metadata: {},
          }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("纯文本handoff内容")).toBeInTheDocument();
  });

  it("renders a progress_update (📋) with structured card", () => {
    render(
      <TeamChannel
        messages={[
          msg({
            id: "p1",
            entry_type: "progress_update",
            sender_role: "测试编写",
            content: "",
            delivery_state: "injected",
            metadata: {
              summary: "已完成3/5个测试用例",
              milestone: "测试覆盖",
              completed_items: 3,
              next_step: "编写集成测试",
              blocked: false,
            },
          }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("进度更新")).toBeInTheDocument();
    expect(screen.getByText("已完成3/5个测试用例")).toBeInTheDocument();
    expect(screen.getByText("测试覆盖")).toBeInTheDocument();
    expect(screen.getByText("已完成 3 项")).toBeInTheDocument();
    expect(screen.getByText(/编写集成测试/)).toBeInTheDocument();
    expect(screen.getByText("下一步：")).toBeInTheDocument();
  });

  it("progress_update shows blocked indicator when blocked=true", () => {
    render(
      <TeamChannel
        messages={[
          msg({
            id: "p2",
            entry_type: "progress_update",
            sender_role: "前端开发",
            content: "",
            delivery_state: "acknowledged",
            metadata: {
              summary: "组件开发受阻",
              milestone: "UI组件",
              completed_items: 2,
              next_step: "等待后端API就绪",
              blocked: true,
            },
          }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("阻塞")).toBeInTheDocument();
    expect(screen.getByText("组件开发受阻")).toBeInTheDocument();
  });

  it("renders a system_fact (⚠) with yellow left border", () => {
    const { container } = render(
      <TeamChannel
        messages={[
          msg({
            id: "s1",
            entry_type: "system_fact",
            sender_role: "System",
            content: "测试编写Session预算消耗达70%",
            delivery_state: "acknowledged",
            metadata: {},
          }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("测试编写Session预算消耗达70%")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
    // system_fact articles should have border-l-2 border-warning class
    const article = container.querySelector("article");
    expect(article?.className).toContain("border-l-2");
    expect(article?.className).toContain("border-warning");
  });
});

describe("TeamChannel status labels", () => {
  it("shows 已排队 for queued state", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "q1", delivery_state: "queued" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("已排队")).toBeInTheDocument();
  });

  it("shows 等待下次执行检查点 for injected state", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "i1", delivery_state: "injected" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("等待下次执行检查点")).toBeInTheDocument();
  });

  it("shows 已送达 for acknowledged state", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "a1", delivery_state: "acknowledged" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("已送达")).toBeInTheDocument();
  });

  it("shows 送达失败 for failed state", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "f1", delivery_state: "failed" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("送达失败")).toBeInTheDocument();
  });
});

describe("TeamChannel filter toggle", () => {
  it("shows 团队频道 header by default (all filter)", () => {
    render(
      <TeamChannel
        messages={[]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("团队频道")).toBeInTheDocument();
    expect(screen.getByText("全部消息")).toBeInTheDocument();
  });

  it("filters messages to selected session when filter is active", () => {
    render(
      <TeamChannel
        messages={[
          msg({ id: "m1", sender_session_id: "s1", sender_role: "后端实现", content: "后端消息" }),
          msg({ id: "m2", sender_session_id: "s2", sender_role: "前端开发", content: "前端消息" }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId="s1"
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    // initially with selectedSessionId="s1", filter should be "s1" via useEffect
    // so only s1 messages show
    expect(screen.getByText("会话对话")).toBeInTheDocument();
    expect(screen.getByText("后端消息")).toBeInTheDocument();
    expect(screen.queryByText("前端消息")).toBeNull();
  });

  it("shows all messages when filter is toggled to team channel", async () => {
    const user = userEvent.setup();
    const onSelectSession = vi.fn();

    render(
      <TeamChannel
        messages={[
          msg({ id: "m1", sender_session_id: "s1", sender_role: "后端实现", content: "后端消息" }),
          msg({ id: "m2", sender_session_id: "s2", sender_role: "前端开发", content: "前端消息" }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId="s1"
        onSelectSession={onSelectSession}
        onSendMessage={vi.fn()}
      />,
    );

    // Start with session filter active
    expect(screen.getByText("仅此会话")).toBeInTheDocument();

    // Click filter toggle button
    await user.click(screen.getByText("仅此会话"));

    // Now all messages should be visible
    expect(screen.getByText("团队频道")).toBeInTheDocument();
    expect(screen.getByText("全部消息")).toBeInTheDocument();
  });
});

describe("TeamChannel paused state", () => {
  it("disables chat input when container is paused", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "m1" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="paused"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    const textarea = screen.getByPlaceholderText("团队已暂停，无法发送消息。");
    expect(textarea).toBeDisabled();

    const sendButton = screen.getByRole("button", { name: /发送/ });
    expect(sendButton).toBeDisabled();

    // Paused indicator should be visible
    expect(screen.getByText("已暂停")).toBeInTheDocument();
  });

  it("enables chat input when container is active", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "m1" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    const textarea = screen.getByPlaceholderText("输入消息…");
    expect(textarea).not.toBeDisabled();
  });
});

describe("TeamChannel CLI engine indicator", () => {
  it("shows CLI engine note when session uses codex engine", () => {
    const cliSessions = [
      session("s1", "后端实现", {}),
    ];
    // Mock execution_engine on session
    (cliSessions[0] as Record<string, unknown>).execution_engine = "codex";

    render(
      <TeamChannel
        messages={[msg({ id: "m1", sender_session_id: "s1" })]}
        sessions={cliSessions}
        containerLifecycle="active"
        selectedSessionId="s1"
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText(/CLI 引擎: 消息在安全检查点注入/)).toBeInTheDocument();
  });

  it("shows CLI engine note for gemini-cli engine", () => {
    const cliSessions = [
      session("s2", "前端开发", {}),
    ];
    (cliSessions[0] as Record<string, unknown>).execution_engine = "gemini-cli";

    render(
      <TeamChannel
        messages={[msg({ id: "m2", sender_session_id: "s2" })]}
        sessions={cliSessions}
        containerLifecycle="active"
        selectedSessionId="s2"
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText(/CLI 引擎: 消息在安全检查点注入/)).toBeInTheDocument();
  });

  it("does NOT show CLI engine note for server engine", () => {
    render(
      <TeamChannel
        messages={[msg({ id: "m1", sender_session_id: "s1" })]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId="s1"
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.queryByText(/CLI 引擎/)).toBeNull();
  });
});

describe("TeamChannel message dedup", () => {
  it("deduplicates messages with the same idempotency_key", () => {
    render(
      <TeamChannel
        messages={[
          msg({ id: "m1", idempotency_key: "key-abc", content: "第一条" }),
          msg({ id: "m2", idempotency_key: "key-abc", content: "重复" }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("第一条")).toBeInTheDocument();
    expect(screen.queryByText("重复")).toBeNull();
  });

  it("shows all messages with different idempotency keys", () => {
    render(
      <TeamChannel
        messages={[
          msg({ id: "m1", idempotency_key: "key-1", content: "第一条" }),
          msg({ id: "m2", idempotency_key: "key-2", content: "第二条" }),
        ]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("第一条")).toBeInTheDocument();
    expect(screen.getByText("第二条")).toBeInTheDocument();
  });
});

describe("TeamChannel handoff guidance", () => {
  it("shows guidance text when handoff type is selected in composer", async () => {
    const user = userEvent.setup();

    render(
      <TeamChannel
        messages={[]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    // Select handoff type from dropdown
    const typeSelect = screen.getByDisplayValue("消息");
    await user.selectOptions(typeSelect, "handoff");

    expect(
      screen.getByText("Handoff 只包含结论、证据、未决问题和接收方下一步。"),
    ).toBeInTheDocument();
  });
});

describe("TeamChannel empty state", () => {
  it("shows empty state when no messages", () => {
    render(
      <TeamChannel
        messages={[]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId={null}
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("暂无消息")).toBeInTheDocument();
  });

  it("shows session-specific empty message when filtered", () => {
    render(
      <TeamChannel
        messages={[]}
        sessions={DEFAULT_SESSIONS}
        containerLifecycle="active"
        selectedSessionId="s1"
        onSelectSession={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("当前会话还没有消息记录。")).toBeInTheDocument();
  });
});
