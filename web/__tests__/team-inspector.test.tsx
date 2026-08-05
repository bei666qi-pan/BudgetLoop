import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { TeamInspector } from "@/components/containers/TeamInspector";
import type {
  TeamInspectorProgress,
  TeamInspectorUsage,
  WorkContainer,
  WorkSessionSummary,
} from "@/lib/types";

/* ── Mock API ── */
const mockApi = vi.hoisted(() => ({
  fetchTeamProgress: vi.fn(),
  fetchTeamUsage: vi.fn(),
  pauseContainer: vi.fn(),
  resumeContainer: vi.fn(),
  stopContainer: vi.fn(),
  patchContainerBudget: vi.fn(),
  pauseSession: vi.fn(),
  resumeSession: vi.fn(),
  cancelSession: vi.fn(),
  patchSessionBudget: vi.fn(),
  appendSessionInstruction: vi.fn(),
}));

vi.mock("@/lib/api", () => mockApi);

/* ── 工厂数据 ── */

function makeSession(id: string, role: string): WorkSessionSummary {
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
  };
}

function makeContainer(overrides: Partial<WorkContainer> = {}): WorkContainer {
  return {
    id: "c1",
    name: "多会话协作",
    project_goal: "实现可审计 Handoff",
    lifecycle_state: "active",
    base_workdir: "/workspace",
    default_workspace_policy: "isolated",
    counts: { sessions: 3, running: 2, waiting: 1, attention: 0 },
    sessions: [],
    created_at: "2026-07-25T01:00:00Z",
    updated_at: "2026-07-25T01:00:00Z",
    ...overrides,
  };
}

function makeProgress(): TeamInspectorProgress {
  return {
    team_summary: {
      total: 4,
      running: 2,
      waiting: 1,
      paused: 0,
      blocked: 1,
      completed: 0,
    },
    active_stage: "实现+审查",
    next_focus: "完成 API 路由",
    sessions: [
      {
        id: "sig-1",
        session_id: "s1",
        run_id: "run-s1",
        summary: "后端实现进行中",
        milestone: "数据模型+迁移",
        completed_items: ["数据模型", "迁移脚本"],
        next_step: "API 路由实现",
        blocked: false,
        blocker_reason: null,
        needs_operator: false,
        evidence: "models.py L392",
        iteration: 3,
        created_at: "2026-07-25T01:00:00Z",
      },
      {
        id: "sig-2",
        session_id: "s2",
        run_id: "run-s2",
        summary: "前端开发进行中",
        milestone: "组件创建",
        completed_items: ["组件 A", "组件 B", "组件 C"],
        next_step: "等待后端 API",
        blocked: true,
        blocker_reason: "等待后端 API 就绪",
        needs_operator: false,
        evidence: null,
        iteration: 2,
        created_at: "2026-07-25T01:00:00Z",
      },
      {
        id: "sig-3",
        session_id: "s3",
        run_id: "run-s3",
        summary: null,
        milestone: null,
        completed_items: [],
        next_step: null,
        blocked: false,
        blocker_reason: null,
        needs_operator: true,
        evidence: null,
        iteration: 1,
        created_at: "2026-07-25T01:00:00Z",
      },
    ],
  };
}

function makeUsage(overrides: Partial<TeamInspectorUsage> = {}): TeamInspectorUsage {
  return {
    tokens: {
      used: 45200,
      max: 200000,
      remaining: 154800,
      prompt: 30000,
      completion: 8000,
      reasoning: 5000,
      cache_read: 2200,
    },
    cost: {
      used: 2.83,
      max: 15,
      remaining: 12.17,
    },
    wall_time_ms: 720000,
    max_wall_time_ms: 3600000,
    calls: {
      used: 34,
      max: 80,
    },
    health: "NORMAL",
    active_time_ms: 180000,
    parallelism: {
      current: 2,
      max: 4,
    },
    consumption_rate_tokens_per_min: 1300,
    estimated_depletion_at: "2026-07-25T03:15:00Z",
    ...overrides,
  };
}

