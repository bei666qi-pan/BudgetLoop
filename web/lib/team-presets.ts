import type { AIGatewayStatus, BudgetConfig, TeamPreset, TeamPresetRole, TeamRoleDraft, TeamRoleOverride } from "@/lib/types";

export const ROLE_BUDGET_LIMITS = {
  max_total_tokens: 200_000,
  max_wall_time_seconds: 7_200,
  max_active_runtime_seconds: 3_600,
  max_llm_calls: 100,
  max_cost: 50,
  max_parallel_llm_calls: 8,
} as const;

export const CATEGORY_LABELS: Record<string, string> = {
  all: "全部",
  general: "通用",
  software: "软件交付",
  game: "游戏研发",
  business: "商业增长",
  content: "品牌内容",
  research: "市场研究",
  data: "数据分析",
  support: "客户支持",
};

export const STAGE_LABELS: Record<string, string> = {
  planning: "规划",
  discovery: "需求澄清",
  strategy: "策略",
  research: "研究",
  design: "设计",
  architecture: "架构",
  readiness: "就绪检查",
  implementation: "实现",
  execution: "执行",
  creation: "创作",
  analysis: "分析",
  storytelling: "洞察表达",
  response: "响应",
  quality: "质量检查",
  review: "独立评审",
  distribution: "分发",
  knowledge: "知识沉淀",
  triage: "问题分流",
  "go-to-market": "上市执行",
};

export function roleDraft(role: TeamPresetRole): TeamRoleDraft {
  return {
    key: role.key,
    enabled: !role.optional,
    role: role.role,
    goal: role.goal,
    budget: { ...role.budget },
    optional: role.optional,
    execution_engine: "openhands",
  };
}

export function roleDrafts(preset: TeamPreset): TeamRoleDraft[] {
  return preset.roles.map(roleDraft);
}

export function enabledRoles(roles: TeamRoleDraft[]): TeamRoleDraft[] {
  return roles.filter((role) => role.enabled);
}

export function aggregateTeamBudget(roles: TeamRoleDraft[]) {
  return enabledRoles(roles).reduce(
    (total, role) => ({
      tokens: total.tokens + role.budget.max_total_tokens,
      calls: total.calls + role.budget.max_llm_calls,
      cost: total.cost + role.budget.max_cost,
    }),
    { tokens: 0, calls: 0, cost: 0 },
  );
}

export function deriveProjectName(goal: string, preset?: TeamPreset | null): string {
  const cleaned = goal.trim().replace(/[。！？!?]+$/u, "");
  if (!cleaned) return preset ? preset.name.replace("团队", "项目") : "";
  const short = Array.from(cleaned).slice(0, 18).join("");
  return Array.from(cleaned).length > 18 ? `${short}…` : short;
}

export function compactStars(stars: number): string {
  if (stars >= 10_000) return `${(stars / 10_000).toFixed(stars >= 100_000 ? 0 : 1)}万`;
  return stars.toLocaleString("zh-CN");
}

export function roleBoundsValid(roles: TeamRoleDraft[]): boolean {
  const count = enabledRoles(roles).length;
  return count >= 2 && count <= 8;
}

export function roleBudgetValid(budget: BudgetConfig): boolean {
  const boundedInteger = (value: number, maximum: number) =>
    Number.isInteger(value) && value >= 1 && value <= maximum;
  return boundedInteger(budget.max_total_tokens, ROLE_BUDGET_LIMITS.max_total_tokens)
    && boundedInteger(budget.max_wall_time_seconds, ROLE_BUDGET_LIMITS.max_wall_time_seconds)
    && boundedInteger(budget.max_active_runtime_seconds, ROLE_BUDGET_LIMITS.max_active_runtime_seconds)
    && boundedInteger(budget.max_llm_calls, ROLE_BUDGET_LIMITS.max_llm_calls)
    && Number.isFinite(budget.max_cost) && budget.max_cost > 0 && budget.max_cost <= ROLE_BUDGET_LIMITS.max_cost
    && boundedInteger(budget.max_parallel_llm_calls, ROLE_BUDGET_LIMITS.max_parallel_llm_calls);
}

export function roleOverride(role: TeamRoleDraft): TeamRoleOverride {
  if (!role.enabled) return { key: role.key, enabled: false };
  return {
    key: role.key,
    enabled: true,
    role: role.role.trim(),
    goal: role.goal.trim(),
    budget: { ...role.budget },
    execution_engine: role.execution_engine,
  };
}

export function safeGatewayConsoleUrl(status: AIGatewayStatus | null): string | null {
  if (status?.type !== "new-api" || !status.console_url) return null;
  try {
    const url = new URL(status.console_url);
    if (
      !["http:", "https:"].includes(url.protocol)
      || url.username
      || url.password
      || url.search
      || url.hash
    ) return null;
    return url.toString();
  } catch {
    return null;
  }
}
