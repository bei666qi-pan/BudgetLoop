import { describe, expect, it } from "vitest";
import { elapsedStartupTime, sessionStartupPresentation } from "@/lib/session-startup-presentation";
import type { WorkSessionSummary } from "@/lib/types";

const session = (values: Partial<WorkSessionSummary> = {}): WorkSessionSummary => ({
  id: "session-1", container_id: "container-1", role: "后端实现", goal: "完成接口", status: "PLANNING",
  task_id: "task-1", current_run_id: "run-1", conversation_id: null, iteration: 0,
  worktree_enabled: true, worktree_branch: null, worktree_path: null, workspace_status: "PENDING",
  workspace_error: null, created_at: "2026-07-27T00:00:00Z", updated_at: "2026-07-27T00:00:00Z", ...values,
});

describe("session startup presentation", () => {
  it("maps persisted workspace stages without inventing progress", () => {
    expect(sessionStartupPresentation(session({ workspace_status: "PENDING" })).state).toBe("queued");
    expect(sessionStartupPresentation(session({ workspace_status: "PROVISIONING" })).label).toBe("正在准备工作区");
    expect(sessionStartupPresentation(session({ workspace_status: "READY" })).state).toBe("starting");
  });

  it("turns a persisted startup failure into an actionable alert", () => {
    const presentation = sessionStartupPresentation(session({ status: "FAILED", workspace_status: "FAILED", workspace_error: "agent workspace not healthy within 120s" }));
    expect(presentation).toMatchObject({ state: "failed", label: "工作区启动失败", error: "agent workspace not healthy within 120s" });
  });

  it("does not hide legacy failed sessions that have no workspace error", () => {
    expect(sessionStartupPresentation(session({ status: "FAILED", workspace_status: "PENDING" }))).toMatchObject({
      state: "failed",
      error: "该 Run 在工作区准备完成前失败。请打开当前 Run 查看记录的失败原因。",
    });
  });

  it("formats elapsed waiting time from the persisted run start", () => {
    expect(elapsedStartupTime("2026-07-27T00:00:00Z", Date.parse("2026-07-27T00:01:05Z"))).toBe("已等待 1 分 5 秒");
  });
});
