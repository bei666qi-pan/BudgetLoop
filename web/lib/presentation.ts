import type { RunStatus, TaskListItem } from "./types";

export const STATUS_LABELS: Record<string, string> = {
  PENDING: "待处理", PLANNING: "规划中", EXECUTING: "执行中", OBSERVING: "观察中",
  EVALUATING: "评估中", REPLANNING: "重新规划", WAITING_APPROVAL: "等待审批",
  PAUSED: "已暂停", COMPLETED: "已完成", PARTIAL_COMPLETED: "部分完成",
  FAILED: "失败", BUDGET_EXHAUSTED: "预算已耗尽", CANCELLED: "已取消",
  // LLM 调用的 request_status
  success: "成功", failed: "失败", rejected_budget: "预算拒绝",
};

export const TERMINAL_STATUS = new Set<RunStatus>([
  "COMPLETED", "PARTIAL_COMPLETED", "FAILED", "BUDGET_EXHAUSTED", "CANCELLED",
]);

export type TaskFilter = "all" | "active" | "pending" | "completed" | "attention";

export function taskFilterOf(status?: string | null): Exclude<TaskFilter, "all"> {
  if (!status || status === "PENDING") return "pending";
  if (status === "COMPLETED") return "completed";
  if (["FAILED", "BUDGET_EXHAUSTED", "PARTIAL_COMPLETED", "WAITING_APPROVAL"].includes(status)) return "attention";
  return "active";
}

export function filterTasks(tasks: TaskListItem[], query: string, filter: TaskFilter): TaskListItem[] {
  const normalized = query.trim().toLocaleLowerCase();
  return tasks.filter((task) => {
    const matchesQuery = !normalized || `${task.name} ${task.id}`.toLocaleLowerCase().includes(normalized);
    const matchesFilter = filter === "all" || taskFilterOf(task.latest_run?.status) === filter;
    return matchesQuery && matchesFilter;
  });
}

export function taskCounts(tasks: TaskListItem[]) {
  return tasks.reduce((counts, task) => {
    counts.all += 1;
    counts[taskFilterOf(task.latest_run?.status)] += 1;
    return counts;
  }, { all: 0, active: 0, pending: 0, completed: 0, attention: 0 });
}

export function statusClass(status?: string | null): string {
  if (status === "COMPLETED") return "badge-success";
  // 调用成功是常态路径，用 info 蓝保持表格安静；运行完成才是 success 绿。
  if (status === "success") return "badge-info";
  if (["WAITING_APPROVAL", "PARTIAL_COMPLETED", "REPLANNING", "rejected_budget"].includes(status ?? "")) return "badge-warning";
  if (["FAILED", "BUDGET_EXHAUSTED", "failed"].includes(status ?? "")) return "badge-critical";
  if (["PAUSED", "CANCELLED"].includes(status ?? "")) return "badge-muted";
  return "badge-info";
}