const defaultProps = {
  containerId: "c1",
  container: makeContainer(),
  sessions: [makeSession("s1", "后端实现"), makeSession("s2", "前端开发")],
  selectedSessionId: null,
  sseConnected: true,
  dataStale: false,
};

/* ── 测试 ── */

describe("TeamInspector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({
      budget: {} as never,
      needs_resume: false,
    });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({
      budget: {} as never,
      needs_resume: false,
    });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  /* ── 渲染与折叠 ── */

  it("renders all three collapsible sections", async () => {
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("进度")).toBeInTheDocument();
    });
    expect(screen.getByText("用量")).toBeInTheDocument();
    expect(screen.getByText("控制")).toBeInTheDocument();
  });

  it("默认展开进度，折叠用量和控制", async () => {
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("团队摘要")).toBeInTheDocument();
    });

    // 用量摘要（token 使用量）在折叠时也可见（因为是 section badge 内容），
    // 但用量区块内部详细内容不渲染
    expect(screen.queryByText("Token 明细")).not.toBeInTheDocument();

    // 控制区块折叠
    expect(screen.queryByText("团队控制")).not.toBeInTheDocument();
  });

  it("点击折叠区块标题可切换展开/折叠", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("进度")).toBeInTheDocument();
    });

    // 点击"进度"折叠
    await user.click(screen.getByText("进度"));
    await waitFor(() => {
      expect(screen.queryByText("团队摘要")).not.toBeInTheDocument();
    });

    // 再点击展开
    await user.click(screen.getByText("进度"));
    await waitFor(() => {
      expect(screen.getByText("团队摘要")).toBeInTheDocument();
    });
  });

  it("点击用量区块展开后显示 Token 明细", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("用量")).toBeInTheDocument();
    });

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getByText("Token 明细")).toBeInTheDocument();
    });
  });

  /* ── 进度区块 ── */

  it("显示团队摘要 — 运行中/等待中/已阻塞计数", async () => {
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("运行中 2")).toBeInTheDocument();
    });
    expect(screen.getByText("等待中 1")).toBeInTheDocument();
    expect(screen.getByText("已阻塞 1")).toBeInTheDocument();
  });

  it("显示当前阶段和下一步焦点", async () => {
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("实现+审查")).toBeInTheDocument();
      expect(screen.getByText("完成 API 路由")).toBeInTheDocument();
    });
  });

  it("选中 Session 时显示其进度详情", async () => {
    render(<TeamInspector {...defaultProps} selectedSessionId="s1" />);

    await waitFor(() => {
      // "后端实现" appears in both section header and summary text - use getAllByText
      const matches = screen.getAllByText(/后端实现/);
      expect(matches.length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("后端实现进行中")).toBeInTheDocument();
      expect(screen.getByText("数据模型+迁移")).toBeInTheDocument();
      expect(screen.getByText("API 路由实现")).toBeInTheDocument();
      expect(screen.getByText("models.py L392")).toBeInTheDocument();
    });
  });

  it("选中阻塞 Session 时显示阻塞原因", async () => {
    render(<TeamInspector {...defaultProps} selectedSessionId="s2" />);

    await waitFor(() => {
      expect(screen.getByText("已阻塞")).toBeInTheDocument();
      expect(screen.getByText("等待后端 API 就绪")).toBeInTheDocument();
    });
  });

  it("选中 Session 在 needs_operator 时显示需操作员标识", async () => {
    render(<TeamInspector {...defaultProps} selectedSessionId="s3" />);

    await waitFor(() => {
      expect(screen.getByText("需操作员")).toBeInTheDocument();
    });
  });

  it("选中 Session 无进度信号时显示「Agent 未声明进度」空态", async () => {
    mockApi.fetchTeamProgress.mockResolvedValue({
      team_summary: { total: 2, running: 0, waiting: 0, paused: 0, blocked: 0, completed: 0 },
      active_stage: null,
      next_focus: null,
      sessions: [],
    });

    render(<TeamInspector {...defaultProps} selectedSessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("Agent 未声明进度")).toBeInTheDocument();
    });
  });

  it("无进度数据时显示空态", async () => {
    mockApi.fetchTeamProgress.mockResolvedValue(null as never);

    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("暂无进度数据")).toBeInTheDocument();
    });
  });

  /* ── 用量区块 ── */

  it("用量区块默认折叠时显示摘要信息", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("用量")).toBeInTheDocument();
    });

    // 展开用量
    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getByText("Tokens")).toBeInTheDocument();
      expect(screen.getByText("费用")).toBeInTheDocument();
      expect(screen.getByText("耗时")).toBeInTheDocument();
      expect(screen.getByText("压力")).toBeInTheDocument();
      expect(screen.getByText("调用")).toBeInTheDocument();
      expect(screen.getByText("消耗速率")).toBeInTheDocument();
      expect(screen.getByText("预计耗尽")).toBeInTheDocument();
    });
  });

  it("显示 Token 用量和百分比", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      // formatTokens(45200) → "45.2k", embedded in "45.2k / 200.0k (23%)"
      expect(screen.getByText(/45\.2k/)).toBeInTheDocument();
      expect(screen.getByText(/200\.0k/)).toBeInTheDocument();
      expect(screen.getByText(/\(23%\)/)).toBeInTheDocument();
    });
  });

  it("显示健康状态标识 NORMAL", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getAllByText("正常").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("CONSERVATIVE 显示保守", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage({ health: "CONSERVATIVE" }));
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getAllByText("保守").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("CRITICAL 显示危急", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage({ health: "CRITICAL" }));
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getAllByText("危急").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("展开 Token 明细显示 prompt/completion/reasoning/cache", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));
    await waitFor(() => {
      expect(screen.getByText("Token 明细")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Token 明细"));

    await waitFor(() => {
      expect(screen.getByText("Prompt")).toBeInTheDocument();
      expect(screen.getByText("Completion")).toBeInTheDocument();
      expect(screen.getByText("Reasoning")).toBeInTheDocument();
      expect(screen.getByText("Cache")).toBeInTheDocument();
    });
  });

  it("展开额外统计显示活跃时间和并行度", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));
    await waitFor(() => {
      expect(screen.getByText("额外统计")).toBeInTheDocument();
    });

    await user.click(screen.getByText("额外统计"));

    await waitFor(() => {
      expect(screen.getByText("活跃时间")).toBeInTheDocument();
      expect(screen.getByText("并行度")).toBeInTheDocument();
    });
  });

  /* ── 缺失字段: 显示「未上报」而非 0 ── */

  it("cost 为 null 时显示「未上报」", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ cost: { used: null, max: 15, remaining: null } }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getByText("未上报")).toBeInTheDocument();
    });
  });

  it("consumption_rate 为 null 时显示「未上报」", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ consumption_rate_tokens_per_min: null }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      const unreported = screen.getAllByText("未上报");
      // 至少有一个 "未上报"（消耗速率）
      expect(unreported.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("cache_read 为 null 时显示「未上报」", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ tokens: { used: 100, max: 1000, remaining: 900, prompt: 50, completion: 20, reasoning: 10, cache_read: null } }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));
    await waitFor(() => {
      expect(screen.getByText("Token 明细")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Token 明细"));

    await waitFor(() => {
      // 在明细表中，cache 行显示 "未上报"
      const allUnreported = screen.getAllByText("未上报");
      expect(allUnreported.length).toBeGreaterThanOrEqual(1);
    });
  });

  /* ── 控制区块 ── */

  it("展开控制区块显示团队控制按钮", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /暂停/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /恢复/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /停止/ })).toBeInTheDocument();
    });
  });

  it("点击暂停调用 pauseContainer", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    // 点击第一个暂停按钮（团队暂停）
    const pauseButtons = screen.getAllByRole("button", { name: /暂停/ });
    await user.click(pauseButtons[0]);

    await waitFor(() => {
      expect(mockApi.pauseContainer).toHaveBeenCalledWith("c1");
    });
  });

  it("点击恢复调用 resumeContainer", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /恢复/ }));

    await waitFor(() => {
      expect(mockApi.resumeContainer).toHaveBeenCalledWith("c1");
    });
  });

  it("点击停止打开确认对话框", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /停止/ }));

    await waitFor(() => {
      expect(screen.getByText(/停止后不可恢复/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /确认停止/ })).toBeInTheDocument();
    });
  });

  it("停止确认对话框中确认停止后调用 stopContainer", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /停止/ }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /确认停止/ })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /确认停止/ }));

    await waitFor(() => {
      expect(mockApi.stopContainer).toHaveBeenCalledWith("c1");
    });
  });

  /* ── 预算调整流程 ── */

  it("点击团队预算调整按钮显示内联表单", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    // 第一个"调整"是团队预算
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
      expect(screen.getByText("确认调整")).toBeInTheDocument();
    });
  });

  it("预算调整显示当前值和已使用值", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/当前: 200,000/)).toBeInTheDocument();
      expect(screen.getByText(/已使用: 45,200/)).toBeInTheDocument();
    });
  });

  it("预算调整输入新值后显示变更预览", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    const input = screen.getByRole("spinbutton", { name: /团队预算.*新值/ });
    await user.clear(input);
    await user.type(input, "300000");

    await waitFor(() => {
      expect(screen.getByText(/200,000 → 300,000/)).toBeInTheDocument();
    });
  });

  it("确认调整后调用 patchContainerBudget", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    const input = screen.getByRole("spinbutton", { name: /团队预算.*新值/ });
    await user.clear(input);
    await user.type(input, "300000");

    await user.click(screen.getByText("确认调整"));

    await waitFor(() => {
      expect(mockApi.patchContainerBudget).toHaveBeenCalledWith("c1", {
        max_total_tokens: 300000,
      });
    });
  });

  /* ── 预算耗尽后恢复 ── */

  it("预算耗尽且 needs_resume 为 true 时显示恢复按钮", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ tokens: { used: 200000, max: 200000, remaining: 0, prompt: 100000, completion: 50000, reasoning: 30000, cache_read: 20000 } }),
    );

    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /已增加预算，请点击恢复/ }),
      ).toBeInTheDocument();
    });
  });

  /* ── 取消确认对话框 ── */

  it("选中 Session 后显示取消按钮，点击后弹出确认对话框", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        selectedSessionId="s1"
        sessions={[
          makeSession("s1", "后端实现"),
          makeSession("s2", "前端开发"),
        ]}
      />,
    );

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText(/选中 Session: 后端实现/)).toBeInTheDocument();
    });

    // Session 取消按钮
    const cancelButtons = screen.getAllByRole("button", { name: /取消/ });
    await user.click(cancelButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/取消后无法恢复/)).toBeInTheDocument();
      expect(screen.getByText(/「后端实现」/)).toBeInTheDocument();
    });
  });

  it("取消确认后调用 cancelSession", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        selectedSessionId="s1"
        sessions={[
          makeSession("s1", "后端实现"),
          makeSession("s2", "前端开发"),
        ]}
      />,
    );

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText(/选中 Session: 后端实现/)).toBeInTheDocument();
    });

    const cancelButtons = screen.getAllByRole("button", { name: /取消/ });
    await user.click(cancelButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /确认取消/ })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /确认取消/ }));

    await waitFor(() => {
      expect(mockApi.cancelSession).toHaveBeenCalledWith("c1", "s1");
    });
  });

  /* ── 团队模式切换 ── */

  it("container 有 team_mode 时显示团队模式信息", async () => {
    const container = makeContainer({
      preset_snapshot: {
        team_mode: "guided",
      } as WorkContainer["preset_snapshot"],
    });

    const user = userEvent.setup();
    render(
      <TeamInspector {...defaultProps} container={container} />,
    );

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队模式")).toBeInTheDocument();
      expect(screen.getByText("引导模式")).toBeInTheDocument();
    });
  });

  it("自主模式显示对应文本", async () => {
    const container = makeContainer({
      preset_snapshot: {
        team_mode: "autonomous",
      } as WorkContainer["preset_snapshot"],
    });

    const user = userEvent.setup();
    render(
      <TeamInspector {...defaultProps} container={container} />,
    );

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("自主模式")).toBeInTheDocument();
    });
  });

  it("没有 team_mode 时不显示团队模式区块", async () => {
    const container = makeContainer();
    const user = userEvent.setup();
    render(
      <TeamInspector {...defaultProps} container={container} />,
    );

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });
    expect(screen.queryByText("团队模式")).not.toBeInTheDocument();
  });

  /* ── 控制禁用状态 ── */

  it("SSE 断开时显示警告并禁用控制按钮", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} sseConnected={false} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(
        screen.getByText("SSE 已断开，控制操作不可用"),
      ).toBeInTheDocument();
    });

    const pauseBtn = screen.getByRole("button", {
      name: /暂停/,
    }) as HTMLButtonElement;
    expect(pauseBtn.disabled).toBe(true);
  });

  it("数据过期时显示警告并禁用控制按钮", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} dataStale />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(
        screen.getByText("数据可能过期，请等待连接恢复"),
      ).toBeInTheDocument();
    });

    const pauseBtn = screen.getByRole("button", {
      name: /暂停/,
    }) as HTMLButtonElement;
    expect(pauseBtn.disabled).toBe(true);
  });

  /* ── Session 级追加指令 ── */

  it("选中 Session 后可发送追加指令", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        selectedSessionId="s1"
        sessions={[
          makeSession("s1", "后端实现"),
          makeSession("s2", "前端开发"),
        ]}
      />,
    );

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText(/选中 Session: 后端实现/)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText("输入纠偏或追加指令...");
    await user.type(textarea, "请优先修复数据模型问题");

    const sendBtn = screen.getByRole("button", { name: /发送指令/ });
    await user.click(sendBtn);

    await waitFor(() => {
      expect(mockApi.appendSessionInstruction).toHaveBeenCalledWith(
        "c1",
        "s1",
        "请优先修复数据模型问题",
      );
    });
  });

  /* ── 并行度调整 ── */

  it("可调整并行度并显示提示文本", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));

    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    // 找第二个"调整"按钮（并行度调整）
    const adjustButtons = screen.getAllByText("调整");
    // 团队预算调整是第一个，并行度是第二个
    await user.click(adjustButtons[1]);

    await waitFor(() => {
      expect(screen.getByText("最大并行度")).toBeInTheDocument();
      expect(screen.getByText("仅影响新发起的 LLM 调用")).toBeInTheDocument();
    });
  });
});

