import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AiGatewayStatus } from "@/components/containers/AiGatewayStatus";
import { ExecutionEnginePicker } from "@/components/containers/ExecutionEnginePicker";
import { PresetRoleList } from "@/components/containers/PresetRoleList";
import { PresetSources } from "@/components/containers/PresetSources";
import { TeamPresetPreview } from "@/components/containers/TeamPresetPreview";
import { aggregateTeamBudget, deriveProjectName, roleBoundsValid, roleBudgetValid, roleDrafts, roleOverride, safeGatewayConsoleUrl } from "@/lib/team-presets";
import type { AIGatewayStatus, ExecutionEngineInfo, TeamPreset, TeamPresetRecommendationResponse } from "@/lib/types";

const source = {
  key: "langgraph",
  repository: "langchain-ai/langgraph",
  url: "https://github.com/langchain-ai/langgraph",
  license: "MIT",
  reviewed_stars: 38_095,
  reviewed_at: "2026-07-25",
  integration: "runtime" as const,
  runtime_dependency: true,
};

const preset: TeamPreset = {
  id: "game-development",
  version: 1,
  name: "游戏研发团队",
  category: "game",
  summary: "从玩法到试玩版",
  best_for: "游戏原型",
  coordination_pattern: "规划 → 设计 → 实现 → 评审",
  default_workspace_policy: "worktree",
  requires_third_party_setup: false,
  sources: [source],
  starter_budget: { max_total_tokens: 30_000, max_llm_calls: 10, max_cost: 3 },
  roles: [
    { key: "producer", role: "制作人", goal: "推动交付", backstory: "控制范围", responsibility: "控制范围", skills: ["规划"], optional: false, budget: { max_total_tokens: 10_000, max_wall_time_seconds: 1200, max_active_runtime_seconds: 600, max_llm_calls: 5, max_cost: 1, max_parallel_llm_calls: 1 } },
    { key: "client", role: "客户端", goal: "实现玩法", backstory: "实现系统", responsibility: "实现系统", skills: ["开发"], optional: false, budget: { max_total_tokens: 20_000, max_wall_time_seconds: 1200, max_active_runtime_seconds: 600, max_llm_calls: 5, max_cost: 2, max_parallel_llm_calls: 1 } },
  ],
  tasks: [],
  sop: { entry: "planning", stages: [] },
};

const engines: ExecutionEngineInfo[] = [
  { id: "openhands", name: "OpenHands", repository: "OpenHands/OpenHands", url: "https://github.com/OpenHands/OpenHands", revision: "a".repeat(40), reviewed_stars: 82_021, license: "MIT core", license_scope: "core", source_path: "vendor/agent-engines/openhands", source_downloaded: true, package_installed: null, managed_ai_ready: null, transport: "server", command: null, capabilities: ["tools"], credential_hint: "server", runtime_available: true, availability_reason: "configured", default: true },
  { id: "codex", name: "Codex", repository: "openai/codex", url: "https://github.com/openai/codex", revision: "b".repeat(40), reviewed_stars: 101_301, license: "Apache-2.0", license_scope: "entire", source_path: "vendor/agent-engines/codex", source_downloaded: true, package_installed: true, managed_ai_ready: false, transport: "cli", command: "codex", capabilities: ["json_events"], credential_hint: "login", runtime_available: false, availability_reason: "worker runtime disabled", default: false },
];

const gatewayStatus: AIGatewayStatus = {
  type: "new-api",
  configured: true,
  healthy: true,
  recommendation_enabled: true,
  recommendation_model: "budgetloop-recommendation",
  default_model: "app-model",
  deployment_label: "New API",
  network_label: null,
  reasoning_effort: "max",
  thinking_enabled: true,
  thinking_budget_tokens: 65536,
  managed_app_runtime: {
    enabled: true,
    credential_source: "budgetloop_scoped_runtime",
    project_env_required: false,
    browser_direct_access: false,
  },
  console_url: "https://gateway.example/admin",
  protocols: ["OpenAI Chat Completions", "OpenAI Responses", "Claude Messages", "Gemini native"],
  routing: "New API 渠道优先级、权重、重试与限流",
  semantic_ai_router: false,
  provenance: {
    name: "New API",
    repository: "QuantumNous/new-api",
    repository_url: "https://github.com/QuantumNous/new-api",
    release: "v1.0.0-rc.21",
    revision: "b".repeat(40),
    license: "AGPL-3.0",
    reviewed_stars: 43_370,
    reviewed_at: "2026-07-25",
  },
  reason_code: null,
  status_class: "2xx",
};

const recommendationRuntime = (source: "ai" | "local_fallback", fallbackReason: string | null = null): TeamPresetRecommendationResponse => ({
  recommendations: [],
  explanation: "transparent",
  runtime: source === "ai" ? "ai-gateway" : "langgraph",
  source,
  gateway: { type: "new-api", model: "budgetloop-recommendation", status_class: source === "ai" ? "2xx" : null },
  fallback_reason: fallbackReason,
});

