import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import type {
  BudgetDetail,
  ContainerTeamInfo,
  LlmCall,
  RunDetail,
  SessionProgressSignal,
} from "@/lib/types";

// ---- Mocks ----

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => {
    const { className, ...rest } = props;
    return (
      <a href={href as string} className={className as string} {...rest}>
        {children as React.ReactNode}
      </a>
    );
  },
}));

const apiFetchMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

const fetchEventsMock = vi.fn();
vi.mock("@/lib/events", () => ({
  approvalIdOf: vi.fn().mockReturnValue(null),
  fetchEvents: (...args: unknown[]) => fetchEventsMock(...args),
}));

// Mock child components to avoid deep rendering
vi.mock("@/components/ApprovalModal", () => ({
  default: () => <div data-testid="approval-modal" />,
}));
vi.mock("@/components/BudgetView", () => ({
  default: () => <div data-testid="budget-view" />,
}));
vi.mock("@/components/LlmCallsTable", () => ({
  default: () => <div data-testid="llm-calls-table" />,
}));
vi.mock("@/components/Timeline", () => ({
  default: () => <div data-testid="timeline" />,
}));
vi.mock("@/components/TokenObservatory", () => ({
  default: () => <div data-testid="token-observatory" />,
}));

// ---- Test Helpers ----

function mockRunDetail(overrides: Partial<RunDetail["run"]> = {}): RunDetail {
  return {
    run: {
      id: "run-1",
      task_id: "task-1",
      attempt_no: 1,
      strategy: "fixed",
      status: "EXECUTING",
      current_phase: "modify",
      pressure_mode: "NORMAL",
      iteration: 4,
      started_at: "2026-08-01T01:00:00Z",
      finished_at: null,
      deadline_at: null,
      active_runtime_ms: 720_000,
      error: null,
      model_config: null,
      ...overrides,
    },
    task: {
      id: "task-1",
      name: "修复支付对账 Bug",
      description: "修复对账差异",
      workdir: "/workspace/billing",
      acceptance_criteria: "全部测试通过",
      template: "fix_bug",
      require_approval: false,
    },
    budget: {
      max_total_tokens: 200_000,
      max_wall_time_seconds: 3600,
      max_active_runtime_seconds: 1800,
      max_llm_calls: 80,
      max_cost: 15,
      max_parallel_llm_calls: 2,
      used_tokens: 45_000,
      used_cost: 2.83,
      used_calls: 34,
      reserved_tokens: 5_000,
      reserved_cost: 0.15,
      reserved_calls: 2,
    },
  };
}

function mockBudgetDetail(): BudgetDetail {
  return {
    budget: {
      max_total_tokens: 200_000,
      max_wall_time_seconds: 3600,
      max_active_runtime_seconds: 1800,
      max_llm_calls: 80,
      max_cost: 15,
      max_parallel_llm_calls: 2,
      used_tokens: 45_000,
      used_cost: 2.83,
      used_calls: 34,
      reserved_tokens: 5_000,
      reserved_cost: 0.15,
      reserved_calls: 2,
    },
    phases: [],
    reallocations: [],
  };
}

function mockContainerInfo(overrides: Partial<ContainerTeamInfo> = {}): ContainerTeamInfo {
  return {
    id: "container-1",
    name: "多会话支付修复",
    lifecycle_state: "active",
    team_status: "运行中",
    ...overrides,
  };
}

function mockProgressSignal(overrides: Partial<SessionProgressSignal> = {}): SessionProgressSignal {
  return {
    id: "sig-1",
    session_id: "session-1",
    run_id: "run-1",
    summary: "已完成数据模型和迁移脚本",
    milestone: "数据模型完成",
    completed_items: ["迁移脚本", "模型定义"],
    next_step: "实现 API 路由",
    blocked: false,
    blocker_reason: null,
    needs_operator: false,
    evidence: "models.py L392",
    iteration: 3,
    created_at: "2026-08-01T01:05:00Z",
    ...overrides,
  };
}

function resolveApiCalls(run: RunDetail, budget?: BudgetDetail, calls: LlmCall[] = [], container?: ContainerTeamInfo | null, signal?: { signals: SessionProgressSignal[] } | null) {
  apiFetchMock.mockImplementation((path: string) => {
    // 精确匹配 run 详情（不含子路径）
    if (path === `/api/runs/${run.run.id}` || path === `/api/runs/${run.run.id}/`) {
      return Promise.resolve(run);
    }
    if (path.startsWith("/api/runs/") && path.endsWith("/llm-calls")) {
      return Promise.resolve(calls);
    }
    if (path.startsWith("/api/runs/") && path.endsWith("/budget")) {
      return Promise.resolve(budget ?? mockBudgetDetail());
    }
    if (path.startsWith("/api/work-containers/")) {
      if (container === null) return Promise.reject(new Error("Not found"));
      return Promise.resolve(container ?? mockContainerInfo());
    }
    if (path.startsWith("/api/sessions/") && path.includes("/progress-signals")) {
      return Promise.resolve(signal ?? { signals: [] });
    }
    return Promise.resolve({});
  });
  fetchEventsMock.mockResolvedValue({ events: [] });
}

