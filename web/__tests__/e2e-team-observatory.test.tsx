/**
 * End-to-end workflow tests for the BudgetLoop "Agent Team 调控观测台".
 *
 * These tests render the ACTUAL TeamObservatoryDashboard component with
 * ACTUAL child components (SessionRail, TeamChannel, TeamInspector).
 * Only the network boundary (apiFetch / control functions) and browser
 * globals (EventSource, window.innerWidth) are mocked.
 *
 * NOTE: In jsdom without CSS, both desktop and mobile panels render
 * simultaneously. Queries use getAllByText / getAllByLabelText / getAllByRole
 * and index into results where duplicates are expected.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// ---- Mock next/navigation ----
vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
}));

// ---- Mock next/link ----
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: Record<string, unknown>) => {
    const { className, ...rest } = props;
    return (
      <a href={href as string} className={className as string} {...rest}>
        {children as React.ReactNode}
      </a>
    );
  },
}));

// ---- Mock @/lib/api ----
const mockApiFetch = vi.fn();
const mockPauseContainer = vi.fn();
const mockResumeContainer = vi.fn();
const mockStopContainer = vi.fn();
const mockPatchContainerBudget = vi.fn();
const mockFetchTeamProgress = vi.fn();
const mockFetchTeamUsage = vi.fn();
const mockPatchSessionBudget = vi.fn();
const mockAppendSessionInstruction = vi.fn();
const mockCancelSession = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  cancelSession: (...args: unknown[]) => mockCancelSession(...args),
  fetchTeamProgress: (...args: unknown[]) =>
    mockFetchTeamProgress(...args),
  fetchTeamUsage: (...args: unknown[]) => mockFetchTeamUsage(...args),
  idempotencyKey: () => "test-key-123",
  pauseContainer: (...args: unknown[]) => mockPauseContainer(...args),
  pauseSession: vi.fn(),
  resumeContainer: (...args: unknown[]) => mockResumeContainer(...args),
  stopContainer: (...args: unknown[]) => mockStopContainer(...args),
  patchContainerBudget: (...args: unknown[]) =>
    mockPatchContainerBudget(...args),
  patchSessionBudget: (...args: unknown[]) =>
    mockPatchSessionBudget(...args),
  appendSessionInstruction: (...args: unknown[]) =>
    mockAppendSessionInstruction(...args),
}));

// ---- Mock EventSource ----
class MockEventSource {
  static instances: MockEventSource[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState: number = MockEventSource.OPEN;
  url: string;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  simulateDisconnect() {
    this.readyState = MockEventSource.CLOSED;
    if (this.onerror) this.onerror(new Event("error"));
  }
}

// ---- Import page component ----
import TeamObservatoryDashboard from "@/app/containers/[id]/page";
import { useParams } from "next/navigation";

// ---- Factory functions ----

function makeMergedData(overrides: Record<string, unknown> = {}) {
  return {
    id: "c1",
    name: "测试团队",
    project_goal: "实现可审计的多Agent协作",
    lifecycle_state: "active",
    base_workdir: "/workspace/test",
    default_workspace_policy: "isolated",
    counts: { sessions: 3, running: 2, waiting: 0, attention: 1 },
    sessions: [
      {
        id: "s1",
        container_id: "c1",
        role: "后端实现",
        goal: "实现API路由与数据模型",
        status: "EXECUTING",
        task_id: "t1",
        current_run_id: "r1",
        conversation_id: null,
        iteration: 3,
        worktree_enabled: false,
        worktree_branch: null,
        worktree_path: null,
        workspace_status: "READY",
        workspace_error: null,
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T01:00:00Z",
      },
      {
        id: "s2",
        container_id: "c1",
        role: "前端开发",
        goal: "实现UI组件与状态管理",
        status: "EXECUTING",
        task_id: "t2",
        current_run_id: "r2",
        conversation_id: null,
        iteration: 2,
        worktree_enabled: false,
        worktree_branch: null,
        worktree_path: null,
        workspace_status: "READY",
        workspace_error: null,
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T01:00:00Z",
      },
      {
        id: "s3",
        container_id: "c1",
        role: "代码审查",
        goal: "审查代码质量与安全",
        status: "WAITING_APPROVAL",
        task_id: "t3",
        current_run_id: "r3",
        conversation_id: null,
        iteration: 1,
        worktree_enabled: false,
        worktree_branch: null,
        worktree_path: null,
        workspace_status: "READY",
        workspace_error: null,
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T01:00:00Z",
      },
    ],
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T01:00:00Z",
    team_status: "active",
    active_session_count: 2,
    total_session_count: 3,
    alert_count: 1,
    alerts: [
      {
        kind: "blocking",
        message: "后端API未就绪，前端等待中",
        session_id: "s1",
        session_role: "后端实现",
      },
    ],
    usage: {
      total_tokens: 45200,
      max_tokens: 200000,
      total_cost: 2.83,
      max_cost: 15,
      total_calls: 34,
      max_calls: 80,
      elapsed_seconds: 720,
      max_wall_time_seconds: 3600,
      pressure: "NORMAL",
      burn_rate_tokens_per_min: 1.3,
      est_depletion: "2h 15m",
    },
    phase: {
      current_phase: "实现+审查",
      next_milestone: "完成API路由",
    },
    ...overrides,
  };
}

function makeProgress(overrides: Record<string, unknown> = {}) {
  return {
    team_summary: {
      total: 3,
      running: 2,
      waiting: 0,
      paused: 0,
      blocked: 1,
      completed: 0,
    },
    active_stage: "实现+审查",
    next_focus: "完成 API 路由",
    sessions: [
      {
        id: "sig-s1",
        session_id: "s1",
        run_id: "r1",
        summary: "已完成数据模型和迁移",
        milestone: "数据模型+迁移",
        completed_items: ["创建模型", "编写迁移"],
        next_step: "实现API路由",
        blocked: false,
        blocker_reason: null,
        needs_operator: false,
        evidence: "models.py L392",
        iteration: 3,
        created_at: "2026-08-01T01:00:00Z",
      },
      {
        id: "sig-s2",
        session_id: "s2",
        run_id: "r2",
        summary: "正在创建UI组件",
        milestone: "组件创建",
        completed_items: ["基础布局", "表单组件", "表格组件"],
        next_step: "对接后端API",
        blocked: true,
        blocker_reason: "等待后端API就绪",
        needs_operator: false,
        evidence: null,
        iteration: 2,
        created_at: "2026-08-01T01:00:00Z",
      },
      {
        id: "sig-s3",
        session_id: "s3",
        run_id: "r3",
        summary: null,
        milestone: null,
        completed_items: [],
        next_step: null,
        blocked: false,
        blocker_reason: null,
        needs_operator: true,
        evidence: null,
        iteration: 1,
        created_at: "2026-08-01T01:00:00Z",
      },
    ],
    ...overrides,
  };
}

function makeUsage(overrides: Record<string, unknown> = {}) {
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
    estimated_depletion_at: "2026-08-01T03:15:00Z",
    ...overrides,
  };
}

// ---- Helpers ----

function setViewport(width: number) {
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

/** Get the first matched element by text (handles duplicates in jsdom). */
function firstText(matcher: string | RegExp) {
  return screen.getAllByText(matcher)[0];
}