describe("Agent Team preset helpers", () => {
  it("derives a short project name and aggregates only enabled roles", () => {
    const roles = roleDrafts(preset);
    roles[1].enabled = false;
    expect(deriveProjectName("在四周内完成一个手机解谜游戏试玩版本并验证核心玩法", preset)).toMatch(/…$/);
    expect(aggregateTeamBudget(roles)).toEqual({ tokens: 10_000, calls: 5, cost: 1 });
    expect(roleBoundsValid(roles)).toBe(false);
  });

  it("keeps role overrides inside the backend budget contract", () => {
    const roles = roleDrafts(preset);
    expect(roleBudgetValid(roles[0].budget)).toBe(true);
    expect(roleBudgetValid({ ...roles[0].budget, max_total_tokens: 99_999_990 })).toBe(false);
    roles[0].enabled = false;
    expect(roleOverride(roles[0])).toEqual({ key: "producer", enabled: false });
  });
});

describe("Execution engine and preset controls", () => {
  it("distinguishes runtime availability from downloaded source", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ExecutionEnginePicker engines={engines} selectedId="openhands" onSelect={onSelect} />);
    expect(screen.getByText("服务已就绪")).toBeInTheDocument();
    expect(screen.getByText("已安装 · 配置待完成")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Codex/ }));
    expect(onSelect).toHaveBeenCalledWith("codex");
  });

  it("keeps source provenance as a real external link", () => {
    render(<PresetSources sources={[source]} />);
    expect(screen.getByRole("link", { name: /langgraph/ })).toHaveAttribute("href", source.url);
    expect(screen.getByText("直接运行")).toBeInTheDocument();
  });

  it("supports per-role engine overrides", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PresetRoleList preset={preset} roles={roleDrafts(preset)} engines={engines} onChange={onChange} />);
    await user.selectOptions(screen.getAllByLabelText("执行引擎")[0], "codex");
    expect(onChange.mock.calls.at(-1)?.[0][0].execution_engine).toBe("codex");
  });

  it("allows create-later while blocking start for an unavailable engine", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const roles = roleDrafts(preset).map((role) => ({ ...role, execution_engine: "codex" }));
    render(<TeamPresetPreview preset={preset} roles={roles} teamMode="guided" budgetMode="bounded" valid startValid={false} busyAction={null} error="运行待启用" onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: /一键创建并启动/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /仅创建，稍后启动/ }));
    expect(onSubmit).toHaveBeenCalledWith(false);
    expect(screen.getByText("仅创建", { selector: ".sm\\:hidden" })).toBeInTheDocument();
  });

  it("labels autonomous Max teams without showing a synthetic token cap", () => {
    render(<TeamPresetPreview preset={preset} roles={roleDrafts(preset)} teamMode="autonomous" budgetMode="max" valid startValid busyAction={null} error={null} onSubmit={vi.fn()} />);
    expect(screen.getByText("Max", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/自主阶段协作与自动 Handoff 已启用/)).toBeInTheDocument();
    expect(screen.getByText(/Max 不会自动停止/)).toBeInTheDocument();
  });
});

describe("AI gateway recommendation transparency", () => {
  it("discloses AI-ready state and opens only a safe upstream console", () => {
    render(<AiGatewayStatus status={gatewayStatus} statusError={null} recommendation={null} />);
    expect(screen.getByText(/AI 智能推荐已就绪/)).toBeInTheDocument();
    expect(screen.getByText(/仅发送推荐字段/)).toBeInTheDocument();
    expect(screen.getByText(/默认继承受限代理能力/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /管理 AI 网关/ })).toHaveAttribute("href", "https://gateway.example/admin");
    expect(screen.getByRole("link", { name: /管理 AI 网关/ })).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: /管理 AI 网关/ })).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("labels validated AI output without exposing hidden reasoning", () => {
    render(<AiGatewayStatus status={gatewayStatus} statusError={null} recommendation={recommendationRuntime("ai")} />);
    expect(screen.getByText("AI 已完成推荐 · 本地目录已校验")).toBeInTheDocument();
    expect(screen.getByText(/不展示或保存隐藏推理/)).toBeInTheDocument();
  });

  it("truthfully discloses when managed app inheritance is disabled", () => {
    const disabled = {
      ...gatewayStatus,
      managed_app_runtime: { ...gatewayStatus.managed_app_runtime, enabled: false },
    };
    render(<AiGatewayStatus status={disabled} statusError={null} recommendation={null} />);
    expect(screen.getByText(/AI 应用自动继承已关闭/)).toBeInTheDocument();
  });

  it("keeps runtime fallback usable and explains the sanitized reason", () => {
    render(<AiGatewayStatus status={gatewayStatus} statusError={null} recommendation={recommendationRuntime("local_fallback", "timeout")} />);
    expect(screen.getByText("已自动切换到本地推荐")).toBeInTheDocument();
    expect(screen.getByText(/AI 网关响应超时；团队创建功能不受影响/)).toBeInTheDocument();
  });

  it("rejects unsafe console URLs even if a client object is forged", () => {
    const unsafe = { ...gatewayStatus, console_url: "https://user:secret@gateway.example/admin" };
    expect(safeGatewayConsoleUrl(unsafe)).toBeNull();
    render(<AiGatewayStatus status={unsafe} statusError={null} recommendation={null} />);
    expect(screen.queryByRole("link", { name: /管理 AI 网关/ })).not.toBeInTheDocument();
  });

  it("shows non-blocking local mode when AI is unconfigured", () => {
    render(<AiGatewayStatus status={{ ...gatewayStatus, configured: false, healthy: false, reason_code: "missing_gateway_key" }} statusError={null} recommendation={null} />);
    expect(screen.getByText("当前使用本地推荐")).toBeInTheDocument();
    expect(screen.getByText(/配置完成后会自动优先使用 AI/)).toBeInTheDocument();
  });
});
