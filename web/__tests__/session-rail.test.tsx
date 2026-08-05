import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TeamSessionRail } from "@/components/containers/TeamSessionRail";
import type { TeamSessionView } from "@/lib/types";

function makeSession(overrides: Partial<TeamSessionView> = {}): TeamSessionView {
  return {
    id: "s1",
    container_id: "c1",
    role: "后端实现",
    status: "EXECUTING",
    pressure_mode: "NORMAL",
    current_phase: "API路由实现",
    last_activity: "2026-08-05T01:00:00Z",
    blocked: false,
    needs_operator: false,
    budget_ratio: 0.25,
    ...overrides,
  };
}

describe("TeamSessionRail sort order", () => {
  /** session item buttons have aria-pressed; filter excludes other buttons (e.g. create) */
  function getSessionItemButtons(): HTMLElement[] {
    const all = screen.getAllByRole("button");
    return all.filter((btn) => btn.hasAttribute("aria-pressed"));
  }

  it("sorts CRITICAL first, then CONSERVATIVE, then NORMAL", () => {
    const sessions: TeamSessionView[] = [
      makeSession({ id: "n1", role: "正常A", pressure_mode: "NORMAL" }),
      makeSession({ id: "c1", role: "保守A", pressure_mode: "CONSERVATIVE" }),
      makeSession({ id: "cr1", role: "紧急A", pressure_mode: "CRITICAL" }),
      makeSession({ id: "n2", role: "正常B", pressure_mode: "NORMAL" }),
    ];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const items = getSessionItemButtons();
    // Check pressure badge text content (exact match via .badge selector)
    const getBadge = (btn: HTMLElement) => btn.querySelector(".badge")?.textContent ?? "";
    expect(getBadge(items[0])).toBe("紧急");
    expect(getBadge(items[1])).toBe("保守");
    expect(getBadge(items[2])).toBe("正常");
    expect(getBadge(items[3])).toBe("正常");
  });

  it("within same pressure tier, orders by last_activity descending (most recent first)", () => {
    const sessions: TeamSessionView[] = [
      makeSession({ id: "n1", role: "正常-旧", pressure_mode: "NORMAL", last_activity: "2026-08-05T00:00:00Z" }),
      makeSession({ id: "n2", role: "正常-新", pressure_mode: "NORMAL", last_activity: "2026-08-05T02:00:00Z" }),
    ];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const items = getSessionItemButtons();
    const first = within(items[0]).getByText("正常-新");
    const second = within(items[1]).getByText("正常-旧");
    expect(first).toBeInTheDocument();
    expect(second).toBeInTheDocument();
  });

  it("handles sessions with null last_activity gracefully (sorted to bottom)", () => {
    const sessions: TeamSessionView[] = [
      makeSession({ id: "n1", role: "有活动", pressure_mode: "NORMAL", last_activity: "2026-08-05T01:00:00Z" }),
      makeSession({ id: "n2", role: "无活动", pressure_mode: "NORMAL", last_activity: null }),
    ];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const items = getSessionItemButtons();
    expect(within(items[0]).getByText("有活动")).toBeInTheDocument();
    expect(within(items[1]).getByText("无活动")).toBeInTheDocument();
  });
});

describe("TeamSessionRail selection", () => {
  it("calls onSelect when a session is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const sessions = [makeSession({ id: "s1", role: "后端实现" })];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={onSelect} />);

    await user.click(screen.getByText("后端实现"));
    expect(onSelect).toHaveBeenCalledWith("s1");
  });

  it("highlights the selected session with accent background", () => {
    const sessions = [
      makeSession({ id: "s1", role: "选中" }),
      makeSession({ id: "s2", role: "未选中" }),
    ];

    render(<TeamSessionRail sessions={sessions} selectedId="s1" onSelect={vi.fn()} />);

    // aria-pressed="true" button is the selected session
    const selectedBtn = screen.getByRole("button", { pressed: true });
    const unselectedBtn = screen.getByRole("button", { pressed: false });

    // Selected has accent bg via Tailwind arbitrary value bg-accent/[0.055]
    expect(selectedBtn.className).toMatch(/bg-accent/);
    // Unselected does not have the accent bg
    expect(unselectedBtn.className).not.toMatch(/bg-accent/);
  });

  it("aria-pressed reflects selection state", () => {
    const sessions = [makeSession({ id: "s1", role: "测试角色" })];

    render(<TeamSessionRail sessions={sessions} selectedId="s1" onSelect={vi.fn()} />);

    const btn = screen.getByRole("button", { pressed: true });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("测试角色");

    // Re-render with different selectedId
    const { unmount } = render(<TeamSessionRail sessions={sessions} selectedId="s2" onSelect={vi.fn()} />);
    const btn2 = screen.getByRole("button", { pressed: false });
    expect(btn2).toBeInTheDocument();
    unmount();
  });
});

