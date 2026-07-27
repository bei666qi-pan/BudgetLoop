import type { WorkSessionSummary } from "@/lib/types";

export type SessionStartupState = "queued" | "provisioning" | "starting" | "failed" | null;

export interface SessionStartupPresentation {
  state: SessionStartupState;
  label: string;
  detail: string;
  error: string | null;
}

const ACTIVE_STARTUP_STATUSES = new Set(["PENDING", "PLANNING"]);
const FAILED_STATUSES = new Set(["FAILED", "BUDGET_EXHAUSTED"]);

export function sessionStartupPresentation(session: WorkSessionSummary): SessionStartupPresentation {
  const startupActive = ACTIVE_STARTUP_STATUSES.has(session.status);
  if (session.workspace_status === "FAILED" || FAILED_STATUSES.has(session.status)) {
    return {
      state: "failed",
      label: "工作区启动失败",
      detail: "该 Session 尚未开始执行。检查 Docker Desktop 或 Agent Server 后可重新创建 Session。",
      error: session.workspace_error ?? "该 Run 在工作区准备完成前失败。请打开当前 Run 查看记录的失败原因。",
    };
  }
  if (!startupActive) return { state: null, label: "", detail: "", error: null };
  if (session.workspace_status === "PROVISIONING") {
    return { state: "provisioning", label: "正在准备工作区", detail: "正在启动隔离工作区并连接 Agent Server。", error: null };
  }
  if (session.workspace_status === "READY") {
    return { state: "starting", label: "工作区已就绪，正在启动 Agent", detail: "正在建立对话并提交首个执行步骤。", error: null };
  }
  return { state: "queued", label: "正在等待工作进程", detail: "Session 已提交，等待工作进程开始准备工作区。", error: null };
}

export function elapsedStartupTime(startedAt: string | null, now = Date.now()): string | null {
  if (!startedAt) return null;
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) return null;
  const seconds = Math.max(0, Math.floor((now - started) / 1000));
  if (seconds < 60) return `已等待 ${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  return `已等待 ${minutes} 分 ${seconds % 60} 秒`;
}
