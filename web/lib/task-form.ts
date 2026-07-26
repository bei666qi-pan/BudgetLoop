import type { BudgetConfig, FolderAccess } from "./types";

export type BudgetPreset = "light" | "standard" | "deep";

export const BUDGET_PRESETS: Record<BudgetPreset, BudgetConfig> = {
  light: { max_total_tokens: 30000, max_wall_time_seconds: 600, max_active_runtime_seconds: 300, max_llm_calls: 8, max_cost: 1.5, max_parallel_llm_calls: 1 },
  standard: { max_total_tokens: 100000, max_wall_time_seconds: 1200, max_active_runtime_seconds: 600, max_llm_calls: 20, max_cost: 5, max_parallel_llm_calls: 2 },
  deep: { max_total_tokens: 250000, max_wall_time_seconds: 2400, max_active_runtime_seconds: 1500, max_llm_calls: 50, max_cost: 15, max_parallel_llm_calls: 4 },
};

export interface TaskDraft { name: string; description: string; workdir: string; projectDir?: string; folderAccess?: FolderAccess; budget: BudgetConfig }
export type TaskErrors = Partial<Record<"name" | "description" | "workdir" | "projectDir" | keyof BudgetConfig, string>>;

export function validateTaskDraft(draft: TaskDraft): TaskErrors {
  const errors: TaskErrors = {};
  if (!draft.name.trim()) errors.name = "请输入清晰的任务名称。";
  if (!draft.description.trim()) errors.description = "请描述要解决的问题和期望结果。";
  if (!draft.workdir.trim()) errors.workdir = "请输入 Agent 可以访问的工作目录。";
  else if (!draft.workdir.trim().startsWith("/")) errors.workdir = "工作目录需要使用绝对路径。";
  if (draft.folderAccess === "full_access") {
    const projectDir = draft.projectDir?.trim() ?? "";
    if (!projectDir) errors.projectDir = "完全访问模式需要填写项目文件夹。";
    else if (!projectDir.startsWith("/")) errors.projectDir = "项目文件夹需要使用绝对路径。";
  }
  for (const [key, value] of Object.entries(draft.budget) as [keyof BudgetConfig, number][]) {
    if (!Number.isFinite(value) || value <= 0) errors[key] = "请输入大于 0 的数值。";
  }
  if (draft.budget.max_active_runtime_seconds > draft.budget.max_wall_time_seconds) errors.max_active_runtime_seconds = "执行时间不能超过绝对截止时间。";
  return errors;
}