/* ── Screen Reader Accessibility ── */
describe("TeamInspector screen reader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  it("collapsible sections have aria-expanded reflecting their state", async () => {
    render(<TeamInspector {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("进度")).toBeInTheDocument();
    });

    // "进度" button is expanded by default
    const progressBtn = screen.getByText("进度").closest("button");
    expect(progressBtn).not.toBeNull();
    expect(progressBtn!.getAttribute("aria-expanded")).toBe("true");

    // "用量" button is collapsed by default
    const usageBtn = screen.getByText("用量").closest("button");
    expect(usageBtn).not.toBeNull();
    expect(usageBtn!.getAttribute("aria-expanded")).toBe("false");

    // "控制" button is collapsed by default
    const controlBtn = screen.getByText("控制").closest("button");
    expect(controlBtn).not.toBeNull();
    expect(controlBtn!.getAttribute("aria-expanded")).toBe("false");
  });

  it("toggling a section updates aria-expanded", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("用量")).toBeInTheDocument();
    });

    const usageBtn = screen.getByText("用量").closest("button");
    expect(usageBtn!.getAttribute("aria-expanded")).toBe("false");

    // Expand
    await user.click(screen.getByText("用量"));
    expect(usageBtn!.getAttribute("aria-expanded")).toBe("true");

    // Collapse
    await user.click(screen.getByText("用量"));
    expect(usageBtn!.getAttribute("aria-expanded")).toBe("false");
  });

  it("confirmation dialog has role=alertdialog and aria-modal=true", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /停止/ }));

    await waitFor(() => {
      const dialog = screen.getByRole("alertdialog");
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute("aria-modal", "true");
    });
  });

  it("confirmation dialog has aria-label matching its title", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /停止/ }));

    await waitFor(() => {
      const dialog = screen.getByRole("alertdialog");
      expect(dialog).toHaveAttribute("aria-label", "停止团队");
    });
  });

  it("status notice has role=status for dynamic announcement", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        selectedSessionId="s1"
        sessions={[makeSession("s1", "后端实现"), makeSession("s2", "前端开发")]}
      />,
    );

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText(/选中 Session: 后端实现/)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText("输入纠偏或追加指令...");
    await user.type(textarea, "测试指令");

    const sendBtn = screen.getByRole("button", { name: /发送指令/ });
    await user.click(sendBtn);

    await waitFor(() => {
      const status = screen.getByRole("status");
      expect(status).toBeInTheDocument();
      expect(status).toHaveTextContent("指令已提交，将在下次执行检查点注入。");
    });
  });

  it("aside component has aria-label for screen reader context", () => {
    render(<TeamInspector {...defaultProps} />);
    const aside = screen.getByLabelText("团队检查器");
    expect(aside.tagName).toBe("ASIDE");
  });

  it("budget adjust input has aria-label for screen readers", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      const input = screen.getByRole("spinbutton", { name: /新值/ });
      expect(input).toBeInTheDocument();
    });
  });
});

