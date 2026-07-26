import type {
  ContainerLifecycle,
  RunStatus,
  SessionTranscriptEntry,
  WorkContainer,
  WorkSessionSummary,
} from "./types";

export type ContainerFilter = "all" | ContainerLifecycle;

export const CONTAINER_LIFECYCLE_LABELS: Record<ContainerLifecycle, string> = {
  active: "活跃",
  paused: "已暂停",
  completed: "已完成",
  archived: "已归档",
};

export const SESSION_STATUS_LABELS: Record<string, string> = {
  PENDING: "待处理",
  PLANNING: "规划中",
  EXECUTING: "执行中",
  OBSERVING: "观察中",
  EVALUATING: "评估中",
  REPLANNING: "重新规划",
  WAITING_APPROVAL: "等待审批",
  PAUSED: "已暂停",
  COMPLETED: "已完成",
  PARTIAL_COMPLETED: "部分完成",
  FAILED: "需要关注",
  BUDGET_EXHAUSTED: "预算耗尽",
  CANCELLED: "已取消",
};

export function filterContainers(
  containers: WorkContainer[],
  query: string,
  filter: ContainerFilter,
): WorkContainer[] {
  const normalized = query.trim().toLocaleLowerCase();
  return containers.filter((container) => {
    const haystack = `${container.name} ${container.project_goal}`.toLocaleLowerCase();
    return (
      (!normalized || haystack.includes(normalized)) &&
      (filter === "all" || container.lifecycle_state === filter)
    );
  });
}

export function aggregateContainerCounts(containers: WorkContainer[]) {
  return containers.reduce(
    (total, container) => ({
      containers: total.containers + 1,
      running: total.running + container.counts.running,
      waiting: total.waiting + container.counts.waiting,
      attention: total.attention + container.counts.attention,
    }),
    { containers: 0, running: 0, waiting: 0, attention: 0 },
  );
}

export function lifecycleTone(lifecycle: ContainerLifecycle): string {
  if (lifecycle === "active") return "text-success bg-success/10 ring-success/20";
  if (lifecycle === "paused") return "text-warning bg-warning/10 ring-warning/20";
  if (lifecycle === "completed") return "text-info bg-info/10 ring-info/20";
  return "text-muted-foreground bg-muted ring-border";
}

export function sessionTone(status: RunStatus | string): string {
  if (["FAILED", "BUDGET_EXHAUSTED"].includes(status)) return "bg-critical";
  if (["WAITING_APPROVAL", "PAUSED", "PENDING"].includes(status)) return "bg-warning";
  if (["COMPLETED", "PARTIAL_COMPLETED"].includes(status)) return "bg-info";
  return "bg-success";
}

export function budgetRatio(session?: { budget?: { max_total_tokens: number; used_tokens: number } | null }) {
  const budget = session?.budget;
  if (!budget || budget.max_total_tokens <= 0) return 0;
  return Math.min(1, Math.max(0, budget.used_tokens / budget.max_total_tokens));
}

export function incomingMessages(
  transcript: SessionTranscriptEntry[],
  selectedSessionId: string,
) {
  return transcript.filter(
    (entry) =>
      entry.entry_type !== "agent_output" &&
      entry.recipient_session_id === selectedSessionId,
  );
}

export function availableHandoffRecipients(
  sessions: WorkSessionSummary[],
  selectedSessionId: string,
) {
  return sessions.filter((session) => session.id !== selectedSessionId);
}

export function presentWorktreePath(path: string | null): string | null {
  if (!path) return null;
  const marker = ".budgetloop/worktrees/";
  const markerIndex = path.indexOf(marker);
  return markerIndex >= 0 ? path.slice(markerIndex) : path;
}
