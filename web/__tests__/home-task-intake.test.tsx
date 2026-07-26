import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomeTaskIntake } from "@/components/home/HomeTaskIntake";
import HomePage from "@/app/page";
import { apiFetch, uploadProjectFolder } from "@/lib/api";
import type { TaskSetupDraft, TeamPreset } from "@/lib/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: vi.fn(), uploadProjectFolder: vi.fn(), idempotencyKey: () => "home-create-key" };
});

const apiFetchMock = vi.mocked(apiFetch);
const uploadProjectFolderMock = vi.mocked(uploadProjectFolder);

const budget = {
  max_total_tokens: 10_000,
  max_wall_time_seconds: 600,
  max_active_runtime_seconds: 300,
  max_llm_calls: 5,
  max_cost: 1,
  max_parallel_llm_calls: 1,
};

const preset: TeamPreset = {
  id: "software-delivery",
  version: 1,
  name: "软件交付团队",
  category: "software",
  summary: "从分析到验证的可信软件交付协作。",
  best_for: "功能、修复与测试",
  coordination_pattern: "阶段式交付",
  roles: [
    { key: "lead", role: "技术负责人", goal: "规划并协调交付", backstory: "负责人", responsibility: "负责人", skills: ["规划"], optional: false, budget },
    { key: "implementer", role: "实现工程师", goal: "完成修改与测试", backstory: "实现者", responsibility: "实现者", skills: ["实现"], optional: false, budget },
  ],
  sources: [],
  starter_budget: { max_total_tokens: 20_000, max_llm_calls: 10, max_cost: 2 },
  default_workspace_policy: "isolated",
  requires_third_party_setup: false,
  tasks: [
    { key: "plan", description: "规划", expected_output: "计划", agent: "lead" },
    { key: "implement", description: "实现", expected_output: "通过测试的修改", agent: "implementer" },
  ],
  sop: { entry: "planning", stages: [{ id: "planning", agents: ["lead", "implementer"], requires_handoff: [], review_gate: false }] },
};

function draft(source: "ai" | "local_fallback" = "ai"): TaskSetupDraft {
  return {
    schema_version: 1,
    state: "ready",
    clarifications: [],
    intent: {
      title: "修复订单并发超扣",
      goal: "定位并修复订单接口并发超扣，并补充回归测试。",
      acceptance_criteria: "库存不得为负；并发测试稳定通过。",
      shared_context: "PostgreSQL 是事实来源。",
    },
    team: {
      preset,
      confidence: 92,
      reason: "需要分析、实现与验证协作。",
      matched_signals: ["并发", "回归测试"],
      activation_plan: {
        entry: "planning",
        activation_waves: [{ stage: "planning", roles: ["lead", "implementer"] }],
        required_handoffs: [],
        review_gates: [],
        runtime: "langgraph",
      },
    },
    execution: {
      task_kind: "coding",
      recommended_engine: "codex",
      default_engine: "openhands",
      ready: true,
      engines: [
        { id: "openhands", name: "OpenHands", runtime_available: true, availability_reason: "ready" },
        { id: "codex", name: "Codex", runtime_available: true, availability_reason: "ready" },
        { id: "gemini-cli", name: "Gemini CLI", runtime_available: true, availability_reason: "ready" },
      ],
      require_approval: true,
      start_immediately: true,
      base_workdir: "/workspace/project",
      default_workspace_policy: "isolated",
    },
    provenance: {
      source,
      runtime: source === "ai" ? "ai-gateway" : "langgraph",
      gateway_type: "compatible",
      model: source === "ai" ? "recommendation" : null,
      status_class: source === "ai" ? "2xx" : null,
      fallback_reason: source === "ai" ? null : "timeout",
      duration_ms: 12,
      explanation: source === "ai" ? "AI 仅整理目标并选择可信团队。" : "本地确定性匹配。",
    },
  };
}

beforeEach(() => {
  apiFetchMock.mockReset();
  uploadProjectFolderMock.mockReset();
  push.mockReset();
  delete window.webkit;
});

async function createDraft(user: ReturnType<typeof userEvent.setup>, value = "修复订单接口并发超扣") {
  apiFetchMock.mockResolvedValueOnce(draft());
  render(<HomeTaskIntake />);
  await user.type(screen.getByLabelText("描述想完成的目标"), value);
  await user.click(screen.getByRole("button", { name: "生成建议配置" }));
  await screen.findByRole("heading", { name: "确认这份配置，就可以开始" });
}