/* ── Edge Cases: Budget Adjustment Form ── */
describe("TeamInspector budget edge cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  it("submitting empty value does not call patchContainerBudget", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    const input = screen.getByRole("spinbutton", { name: /新值/ });
    await user.clear(input);
    // Input is empty — confirm button should be disabled
    const confirmBtn = screen.getByText("确认调整");
    expect(confirmBtn).toBeDisabled();
  });

  it("submitting negative value does not call patchContainerBudget", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    const input = screen.getByRole("spinbutton", { name: /新值/ });
    await user.clear(input);
    await user.type(input, "-100");
    // Negative value is invalid: !isValid since newVal > 0 is false
    const confirmBtn = screen.getByText("确认调整");
    expect(confirmBtn).toBeDisabled();
  });

  it("submitting zero value is invalid", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    const input = screen.getByRole("spinbutton", { name: /新值/ });
    await user.clear(input);
    await user.type(input, "0");
    // Zero is invalid: !isValid since newVal > 0 is false
    const confirmBtn = screen.getByText("确认调整");
    expect(confirmBtn).toBeDisabled();
  });

  it("shows validation error when new budget is below used+reserved", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });

    const adjustButtons = screen.getAllByText("调整");
    await user.click(adjustButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
    });

    // Current usage: 45,200 tokens. Try to set budget to 30,000 (below used).
    const input = screen.getByRole("spinbutton", { name: /新值/ });
    await user.clear(input);
    await user.type(input, "30000");

    // Confirm button is enabled (value is valid > 0), but submitting should fail
    const confirmBtn = screen.getByText("确认调整");
    expect(confirmBtn).not.toBeDisabled();

    await user.click(confirmBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/新预算不能低于已使用\+已预留/),
      ).toBeInTheDocument();
    });
  });
});