import { useParams } from "next/navigation";
import RunDetailPage from "@/app/runs/[id]/page";

async function renderPage(runId = "run-1") {
  (useParams as ReturnType<typeof vi.fn>).mockReturnValue({ id: runId });
  const result = render(<RunDetailPage />);
  await waitFor(() => {
    expect(screen.queryByText("无法打开运行指挥台")).not.toBeInTheDocument();
  }, { timeout: 3000 });
  return result;
}

/** 等待团队上下文加载完成：容器横幅或面包装已更新。 */
async function waitForTeamContext(expectPresent: boolean) {
  if (expectPresent) {
    await waitFor(() => {
      expect(screen.getByText(/此 Run 属于团队/)).toBeInTheDocument();
    }, { timeout: 3000 });
  }
}

// ---- Tests ----

describe("Run 页面 — 团队上下文 (Group 13)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useParams as ReturnType<typeof vi.fn>).mockReturnValue({ id: "run-1" });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe("独立 Run（无容器上下文）", () => {
    it("面包装显示「任务工作台」而非团队层级", async () => {
      const run = mockRunDetail({ work_container_id: undefined, work_session_id: undefined, work_session_role: undefined });
      resolveApiCalls(run);
      await renderPage();
      expect(screen.getByText("任务工作台")).toBeInTheDocument();
      expect(screen.queryByText("Agent Team")).not.toBeInTheDocument();
    });

    it("不显示团队状态横幅", async () => {
      const run = mockRunDetail({ work_container_id: undefined });
      resolveApiCalls(run);
      await renderPage();
      expect(screen.queryByText(/此 Run 属于团队/)).not.toBeInTheDocument();
    });

    it("不显示 Session 进度信号区块", async () => {
      const run = mockRunDetail({ work_container_id: undefined });
      resolveApiCalls(run);
      await renderPage();
      expect(screen.queryByText("Session 进度信号")).not.toBeInTheDocument();
    });

    it("保留所有现有的核心功能区块", async () => {
      const run = mockRunDetail({ work_container_id: undefined });
      resolveApiCalls(run);
      await renderPage();
      expect(screen.getByText("当前活动")).toBeInTheDocument();
      expect(screen.getByText("预算健康")).toBeInTheDocument();
      // 面包装含「运行指挥台」
      expect(screen.getByText("运行指挥台")).toBeInTheDocument();
    });
  });

  describe("团队 Run（有容器上下文）", () => {
    it("面包装显示完整层级：Agent Team → 容器名 → Session Role", async () => {
      const run = mockRunDetail({
        work_container_id: "container-1",
        work_session_id: "session-1",
        work_session_role: "后端实现",
      });
      const container = mockContainerInfo();
      resolveApiCalls(run, undefined, [], container);
      await renderPage();
      await waitForTeamContext(true);
      expect(screen.getByText("Agent Team")).toBeInTheDocument();
      // 面包装和横幅都会显示容器名，至少出现一次
      expect(screen.getByText("后端实现")).toBeInTheDocument();
      // 面包装链接可导航
      const teamLink = screen.getByText("Agent Team").closest("a");
      expect(teamLink).toHaveAttribute("href", "/containers");
      const containerLinks = screen.getAllByText("多会话支付修复");
      expect(containerLinks.length).toBeGreaterThanOrEqual(1);
      const containerLink = containerLinks[0].closest("a");
      expect(containerLink).toHaveAttribute("href", "/containers/container-1");
    });

    it("显示团队状态横幅（活跃容器）", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo({ lifecycle_state: "active", team_status: "运行中" });
      resolveApiCalls(run, undefined, [], container);
      await renderPage();
      await waitForTeamContext(true);
      expect(screen.getByText(/此 Run 属于团队/)).toBeInTheDocument();
      expect(screen.getByText("运行中")).toBeInTheDocument();
    });

    it("显示团队状态横幅（已暂停容器）", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo({ lifecycle_state: "paused", team_status: "已暂停" });
      resolveApiCalls(run, undefined, [], container);
      await renderPage();
      await waitForTeamContext(true);
      expect(screen.getByText("已暂停")).toBeInTheDocument();
    });

    it("container API 失败时不崩溃，隐藏横幅", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      resolveApiCalls(run, undefined, [], null); // null = API fails
      await renderPage();
      expect(screen.queryByText(/此 Run 属于团队/)).not.toBeInTheDocument();
      // 面包装仍显示但容器名为占位符
      expect(screen.getByText("…")).toBeInTheDocument();
    });
  });

  describe("Session 进度信号展示", () => {
    it("有进度信号时显示完整的进度信号面板", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const signal = mockProgressSignal();
      resolveApiCalls(run, undefined, [], container, { signals: [signal] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.getByText("Session 进度信号")).toBeInTheDocument();
      expect(screen.getByText("已完成数据模型和迁移脚本")).toBeInTheDocument();
      expect(screen.getByText("数据模型完成")).toBeInTheDocument();
      expect(screen.getByText("实现 API 路由")).toBeInTheDocument();
      expect(screen.getByText("models.py L392")).toBeInTheDocument();
      expect(screen.getByText("未阻塞")).toBeInTheDocument();
      expect(screen.getByText("否")).toBeInTheDocument();
      expect(screen.getByText("第 3 轮")).toBeInTheDocument();
    });

    it("阻塞状态正确显示", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const signal = mockProgressSignal({
        blocked: true,
        blocker_reason: "等待 API 契约确认",
      });
      resolveApiCalls(run, undefined, [], container, { signals: [signal] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.getByText("已阻塞")).toBeInTheDocument();
      expect(screen.getByText("等待 API 契约确认")).toBeInTheDocument();
    });

    it("需操作员标记正确显示", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const signal = mockProgressSignal({ needs_operator: true });
      resolveApiCalls(run, undefined, [], container, { signals: [signal] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.getByText("需要干预")).toBeInTheDocument();
    });

    it("缺失字段显示「未上报」而非 0 或空", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const signal = mockProgressSignal({
        summary: null,
        milestone: null,
        next_step: null,
        evidence: null,
        blocked: false,
        blocker_reason: null,
      });
      resolveApiCalls(run, undefined, [], container, { signals: [signal] });
      await renderPage();
      await waitForTeamContext(true);

      // 四个 "未上报" 分别对应 summary, milestone, next_step, evidence
      const unreported = screen.getAllByText("未上报");
      expect(unreported).toHaveLength(4);
    });

    it("无进度信号时不显示进度面板", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      resolveApiCalls(run, undefined, [], container, { signals: [] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.queryByText("Session 进度信号")).not.toBeInTheDocument();
    });

    it("进度 API 失败时不崩溃，不显示面板", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      // 让 progress API 返回 rejected
      apiFetchMock.mockImplementation((path: string) => {
        if (path === `/api/runs/${run.run.id}`) return Promise.resolve(run);
        if (path.startsWith("/api/runs/") && path.endsWith("/llm-calls")) return Promise.resolve([]);
        if (path.startsWith("/api/runs/") && path.endsWith("/budget")) return Promise.resolve(mockBudgetDetail());
        if (path.startsWith("/api/work-containers/")) return Promise.resolve(container);
        if (path.startsWith("/api/sessions/") && path.includes("/progress-signals")) return Promise.reject(new Error("Not found"));
        return Promise.resolve({});
      });
      fetchEventsMock.mockResolvedValue({ events: [] });

      await renderPage();
      await waitForTeamContext(true);
      expect(screen.queryByText("Session 进度信号")).not.toBeInTheDocument();
    });

    it("返回多个进度信号时取最新的（last element）", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const older = mockProgressSignal({ id: "sig-old", iteration: 1, summary: "旧进度" });
      const newer = mockProgressSignal({ id: "sig-new", iteration: 3, summary: "新进度" });
      resolveApiCalls(run, undefined, [], container, { signals: [older, newer] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.getByText("新进度")).toBeInTheDocument();
      expect(screen.queryByText("旧进度")).not.toBeInTheDocument();
      expect(screen.getByText("第 3 轮")).toBeInTheDocument();
    });
  });

  describe("所有功能在团队上下文中仍然正常工作", () => {
    it("TokenObservatory 和 BudgetView 仍然渲染", async () => {
      const run = mockRunDetail({ work_container_id: "container-1", work_session_id: "session-1", work_session_role: "后端实现" });
      const container = mockContainerInfo();
      const signal = mockProgressSignal();
      resolveApiCalls(run, undefined, [], container, { signals: [signal] });
      await renderPage();
      await waitForTeamContext(true);

      expect(screen.getByTestId("token-observatory")).toBeInTheDocument();
      // 预算健康区块仍然存在
      expect(screen.getByText("预算健康")).toBeInTheDocument();
    });
  });
});