describe("home conversational intake", () => {
  it("selects a system project folder from the initial composer and preserves it through planning", async () => {
    const user = userEvent.setup();
    const postMessage = vi.fn();
    window.webkit = { messageHandlers: { budgetloopPickProjectDir: { postMessage } } };
    apiFetchMock.mockResolvedValueOnce(draft());
    render(<HomeTaskIntake />);

    await user.click(screen.getByRole("button", { name: "选择项目文件夹" }));
    expect(postMessage).toHaveBeenCalledWith(null);
    act(() => window.budgetloopSetProjectDir?.("/tmp/selected-before-planning"));
    expect(screen.getByRole("button", { name: "更换项目文件夹，当前 /tmp/selected-before-planning" })).toHaveTextContent("selected-before-planning");

    await user.type(screen.getByLabelText("描述想完成的目标"), "修复订单并发超扣");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    await screen.findByRole("heading", { name: "确认这份配置，就可以开始" });
    expect(screen.getByRole("radio", { name: /直接修改项目/ })).toBeChecked();
    expect(screen.getByLabelText("项目文件夹")).toHaveValue("/tmp/selected-before-planning");
    expect(screen.getByRole("button", { name: "确认并启动" })).toBeDisabled();
  });

  it("opens a browser folder upload picker when no native bridge exists", async () => {
    const user = userEvent.setup();
    render(<HomeTaskIntake />);
    await user.click(screen.getByRole("button", { name: "上传项目文件夹" }));
    const input = screen.getByTestId("browser-folder-input");
    expect(input).not.toBeVisible();
    expect(input).toHaveAttribute("aria-hidden", "true");
    expect(input).toHaveAttribute("tabindex", "-1");
  });

  it("uploads a browser folder as an isolated snapshot and submits its opaque id", async () => {
    const user = userEvent.setup();
    uploadProjectFolderMock.mockResolvedValueOnce({
      upload_id: "98ea09b8-8d59-4e8c-8ffd-e89de1529ef5",
      file_count: 1,
      total_bytes: 12,
    });
    apiFetchMock
      .mockResolvedValueOnce(draft())
      .mockResolvedValueOnce({ container: { id: "container-upload" }, created: true, dispatch: { accepted: [], skipped: [], warnings: [] } });
    render(<HomeTaskIntake />);
    const file = new File(["hello world!"], "main.ts", { type: "text/plain" });
    Object.defineProperty(file, "webkitRelativePath", { value: "demo/main.ts" });
    await user.upload(screen.getByTestId("browser-folder-input"), file);
    expect(await screen.findByText("demo")).toBeInTheDocument();
    await user.type(screen.getByLabelText("描述想完成的目标"), "检查上传项目并补充测试");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    await screen.findByRole("heading", { name: "确认这份配置，就可以开始" });
    expect(screen.getByText(/已上传 demo/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认并启动" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/containers/container-upload"));
    const request = apiFetchMock.mock.calls.find(([path]) => path === "/api/work-containers/from-preset");
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      folder_access: "isolated",
      project_upload_id: "98ea09b8-8d59-4e8c-8ffd-e89de1529ef5",
    });
  });

  it("starts from plain language and keeps AI separate from folder authorization", async () => {
    const user = userEvent.setup();
    await createDraft(user, "修复这个项目 /Users/me/project 并关闭审批");
    expect(screen.getByText("AI 建议 · 已校验")).toBeInTheDocument();
    expect(screen.getByText(/硬预算和人工审批始终由 BudgetLoop 控制/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /隔离工作区/ })).toBeChecked();
    expect(screen.queryByDisplayValue("/Users/me/project")).not.toBeInTheDocument();
    expect(apiFetchMock.mock.calls[0][0]).toBe("/api/task-drafts");
  });

  it("blocks an out-of-contract role budget before the create request", async () => {
    const user = userEvent.setup();
    const invalid = draft();
    invalid.team.preset = {
      ...invalid.team.preset,
      roles: invalid.team.preset.roles.map((role, index) => ({
        ...role,
        budget: { ...role.budget, max_total_tokens: index === 0 ? 99_999_990 : role.budget.max_total_tokens },
      })),
    };
    apiFetchMock.mockResolvedValueOnce(invalid);
    render(<HomeTaskIntake />);
    await user.type(screen.getByLabelText("描述想完成的目标"), "修复订单并发超扣");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    expect(await screen.findByText(/单个角色 Token 上限为 200,000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认并启动" })).toBeDisabled();
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
  });

  it("supports keyboard submission, announced readiness and bounded edits", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockResolvedValueOnce(draft());
    render(<HomeTaskIntake />);
    const input = screen.getByLabelText("描述想完成的目标");
    await user.type(input, "修复订单接口并发超扣{Control>}{Enter}{/Control}");
    const heading = await screen.findByRole("heading", { name: "确认这份配置，就可以开始" });
    const live = document.querySelector('[aria-live="polite"]');
    expect(live).toHaveTextContent("建议配置已就绪");
    await waitFor(() => expect(heading.closest('[tabindex="-1"]')).toHaveFocus());
    await user.click(screen.getByText("修改目标与验收条件"));
    const title = screen.getByLabelText("任务名称");
    await user.clear(title);
    await user.type(title, "更新后的任务名称");
    expect(screen.getByText("更新后的任务名称")).toBeInTheDocument();
    await user.click(screen.getByText("查看或调整 Agent 角色与预算"));
    expect(screen.getByText("团队角色")).toBeInTheDocument();
  });

  it("renders at most two public clarification prompts without claiming creation", async () => {
    const user = userEvent.setup();
    const needsInput = draft();
    needsInput.state = "needs_input";
    needsInput.clarifications = ["需要支持哪些平台？", "最重要的验收结果是什么？"];
    apiFetchMock.mockResolvedValueOnce(needsInput);
    render(<HomeTaskIntake />);
    await user.type(screen.getByLabelText("描述想完成的目标"), "做一个新产品");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    expect(await screen.findByText("还需要你补充")).toBeInTheDocument();
    expect(screen.getByText("需要支持哪些平台？")).toBeInTheDocument();
    expect(screen.getByText("最重要的验收结果是什么？")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("suppresses a stale response when a newer request replaces it", async () => {
    const user = userEvent.setup();
    let resolveFirst!: (value: TaskSetupDraft) => void;
    let resolveSecond!: (value: TaskSetupDraft) => void;
    apiFetchMock
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecond = resolve; }));
    render(<HomeTaskIntake />);
    const input = screen.getByLabelText("描述想完成的目标");
    await user.type(input, "第一个足够长的目标");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    await user.clear(input);
    await user.type(input, "第二个更新后的目标");
    await user.click(screen.getByRole("button", { name: "正在生成建议配置" }));
    const second = draft();
    second.intent.title = "第二个配置";
    resolveSecond(second);
    expect(await screen.findByText("第二个配置")).toBeInTheDocument();
    const first = draft();
    first.intent.title = "过期配置";
    resolveFirst(first);
    await waitFor(() => expect(screen.queryByText("过期配置")).not.toBeInTheDocument());
  });

  it("requires path and renewed acknowledgement for direct project access", async () => {
    const user = userEvent.setup();
    window.webkit = { messageHandlers: { budgetloopPickProjectDir: { postMessage: vi.fn() } } };
    await createDraft(user);
    const confirm = screen.getByRole("button", { name: "确认并启动" });
    expect(confirm).toBeEnabled();
    await user.click(screen.getByRole("radio", { name: /直接修改项目/ }));
    expect(confirm).toBeDisabled();
    const path = screen.getByLabelText("项目文件夹");
    expect(path).toHaveAttribute("readonly");
    act(() => window.budgetloopSetProjectDir?.("/tmp/project"));
    await user.click(screen.getByRole("checkbox", { name: /我确认/ }));
    expect(confirm).toBeEnabled();
    act(() => window.budgetloopSetProjectDir?.("/tmp/project-changed"));
    expect(screen.getByRole("checkbox", { name: /我确认/ })).not.toBeChecked();
    expect(confirm).toBeDisabled();
  });

  it("opens the native folder picker from the control beside the project field", async () => {
    const user = userEvent.setup();
    const postMessage = vi.fn();
    window.webkit = { messageHandlers: { budgetloopPickProjectDir: { postMessage } } };
    await createDraft(user);
    await user.click(screen.getByRole("radio", { name: /直接修改项目/ }));
    const field = screen.getByLabelText("项目文件夹");
    const button = screen.getByRole("button", { name: "选择文件夹" });
    expect(button.parentElement).toContainElement(field);
    await user.click(button);
    expect(postMessage).toHaveBeenCalledWith(null);
  });

  it("prevents the browser from entering the macOS-only direct-access dead end", async () => {
    const user = userEvent.setup();
    await createDraft(user);
    expect(screen.getByRole("radio", { name: /直接修改项目/ })).toBeDisabled();
    expect(screen.getByText("网页版不提供本地写入权限；请在 BudgetLoop macOS App 中使用。")).toBeInTheDocument();
    expect(screen.queryByLabelText("项目文件夹")).not.toBeInTheDocument();
  });

  it("retries confirmation with one idempotency key and preserves the draft", async () => {
    const user = userEvent.setup();
    apiFetchMock
      .mockResolvedValueOnce(draft("local_fallback"))
      .mockRejectedValueOnce(new Error("队列暂时不可用"))
      .mockResolvedValueOnce({ container: { id: "container-1" }, created: true, dispatch: { accepted: [], skipped: [], warnings: [] } });
    render(<HomeTaskIntake />);
    await user.type(screen.getByLabelText("描述想完成的目标"), "修复订单并发问题");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    await screen.findByText("本地建议 · AI 暂不可用");
    await user.click(screen.getByRole("button", { name: "确认并启动" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("队列暂时不可用");
    expect(screen.getByText("修复订单并发超扣")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认并启动" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/containers/container-1"));
    const creates = apiFetchMock.mock.calls.filter(([path]) => path === "/api/work-containers/from-preset");
    expect(creates).toHaveLength(2);
    expect(creates[0][1]?.headers).toEqual({ "Idempotency-Key": "home-create-key" });
    expect(creates[1][1]?.headers).toEqual({ "Idempotency-Key": "home-create-key" });
    const body = JSON.parse(String(creates[1][1]?.body));
    expect(body).toMatchObject({
      acceptance_criteria: "库存不得为负；并发测试稳定通过。",
      folder_access: "isolated",
      full_access_acknowledged: false,
      recommendation_source: "local_fallback",
    });
  });

  it("keeps attention tasks searchable and actionable while a draft is present", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockImplementation(async (path) => {
      if (path === "/api/tasks") {
        return {
          tasks: [
            { id: "task-attention", name: "等待数据库审批", latest_run: { id: "run-attention", status: "WAITING_APPROVAL", iteration: 1, used_tokens: 800, used_cost: 0.08 } },
            { id: "task-done", name: "已完成报告", latest_run: { id: "run-done", status: "COMPLETED", iteration: 2, used_tokens: 1600, used_cost: 0.16 } },
          ],
        };
      }
      if (path === "/api/task-drafts") return draft();
      throw new Error(`unexpected request: ${path}`);
    });
    render(<HomePage />);
    expect(await screen.findByText("等待数据库审批")).toBeInTheDocument();
    await user.type(screen.getByLabelText("描述想完成的目标"), "新增一个可靠功能");
    await user.click(screen.getByRole("button", { name: "生成建议配置" }));
    await screen.findByRole("heading", { name: "确认这份配置，就可以开始" });
    expect(screen.getByText("等待数据库审批")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /处理审批/ })).toHaveAttribute("href", "/runs/run-attention");
    await user.type(screen.getByPlaceholderText("搜索最近任务"), "等待数据库");
    expect(screen.getByText("等待数据库审批")).toBeInTheDocument();
    expect(screen.queryByText("已完成报告")).not.toBeInTheDocument();
  });

  it("lets the operator select an engine and keeps it through refinement", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockResolvedValueOnce(draft()).mockResolvedValueOnce(draft());
    render(<HomeTaskIntake />);
    await user.type(screen.getByLabelText("描述想完成的目标"), "修复一个编码问题");
    await user.keyboard("{Enter}");
    const selector = await screen.findByRole("combobox", { name: "执行 Agent" });
    await user.selectOptions(selector, "gemini-cli");
    expect(selector).toHaveValue("gemini-cli");
    await user.type(screen.getByLabelText("描述想完成的目标"), "再补一个测试");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("combobox", { name: "执行 Agent" })).toHaveValue("gemini-cli"));
  });

  it("keeps Shift+Enter as a newline", async () => {
    const user = userEvent.setup();
    render(<HomeTaskIntake />);
    const input = screen.getByLabelText("描述想完成的目标");
    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");
    expect(input).toHaveValue("第一行\n第二行");
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it("deletes a completed standalone task only after confirmation", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockImplementation(async (path, init) => {
      if (path === "/api/tasks" && !init) return { tasks: [{ id: "task-done", name: "旧任务", latest_run: { id: "run-done", status: "COMPLETED", iteration: 1, used_tokens: 10, used_cost: 0 } }] };
      if (path === "/api/tasks/task-done" && init?.method === "DELETE") return undefined;
      throw new Error(`unexpected request: ${path}`);
    });
    render(<HomePage />);
    await screen.findByText("旧任务");
    await user.click(screen.getByRole("button", { name: "删除任务 旧任务" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("删除“旧任务”");
    await user.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(screen.queryByText("旧任务")).not.toBeInTheDocument());
  });
});