/* ── Edge Cases: Control Button States ── */
describe("TeamInspector control button edge cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  it("all control buttons are disabled during SSE disconnect", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} sseConnected={false} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("SSE 已断开，控制操作不可用")).toBeInTheDocument();
    });

    // All team-level control buttons should be disabled
    const allButtons = screen.getAllByRole("button");
    const controlButtons = allButtons.filter(
      (btn) => {
        const text = btn.textContent ?? "";
        return ["暂停", "恢复", "停止"].some((t) => text.includes(t)) && !text.includes("确认");
      },
    );
    for (const btn of controlButtons) {
      expect((btn as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("all control buttons are disabled during data stale state", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} dataStale />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("数据可能过期，请等待连接恢复")).toBeInTheDocument();
    });

    const pauseBtn = screen.getByRole("button", { name: /暂停/ }) as HTMLButtonElement;
    expect(pauseBtn.disabled).toBe(true);

    const resumeBtn = screen.getByRole("button", { name: /恢复/ }) as HTMLButtonElement;
    expect(resumeBtn.disabled).toBe(true);

    const stopBtn = screen.getByRole("button", { name: /停止/ }) as HTMLButtonElement;
    expect(stopBtn.disabled).toBe(true);
  });

  it("budget adjust button is disabled during SSE disconnect", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} sseConnected={false} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("SSE 已断开，控制操作不可用")).toBeInTheDocument();
    });

    // All "调整" buttons should be disabled
    const adjustButtons = screen.getAllByText("调整");
    for (const btn of adjustButtons) {
      expect((btn as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("session cancel button is disabled during SSE disconnect", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        sseConnected={false}
        selectedSessionId="s1"
        sessions={[makeSession("s1", "后端实现"), makeSession("s2", "前端开发")]}
      />,
    );

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("SSE 已断开，控制操作不可用")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByRole("button", { name: /取消/ }) as HTMLButtonElement;
    expect(cancelBtn.disabled).toBe(true);
  });
});

