// execution_events.type → 时间线分类、图标与配色。分类与后端 EventType 枚举对齐。
import type { LucideIcon } from "lucide-react";
import {
  Play,
  ArrowLeftRight,
  Layers,
  RefreshCw,
  Sparkles,
  Wrench,
  CheckCircle2,
  Target,
  DollarSign,
  TrendingUp,
  Shuffle,
  Undo2,
  Hand,
  Flag,
  MessageSquare,
  AlertTriangle,
  Square,
  Info,
} from "lucide-react";

export type EventCategory =
  | "plan" | "execute" | "tool" | "feedback" | "progress"
  | "correction" | "approval" | "budget" | "message" | "warning" | "final";

export interface EventMeta {
  category: EventCategory;
  label: string;
  icon: LucideIcon;
}

export const CATEGORY_STYLE: Record<EventCategory, { dot: string; badge: string; label: string }> = {
  plan: { dot: "bg-info", badge: "badge-info", label: "计划" },
  execute: { dot: "bg-info", badge: "badge-info", label: "执行" },
  tool: { dot: "bg-accent", badge: "badge-success", label: "工具调用" },
  feedback: { dot: "bg-accent", badge: "badge-success", label: "反馈" },
  progress: { dot: "bg-accent", badge: "badge-success", label: "进展评估" },
  correction: { dot: "bg-warning", badge: "badge-warning", label: "修正" },
  approval: { dot: "bg-warning", badge: "badge-warning", label: "审批" },
  budget: { dot: "bg-muted-foreground", badge: "badge-muted", label: "预算" },
  message: { dot: "bg-muted-foreground", badge: "badge-muted", label: "消息" },
  warning: { dot: "bg-critical", badge: "badge-critical", label: "警告" },
  final: { dot: "bg-accent", badge: "badge-success", label: "最终结果" },
};

const EVENT_META: Record<string, EventMeta> = {
  run_started: { category: "plan", label: "运行开始", icon: Play },
  state_changed: { category: "plan", label: "状态变更", icon: ArrowLeftRight },
  phase_changed: { category: "plan", label: "阶段切换", icon: Layers },
  iteration_started: { category: "plan", label: "迭代开始", icon: RefreshCw },
  iteration_finished: { category: "plan", label: "迭代结束", icon: RefreshCw },
  llm_call: { category: "execute", label: "LLM 调用", icon: Sparkles },
  tool_call: { category: "tool", label: "工具调用", icon: Wrench },
  test_result: { category: "feedback", label: "测试结果", icon: CheckCircle2 },
  progress_scored: { category: "progress", label: "进展评估", icon: Target },
  budget_updated: { category: "budget", label: "预算更新", icon: DollarSign },
  budget_reallocated: { category: "correction", label: "预算重分配", icon: ArrowLeftRight },
  pressure_changed: { category: "correction", label: "压力模式变更", icon: TrendingUp },
  strategy_switched: { category: "correction", label: "策略调整", icon: Shuffle },
  rollback: { category: "correction", label: "回滚", icon: Undo2 },
  approval_requested: { category: "approval", label: "审批请求", icon: Hand },
  approval_decided: { category: "approval", label: "审批结果", icon: CheckCircle2 },
  checkpoint_created: { category: "final", label: "检查点", icon: Flag },
  agent_message: { category: "message", label: "Agent 消息", icon: MessageSquare },
  warning: { category: "warning", label: "警告", icon: AlertTriangle },
  run_finished: { category: "final", label: "运行结束", icon: Square },
};

export function eventMeta(type: string): EventMeta {
  return EVENT_META[type] ?? { category: "message", label: type, icon: Info };
}

export function approvalIdOf(payload: Record<string, unknown>): string | null {
  const v = payload.approval_id ?? payload.id;
  return typeof v === "string" ? v : null;
}

// API helpers for events
import { API_BASE } from "./api";

export async function fetchEvents(runId: string, afterSeq: number): Promise<{ events: any[] }> {
  const url = `${API_BASE}/api/runs/${runId}/events?after_seq=${afterSeq}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) return { events: [] };
  return res.json();
}
