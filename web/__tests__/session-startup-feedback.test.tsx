import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionStartupFeedback } from "@/components/containers/SessionStartupFeedback";
import type { WorkSessionSummary } from "@/lib/types";

function session(overrides: Partial<WorkSessionSummary> = {}): WorkSessionSummary {
  return {
    id: "session-1",
    container_id: "container-1",
    role: "Engineer",
    goal: "Ship the fix",
    status: "PLANNING",
    task_id: "task-1",
    current_run_id: "run-1",
    conversation_id: null,
    iteration: 0,
    worktree_enabled: false,
    worktree_branch: null,
    worktree_path: null,
    workspace_status: "PROVISIONING",
    workspace_error: null,
    run_started_at: "2026-07-27T02:00:00.000Z",
    created_at: "2026-07-27T02:00:00.000Z",
    updated_at: "2026-07-27T02:00:00.000Z",
    ...overrides,
  };
}

describe("SessionStartupFeedback", () => {
  afterEach(() => vi.useRealTimers());

  it("shows one accessible progress message, a decorative mark, and a live elapsed time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-27T02:00:10.000Z"));
    const { container } = render(<SessionStartupFeedback session={session()} />);

    expect(screen.getByRole("region", { name: "Session 启动进度" })).toBeInTheDocument();
    expect(screen.getAllByText("正在准备工作区")).toHaveLength(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(container.querySelector("[data-activity-mark='budgetloop']")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(screen.getByText("已等待 10 秒")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByText("已等待 11 秒")).toBeInTheDocument();
  });

  it("announces a preserved startup failure with a recovery action", () => {
    render(
      <SessionStartupFeedback
        session={session({ workspace_status: "FAILED", workspace_error: "Docker daemon unavailable" })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("工作区启动失败");
    expect(screen.getByRole("alert")).toHaveTextContent("Docker daemon unavailable");
    expect(screen.getByRole("alert")).toHaveTextContent("检查 Docker Desktop");
  });
});