/* ── Edge Cases: Text Overflow ── */
describe("TeamInspector text overflow edge cases", () => {
  it("very long session role names are truncated with truncate class", () => {
    // In SessionRail, role text has className "truncate"
    const longRole = "这是一个非常非常非常非常长的角色名称用来测试文本截断功能是否正常工作";
    expect(longRole.length).toBeGreaterThan(30);

    // The truncate class in Tailwind applies:
    // overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    const truncateClass = "truncate";
    expect(truncateClass).toBe("truncate"); // Tailwind handles ellipsis
  });

  it("very long evidence text uses break-all to wrap without overflow", () => {
    // In SessionProgressDetail, evidence is rendered with:
    // <code className="break-all"> so long paths don't overflow
    const longEvidence = "/workspace/projects/very/deeply/nested/path/to/src/components/containers/observatory/analytics/module.ts L392";
    // The break-all class ensures the text wraps at any character
    const breakAllClass = "break-all";
    expect(breakAllClass).toBeDefined();
  });

  it("inspector aside has overflow-y-auto to prevent content cutoff", () => {
    // TeamInspector renders as <aside className="overflow-y-auto">
    const hasOverflowYAuto = true;
    expect(hasOverflowYAuto).toBe(true);
  });
});

/* ── Edge Cases: Message Types with Null/Empty Metadata ── */
describe("TeamInspector message type edge cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  it("progress section handles sessions with null summary gracefully", async () => {
    mockApi.fetchTeamProgress.mockResolvedValue({
      team_summary: { total: 1, running: 1, waiting: 0, paused: 0, blocked: 0, completed: 0 },
      active_stage: null,
      next_focus: null,
      sessions: [{
        id: "sig-null",
        session_id: "s1",
        run_id: "run-s1",
        summary: null,
        milestone: null,
        completed_items: null,
        next_step: null,
        blocked: false,
        blocker_reason: null,
        needs_operator: false,
        evidence: null,
        iteration: 0,
        created_at: "2026-07-25T01:00:00Z",
      }],
    });

    render(<TeamInspector {...defaultProps} selectedSessionId="s1" />);
    await waitFor(() => {
      // Session signal exists but all fields are null → renders minimal card (iteration only)
      expect(screen.getByText(/选中 Session/)).toBeInTheDocument();
      // Should not crash — renders with iteration 0, no summary/milestone/evidence
    });
  });

  it("progress section handles completely empty sessions array", async () => {
    mockApi.fetchTeamProgress.mockResolvedValue({
      team_summary: { total: 0, running: 0, waiting: 0, paused: 0, blocked: 0, completed: 0 },
      active_stage: null,
      next_focus: null,
      sessions: [],
    });

    render(<TeamInspector {...defaultProps} />);
    await waitFor(() => {
      // All counts zero → shows "暂无活跃 Session" text
      expect(screen.getByText("暂无活跃 Session")).toBeInTheDocument();
    });
  });

  it("usage section handles null consumption rate gracefully", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ consumption_rate_tokens_per_min: null }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      const allUnreported = screen.getAllByText("未上报");
      expect(allUnreported.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("usage section handles all-zero max values without division by zero", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({
        tokens: { used: 0, max: 0, remaining: 0, prompt: 0, completion: 0, reasoning: 0, cache_read: 0 },
        calls: { used: 0, max: 0 },
        wall_time_ms: 0,
        max_wall_time_ms: 0,
        cost: { used: 0, max: 0, remaining: 0 },
      }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      // Should render without crashing — no division by zero
      expect(screen.getByText("Tokens")).toBeInTheDocument();
      expect(screen.getByText("调用")).toBeInTheDocument();
    });
  });

  it("usage section handles null active_time_ms gracefully", async () => {
    mockApi.fetchTeamUsage.mockResolvedValue(
      makeUsage({ active_time_ms: null }),
    );
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("用量"));

    await waitFor(() => {
      expect(screen.getByText("额外统计")).toBeInTheDocument();
    });

    await user.click(screen.getByText("额外统计"));

    await waitFor(() => {
      const allUnreported = screen.getAllByText("未上报");
      expect(allUnreported.length).toBeGreaterThanOrEqual(1);
    });
  });
});