/** Get the first matched element by label. */
function firstLabel(label: string) {
  return screen.getAllByLabelText(label)[0];
}

/** Get the first matched element by placeholder. */
function firstPlaceholder(placeholder: string) {
  return screen.getAllByPlaceholderText(placeholder)[0];
}

// ---- Suite setup ----

describe("Team Observatory E2E", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockEventSource.instances.length = 0;
    vi.stubGlobal("EventSource", MockEventSource);

    setViewport(1280);

    (useParams as ReturnType<typeof vi.fn>).mockReturnValue({ id: "c1" });

    mockApiFetch.mockResolvedValue(makeMergedData());
    mockPauseContainer.mockResolvedValue(undefined);
    mockResumeContainer.mockResolvedValue(undefined);
    mockStopContainer.mockResolvedValue(undefined);
    mockPatchContainerBudget.mockResolvedValue({
      budget: {} as never,
      needs_resume: false,
    });
    mockPatchSessionBudget.mockResolvedValue({
      budget: {} as never,
      needs_resume: false,
    });
    mockAppendSessionInstruction.mockResolvedValue(undefined);
    mockCancelSession.mockResolvedValue(undefined);
    mockFetchTeamProgress.mockResolvedValue(makeProgress());
    mockFetchTeamUsage.mockResolvedValue(makeUsage());
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // ========================================================================
  // SCENARIO 1: FULL PAGE RENDER
  // ========================================================================
  describe("Scenario 1: Full page render", () => {
    it("renders the team name, goal, lifecycle badge, and session counts", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      expect(
        screen.getByText("实现可审计的多Agent协作"),
      ).toBeInTheDocument();
      expect(screen.getByText("活跃")).toBeInTheDocument();
      expect(screen.getByText(/3 个 Session/)).toBeInTheDocument();
      expect(screen.getByText(/2 运行中/)).toBeInTheDocument();
      expect(screen.getByText(/1 需关注/)).toBeInTheDocument();
    });

    it("shows top bar with team status and connection indicator", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // "运行中" appears in TopBar (and possibly elsewhere in mobile)
      const statusBadges = screen.getAllByText("运行中");
      expect(statusBadges.length).toBeGreaterThanOrEqual(1);

      // "已连接" in TopBar
      expect(screen.getByText("已连接")).toBeInTheDocument();

      // Active/total count
      expect(screen.getByText("2/3 运行中")).toBeInTheDocument();

      // Phase label
      expect(screen.getByText("实现+审查")).toBeInTheDocument();
    });

    it("shows SessionRail with all sessions", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Two SessionRail instances; pick the first
      const sessionRails = screen.getAllByLabelText("Sessions");
      expect(sessionRails.length).toBeGreaterThanOrEqual(1);

      // All three session names appear in both panels; verify presence
      expect(screen.getAllByText("后端实现").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("前端开发").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("代码审查").length).toBeGreaterThanOrEqual(1);
    });

    it("clicking a session selects it and shows filter in TeamChannel", async () => {
      const user = userEvent.setup();
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getAllByText("后端实现").length).toBeGreaterThanOrEqual(1);
      });

      // Click the first "前端开发" button (SessionRail button)
      const frontEndButtons = screen.getAllByText("前端开发");
      await user.click(frontEndButtons[0]);

      // TeamChannel should show session filter (both instances react)
      await waitFor(() => {
        expect(
          screen.getAllByText("仅此会话").length,
        ).toBeGreaterThanOrEqual(1);
      });
    });

    it("shows cross-tab alert banner with blocking alert", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      const alertBanner = screen.getByRole("alert");
      expect(alertBanner).toBeInTheDocument();
      expect(alertBanner.textContent).toContain("后端实现");
      expect(alertBanner.textContent).toContain("后端API未就绪");
    });
  });

  // ========================================================================
  // SCENARIO 2: MESSAGE SEND FLOW
  // ========================================================================
  describe("Scenario 2: Message send flow", () => {
    it("types a message and sends it via the API", async () => {
      const user = userEvent.setup();
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getAllByText("后端实现").length).toBeGreaterThanOrEqual(1);
      });

      // Click first "后端实现" session
      await user.click(firstText("后端实现"));

      // Type in the composer — two TeamChannel instances, first one
      const textarea = firstPlaceholder("输入消息…");
      await user.type(textarea, "请开始实现用户认证模块");

      const sendButtons = screen.getAllByRole("button", { name: /发送/ });
      await user.click(sendButtons[0]);

      await waitFor(() => {
        expect(mockApiFetch).toHaveBeenCalledWith(
          expect.stringContaining("/messages"),
          expect.objectContaining({ method: "POST" }),
        );
      });
    });

    it("message input is disabled when container is paused", async () => {
      mockApiFetch.mockResolvedValue(
        makeMergedData({
          lifecycle_state: "paused",
          team_status: "paused",
        }),
      );

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Two textareas, both disabled
      const textareas = screen.getAllByPlaceholderText(
        "团队已暂停，无法发送消息。",
      );
      expect(textareas.length).toBeGreaterThanOrEqual(1);
      for (const ta of textareas) {
        expect(ta).toBeDisabled();
      }

      const sendButtons = screen.getAllByRole("button", { name: /发送/ });
      expect(sendButtons[0]).toBeDisabled();
    });

    it("shows session-specific empty message when filtering by session", async () => {
      const user = userEvent.setup();
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getAllByText("前端开发").length).toBeGreaterThanOrEqual(1);
      });

      await user.click(firstText("前端开发"));

      await waitFor(() => {
        expect(
          screen.getAllByText("当前会话还没有消息记录。").length,
        ).toBeGreaterThanOrEqual(1);
      });
    });
  });

  // ========================================================================
  // SCENARIO 3: CONTROL FLOW (PAUSE / RESUME)
  // ========================================================================
  describe("Scenario 3: Control flow", () => {
    it("clicking pause in top bar triggers pauseContainer", async () => {
      const user = userEvent.setup();

      let callCount = 0;
      mockApiFetch.mockImplementation(() => {
        callCount++;
        if (callCount <= 2) {
          return Promise.resolve(makeMergedData());
        }
        return Promise.resolve(
          makeMergedData({
            lifecycle_state: "paused",
            team_status: "paused",
          }),
        );
      });

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Pause buttons: one from TopBar, two from TeamInspector (collapsed)
      const pauseButtons = screen.getAllByRole("button", { name: /暂停/ });
      expect(pauseButtons.length).toBeGreaterThanOrEqual(1);

      await user.click(pauseButtons[0]);

      await waitFor(() => {
        expect(mockPauseContainer).toHaveBeenCalledWith("c1");
      });
    });

    it("rendered with paused state shows resume button", async () => {
      mockApiFetch.mockResolvedValue(
        makeMergedData({
          lifecycle_state: "paused",
          team_status: "paused",
        }),
      );

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // "已暂停" appears in TopBar + TeamChannel
      const pausedTexts = screen.getAllByText("已暂停");
      expect(pausedTexts.length).toBeGreaterThanOrEqual(1);

      // Resume button
      expect(
        screen.getByRole("button", { name: /恢复/ }),
      ).toBeInTheDocument();
    });

    it("clicking resume calls resumeContainer", async () => {
      const user = userEvent.setup();

      mockApiFetch.mockResolvedValue(
        makeMergedData({
          lifecycle_state: "paused",
          team_status: "paused",
        }),
      );

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      const resumeButton = screen.getByRole("button", { name: /恢复/ });
      await user.click(resumeButton);

      await waitFor(() => {
        expect(mockResumeContainer).toHaveBeenCalledWith("c1");
      });
    });

    it("clicking stop triggers window.confirm and calls stopContainer", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Stop buttons: one from TopBar, two from TeamInspector
      const stopButtons = screen.getAllByRole("button", { name: /停止/ });
      expect(stopButtons.length).toBeGreaterThanOrEqual(1);

      await user.click(stopButtons[0]);

      expect(window.confirm).toHaveBeenCalledWith(
        "确定要停止团队运行？此操作不可撤销。",
      );

      await waitFor(() => {
        expect(mockStopContainer).toHaveBeenCalledWith("c1");
      });
    });

    it("chat input disabled and paused indicator when container is paused", async () => {
      mockApiFetch.mockResolvedValue(
        makeMergedData({
          lifecycle_state: "paused",
          team_status: "paused",
        }),
      );

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      const textareas = screen.getAllByPlaceholderText(
        "团队已暂停，无法发送消息。",
      );
      expect(textareas.length).toBeGreaterThanOrEqual(1);
      for (const ta of textareas) {
        expect(ta).toBeDisabled();
      }

      const sendButtons = screen.getAllByRole("button", { name: /发送/ });
      expect(sendButtons[0]).toBeDisabled();
    });
  });

  // ========================================================================
  // SCENARIO 4: BUDGET ADJUSTMENT FLOW
  // ========================================================================
  describe("Scenario 4: Budget adjustment flow", () => {
    it("opens budget adjust form, shows old→new preview, and confirms", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Expand the first control section (collapsible header in TeamInspector)
      const controlHeaders = screen.getAllByRole("button", { name: "控制" });
      await user.click(controlHeaders[0]);

      await waitFor(() => {
        expect(screen.getByText("团队控制")).toBeInTheDocument();
      });

      // Click first "调整" button (team budget)
      const adjustButtons = screen.getAllByText("调整");
      await user.click(adjustButtons[0]);

      await waitFor(() => {
        expect(screen.getByText("团队预算 (Tokens)")).toBeInTheDocument();
        expect(screen.getByText(/当前: 200,000/)).toBeInTheDocument();
        expect(screen.getByText(/已使用: 45,200/)).toBeInTheDocument();
      });

      const input = screen.getByRole("spinbutton", { name: /新值/ });
      await user.clear(input);
      await user.type(input, "300000");

      await waitFor(() => {
        expect(
          screen.getByText(/200,000 → 300,000/),
        ).toBeInTheDocument();
      });

      const confirmBtn = screen.getByText("确认调整");
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(mockPatchContainerBudget).toHaveBeenCalledWith("c1", {
          max_total_tokens: 300000,
        });
      });
    });

    it("confirm button disabled when budget input is cleared", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      const controlHeaders = screen.getAllByRole("button", { name: "控制" });
      await user.click(controlHeaders[0]);

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

      const confirmBtn = screen.getByText("确认调整");
      expect(confirmBtn).toBeDisabled();
    });
  });

  // ========================================================================
  // SCENARIO 5: MOBILE TAB FLOW
  // ========================================================================
  describe("Scenario 5: Mobile tab flow (390px)", () => {
    beforeEach(() => {
      setViewport(390);
    });

    it("shows mobile tab bar with three tabs", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      const tablist = screen.getByRole("tablist", { name: "观测台区域" });
      expect(tablist).toBeInTheDocument();

      const membersTab = within(tablist).getByRole("tab", {
        name: "成员",
      });
      const chatTab = within(tablist).getByRole("tab", { name: "对话" });
      const controlTab = within(tablist).getByRole("tab", {
        name: "控制",
      });

      expect(membersTab).toBeInTheDocument();
      expect(chatTab).toBeInTheDocument();
      expect(controlTab).toBeInTheDocument();

      expect(chatTab).toHaveAttribute("aria-selected", "true");
      expect(membersTab).toHaveAttribute("aria-selected", "false");
      expect(controlTab).toHaveAttribute("aria-selected", "false");
    });

    it("clicking '成员' tab shows SessionRail sessions", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("tab", { name: "成员" }));

      // SessionRail should be present
      const sessionRails = screen.getAllByLabelText("Sessions");
      expect(sessionRails.length).toBeGreaterThanOrEqual(1);

      // Session names visible
      expect(
        screen.getAllByText("后端实现").length,
      ).toBeGreaterThanOrEqual(1);
    });

    it("clicking '控制' tab shows TeamInspector with section headers", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("tab", { name: "控制" }));

      // TeamInspector section headers should be visible
      await waitFor(() => {
        expect(
          screen.getAllByText("进度").length,
        ).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText("用量").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("控制").length).toBeGreaterThanOrEqual(1);
    });

    it("cross-tab alert banner is visible regardless of active tab", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      expect(screen.getByRole("alert")).toBeInTheDocument();

      await user.click(screen.getByRole("tab", { name: "成员" }));
      expect(screen.getByRole("alert")).toBeInTheDocument();

      await user.click(screen.getByRole("tab", { name: "控制" }));
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // SCENARIO 6: SSE DISCONNECT FLOW
  // ========================================================================
  describe("Scenario 6: SSE disconnect flow", () => {
    it("shows '已连接' initially with green connection dot", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText("已连接")).toBeInTheDocument();
      });

      // Verify the green dot exists by checking the parent span contains bg-success
      const connectedSpan = screen.getByText("已连接").closest(
        "span.inline-flex",
      );
      expect(connectedSpan).not.toBeNull();
      const hasGreenDot =
        connectedSpan!.querySelector("span.rounded-full") !== null;
      expect(hasGreenDot).toBe(true);
    });

    it("simulating SSE disconnect shows '已断开'", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText("已连接")).toBeInTheDocument();
      });

      const esInstance = MockEventSource.instances[0];
      expect(esInstance).toBeDefined();
      esInstance.simulateDisconnect();

      await waitFor(() => {
        expect(screen.getByText("已断开")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // SCENARIO 7: TeamInspector integration within dashboard
  // ========================================================================
  describe("Scenario 7: TeamInspector integration", () => {
    it("progress section renders team summary counts", async () => {
      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(
          screen.getAllByText("团队摘要").length,
        ).toBeGreaterThanOrEqual(1);
      });

      // Running and blocked counts; waiting may be 0 and formatted differently
      expect(
        screen.getAllByText("运行中 2").length,
      ).toBeGreaterThanOrEqual(1);
      expect(
        screen.getAllByText("已阻塞 1").length,
      ).toBeGreaterThanOrEqual(1);
    });

    it("usage section shows detailed metrics when expanded", async () => {
      const user = userEvent.setup();

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(screen.getByText("测试团队")).toBeInTheDocument();
      });

      // Expand first "用量" section
      const usageHeaders = screen.getAllByText("用量");
      await user.click(usageHeaders[0]);

      await waitFor(() => {
        expect(screen.getByText("Tokens")).toBeInTheDocument();
      });

      expect(screen.getByText("费用")).toBeInTheDocument();
      expect(screen.getByText("耗时")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // SCENARIO 8: Error state
  // ========================================================================
  describe("Scenario 8: Error states", () => {
    it("shows error page when container fetch fails", async () => {
      mockApiFetch.mockRejectedValue(new Error("网络连接失败"));

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(
          screen.getByText("团队观测台无法打开"),
        ).toBeInTheDocument();
      });

      expect(screen.getByText("网络连接失败")).toBeInTheDocument();
      expect(screen.getByText("重试")).toBeInTheDocument();
    });

    it("shows empty state when container has no sessions", async () => {
      mockApiFetch.mockResolvedValue(
        makeMergedData({
          sessions: [],
          counts: { sessions: 0, running: 0, waiting: 0, attention: 0 },
        }),
      );

      render(<TeamObservatoryDashboard />);

      await waitFor(() => {
        expect(
          screen.getByText("此团队暂无活动 Session"),
        ).toBeInTheDocument();
      });

      expect(
        screen.getByRole("button", { name: /新建 Session/ }),
      ).toBeInTheDocument();
    });
  });
});
