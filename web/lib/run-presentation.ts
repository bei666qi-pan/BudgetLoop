import type { FolderAccess, PressureMode } from "./types";

export interface FolderAccessModePresentation {
  label: string;
  badgeClass: string;
}

// 权限模式展示：full_access 需要醒目高风险标记（对齐 codex Full Access 的呈现方式）。
export function folderAccessMode(mode: FolderAccess | string | null | undefined): FolderAccessModePresentation {
  if (mode === "full_access") return { label: "完全访问模式", badgeClass: "badge-warning" };
  return { label: "隔离工作区", badgeClass: "badge-success" };
}

export function budgetUsageRatio(used: number, reserved: number | null | undefined, limit: number): number {
  if (!Number.isFinite(limit) || limit <= 0) return 0;
  return Math.min(1, Math.max(0, (Math.max(0, used) + Math.max(0, reserved ?? 0)) / limit));
}

export function pressureExplanation(mode: PressureMode | string): string {
  if (mode === "CONSERVATIVE") return "剩余资源收紧，系统会优先完成最小可验证修复。";
  if (mode === "CRITICAL") return "预算接近上限，系统将严格限制探索并优先交付可解释结果。";
  return "预算充足，系统会在硬上限内平衡分析、修改与验证。";
}

export function runPhaseLabel(
  currentPhase: string | null | undefined,
  terminal: boolean,
  labels: Record<string, string>,
): string {
  if (terminal) return "已结束";
  if (currentPhase) return labels[currentPhase] ?? currentPhase;
  return "准备中";
}