describe("TeamSessionRail alert indicators", () => {
  it("shows alert icon when blocked=true", () => {
    const sessions = [makeSession({ id: "s1", role: "阻塞会话", blocked: true })];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const alert = screen.getByLabelText("已阻塞");
    expect(alert).toBeInTheDocument();
  });

  it("shows alert icon when needs_operator=true", () => {
    const sessions = [makeSession({ id: "s1", role: "需操作员", needs_operator: true })];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const alert = screen.getByLabelText("需要操作员介入");
    expect(alert).toBeInTheDocument();
  });

  it("shows combined alert label when both blocked and needs_operator", () => {
    const sessions = [makeSession({ id: "s1", role: "双警报", blocked: true, needs_operator: true })];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const alert = screen.getByLabelText("阻塞且需要操作员介入");
    expect(alert).toBeInTheDocument();
  });

  it("does NOT show alert icon when neither blocked nor needs_operator", () => {
    const sessions = [makeSession({ id: "s1", role: "正常", blocked: false, needs_operator: false })];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    expect(screen.queryByLabelText("已阻塞")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("需要操作员介入")).not.toBeInTheDocument();
  });
});

describe("TeamSessionRail filter", () => {
  const sessions: TeamSessionView[] = [
    makeSession({ id: "normal", role: "正常会话", pressure_mode: "NORMAL", blocked: false, needs_operator: false }),
    makeSession({ id: "blocked", role: "阻塞会话", pressure_mode: "CRITICAL", blocked: true, needs_operator: false }),
    makeSession({ id: "needs-op", role: "需操作员", pressure_mode: "CONSERVATIVE", blocked: false, needs_operator: true }),
    makeSession({ id: "both", role: "阻塞且需操作员", pressure_mode: "CRITICAL", blocked: true, needs_operator: true }),
  ];

  it('shows all sessions when filter is "全部消息"', () => {
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("正常会话")).toBeInTheDocument();
    expect(screen.getByText("阻塞会话")).toBeInTheDocument();
    expect(screen.getByText("需操作员")).toBeInTheDocument();
    expect(screen.getByText("阻塞且需操作员")).toBeInTheDocument();
  });

  it('shows only sessions with needs_operator when filter is "@我的"', async () => {
    const user = userEvent.setup();
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("筛选 Session"), "mine");

    expect(screen.queryByText("正常会话")).not.toBeInTheDocument();
    expect(screen.queryByText("阻塞会话")).not.toBeInTheDocument();
    expect(screen.getByText("需操作员")).toBeInTheDocument();
    expect(screen.getByText("阻塞且需操作员")).toBeInTheDocument();
  });

  it('shows only blocked sessions when filter is "仅阻塞"', async () => {
    const user = userEvent.setup();
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("筛选 Session"), "blocked");

    expect(screen.queryByText("正常会话")).not.toBeInTheDocument();
    expect(screen.getByText("阻塞会话")).toBeInTheDocument();
    expect(screen.getByText("需操作员")).toBeInTheDocument();
    expect(screen.getByText("阻塞且需操作员")).toBeInTheDocument();
  });

  it("shows empty message when filter returns no results", async () => {
    const user = userEvent.setup();
    const onlyNormal = [makeSession({ id: "n1", role: "正常", blocked: false, needs_operator: false })];

    render(<TeamSessionRail sessions={onlyNormal} selectedId={null} onSelect={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("筛选 Session"), "blocked");
    expect(screen.getByText("没有阻塞的 Session")).toBeInTheDocument();
  });
});