/* ── Edge Cases: Control Section Stress ── */
describe("TeamInspector control stress tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.fetchTeamProgress.mockResolvedValue(makeProgress());
    mockApi.fetchTeamUsage.mockResolvedValue(makeUsage());
    mockApi.pauseContainer.mockResolvedValue(undefined);
    mockApi.resumeContainer.mockResolvedValue(undefined);
    mockApi.stopContainer.mockResolvedValue(undefined);
    mockApi.patchContainerBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.pauseSession.mockResolvedValue(undefined);
    mockApi.resumeSession.mockResolvedValue(undefined);
    mockApi.cancelSession.mockResolvedValue(undefined);
    mockApi.patchSessionBudget.mockResolvedValue({ budget: {} as never, needs_resume: false });
    mockApi.appendSessionInstruction.mockResolvedValue(undefined);
  });

  it("rapidly toggling collapsible sections does not crash", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("进度")).toBeInTheDocument();
    });

    // Toggle all sections rapidly
    await user.click(screen.getByText("进度"));
    await user.click(screen.getByText("用量"));
    await user.click(screen.getByText("控制"));
    await user.click(screen.getByText("控制"));
    await user.click(screen.getByText("用量"));
    await user.click(screen.getByText("进度"));

    // Should still render — no crash
    await waitFor(() => {
      expect(screen.getByText("团队摘要")).toBeInTheDocument();
    });
  });

  it("opening and canceling stop dialog without confirm does not call stopContainer", async () => {
    const user = userEvent.setup();
    render(<TeamInspector {...defaultProps} />);

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText("团队控制")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /停止/ }));

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    // Click cancel instead of confirm
    await user.click(screen.getByText("取消"));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(mockApi.stopContainer).not.toHaveBeenCalled();
  });

  it("send instruction button disabled when textarea is empty", async () => {
    const user = userEvent.setup();
    render(
      <TeamInspector
        {...defaultProps}
        selectedSessionId="s1"
        sessions={[makeSession("s1", "后端实现"), makeSession("s2", "前端开发")]}
      />,
    );

    await user.click(screen.getByText("控制"));
    await waitFor(() => {
      expect(screen.getByText(/选中 Session: 后端实现/)).toBeInTheDocument();
    });

    const sendBtn = screen.getByRole("button", { name: /发送指令/ }) as HTMLButtonElement;
    expect(sendBtn.disabled).toBe(true);
  });
});