describe("TeamSessionRail mobile rendering", () => {
  it("renders as a flat scrollable list without border-r sidebar styling", () => {
    const sessions = [makeSession({ id: "s1", role: "移动端" })];

    render(
      <TeamSessionRail
        sessions={sessions}
        selectedId={null}
        onSelect={vi.fn()}
        isMobile
      />,
    );

    // Mobile mode uses a div container, not an <aside>
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    // Should not have sidebar width classes
    const container = screen.getByLabelText("Session 列表");
    expect(container).toBeInTheDocument();
    expect(container.tagName).toBe("DIV");
  });

  it("has min-w-[390px] on mobile to respect minimum width", () => {
    const sessions = [makeSession()];

    render(
      <TeamSessionRail
        sessions={sessions}
        selectedId={null}
        onSelect={vi.fn()}
        isMobile
      />,
    );

    const container = screen.getByLabelText("Session 列表");
    expect(container.classList.contains("min-w-[390px]")).toBeTruthy();
  });

  it("desktop renders as an <aside> with w-72", () => {
    const sessions = [makeSession()];

    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    const aside = screen.getByRole("complementary");
    expect(aside).toBeInTheDocument();
    expect(aside.classList.contains("w-72")).toBeTruthy();
  });
});

describe("TeamSessionRail status dots", () => {
  it("uses bg-success (green) for RUNNING statuses", () => {
    const sessions = [makeSession({ id: "s1", role: "执行中", status: "EXECUTING" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const dot = screen.getByLabelText("状态: EXECUTING");
    expect(dot.classList.contains("bg-success")).toBeTruthy();
  });

  it("uses bg-warning (yellow) for PAUSED", () => {
    const sessions = [makeSession({ id: "s1", role: "已暂停", status: "PAUSED" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const dot = screen.getByLabelText("状态: PAUSED");
    expect(dot.classList.contains("bg-warning")).toBeTruthy();
  });

  it("uses bg-muted-foreground (gray) for PENDING (waiting)", () => {
    const sessions = [makeSession({ id: "s1", role: "等待中", status: "PENDING" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const dot = screen.getByLabelText("状态: PENDING");
    expect(dot.classList.contains("bg-muted-foreground")).toBeTruthy();
  });

  it("uses bg-critical (red) for FAILED/error", () => {
    const sessions = [makeSession({ id: "s1", role: "失败", status: "FAILED" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const dot = screen.getByLabelText("状态: FAILED");
    expect(dot.classList.contains("bg-critical")).toBeTruthy();
  });
});

describe("TeamSessionRail pressure badges", () => {
  it("shows green badge for NORMAL pressure", () => {
    const sessions = [makeSession({ pressure_mode: "NORMAL" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const badge = screen.getByText("正常");
    expect(badge.classList.contains("badge-success")).toBeTruthy();
  });

  it("shows yellow badge for CONSERVATIVE pressure", () => {
    const sessions = [makeSession({ pressure_mode: "CONSERVATIVE" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const badge = screen.getByText("保守");
    expect(badge.classList.contains("badge-warning")).toBeTruthy();
  });

  it("shows red badge for CRITICAL pressure", () => {
    const sessions = [makeSession({ pressure_mode: "CRITICAL" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const badge = screen.getByText("紧急");
    expect(badge.classList.contains("badge-critical")).toBeTruthy();
  });
});

describe("TeamSessionRail missing data", () => {
  it('displays "未上报" when current_phase is null', () => {
    const sessions = [makeSession({ role: "测试", current_phase: null })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("未上报")).toBeInTheDocument();
  });

  it("hides token bar when budget_ratio is undefined", () => {
    const sessions = [makeSession({ role: "无预算", budget_ratio: undefined })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    // ProgressBar renders a div with rounded-full overflow-hidden
    const container = screen.getByText("无预算").closest("button");
    const progressBars = container?.querySelectorAll(".overflow-hidden.rounded-full");
    expect(progressBars?.length ?? 0).toBe(0);
  });

  it("shows token bar when budget_ratio is provided", () => {
    const sessions = [makeSession({ role: "有预算", budget_ratio: 0.5 })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const container = screen.getByText("有预算").closest("button");
    const progressBars = container?.querySelectorAll(".overflow-hidden.rounded-full");
    expect(progressBars?.length ?? 0).toBeGreaterThan(0);
  });
});

describe("TeamSessionRail create session button", () => {
  it('shows "新建 Session" button when onCreateSession is provided', () => {
    const sessions = [makeSession()];
    render(
      <TeamSessionRail
        sessions={sessions}
        selectedId={null}
        onSelect={vi.fn()}
        onCreateSession={vi.fn()}
      />,
    );

    expect(screen.getByText("新建 Session")).toBeInTheDocument();
  });

  it("does NOT show create button when onCreateSession is not provided", () => {
    const sessions = [makeSession()];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);

    expect(screen.queryByText("新建 Session")).not.toBeInTheDocument();
  });
});

describe("TeamSessionRail current phase", () => {
  it("shows current_phase text when provided", () => {
    const sessions = [makeSession({ role: "后端", current_phase: "实现阶段3" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("实现阶段3")).toBeInTheDocument();
  });
});

/* ── Screen Reader Accessibility ── */
describe("TeamSessionRail screen reader", () => {
  it("session item buttons have aria-pressed reflecting selection", () => {
    const sessions = [makeSession({ id: "s1", role: "读屏测试" })];
    render(<TeamSessionRail sessions={sessions} selectedId="s1" onSelect={vi.fn()} />);
    const btn = screen.getByRole("button", { pressed: true });
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("unselected sessions have aria-pressed=false", () => {
    const sessions = [
      makeSession({ id: "s1", role: "已选" }),
      makeSession({ id: "s2", role: "未选" }),
    ];
    render(<TeamSessionRail sessions={sessions} selectedId="s1" onSelect={vi.fn()} />);
    const unselected = screen.getByRole("button", { pressed: false });
    expect(unselected).toHaveAttribute("aria-pressed", "false");
  });

  it("session items display role text for screen readers", () => {
    const sessions = [makeSession({ id: "s1", role: "后端实现" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("后端实现")).toBeInTheDocument();
  });

  it("alert icons have descriptive aria-labels for blocked state", () => {
    const sessions = [makeSession({ id: "s1", role: "阻塞中", blocked: true })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("已阻塞")).toBeInTheDocument();
  });

  it("alert icons have descriptive aria-labels for needs_operator state", () => {
    const sessions = [makeSession({ id: "s1", role: "需关注", needs_operator: true })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("需要操作员介入")).toBeInTheDocument();
  });

  it("alert icons have combined aria-label when both blocked and needs_operator", () => {
    const sessions = [makeSession({ id: "s1", role: "双警报", blocked: true, needs_operator: true })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("阻塞且需要操作员介入")).toBeInTheDocument();
  });

  it("status dots have aria-label describing the status", () => {
    const sessions = [makeSession({ id: "s1", role: "运行中", status: "EXECUTING" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("状态: EXECUTING")).toBeInTheDocument();
  });

  it("filter <select> has aria-label for screen readers", () => {
    const sessions = [makeSession({ id: "s1" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("筛选 Session")).toBeInTheDocument();
  });

  it("desktop aside has aria-label 'Session 列表'", () => {
    const sessions = [makeSession()];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const aside = screen.getByLabelText("Session 列表");
    expect(aside.tagName).toBe("ASIDE");
  });

  it("mobile container has aria-label 'Session 列表'", () => {
    const sessions = [makeSession({ id: "s1" })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} isMobile />);
    const container = screen.getByLabelText("Session 列表");
    expect(container).toBeInTheDocument();
  });
});

/* ── ProgressBar Accessibility ── */
describe("TeamSessionRail progress bar accessibility", () => {
  it("progress bar has role=progressbar", () => {
    const sessions = [makeSession({ id: "s1", role: "预算", budget_ratio: 0.5 })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toBeInTheDocument();
  });

  it("progress bar has aria-valuenow, aria-valuemin, aria-valuemax", () => {
    const sessions = [makeSession({ id: "s1", role: "预算", budget_ratio: 0.5 })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "50");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });

  it("progress bar reflects budget_ratio correctly at 0%", () => {
    const sessions = [makeSession({ id: "s1", role: "空预算", budget_ratio: 0 })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "0");
  });

  it("progress bar clamps ratio > 1 to 100%", () => {
    const sessions = [makeSession({ id: "s1", role: "超预算", budget_ratio: 1.2 })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
  });

  it("no progress bar rendered when budget_ratio is undefined", () => {
    const sessions = [makeSession({ id: "s1", role: "无预算", budget_ratio: undefined })];
    render(<TeamSessionRail sessions={sessions} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
