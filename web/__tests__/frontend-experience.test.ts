import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { filterTasks, statusClass, taskCounts, taskFilterOf } from "@/lib/presentation";
import { BUDGET_PRESETS, validateTaskDraft } from "@/lib/task-form";
import { budgetUsageRatio, folderAccessMode, pressureExplanation, runPhaseLabel } from "@/lib/run-presentation";
import { averageScore, outcomeTone } from "@/lib/report-presentation";
import type { TaskListItem } from "@/lib/types";

const tasks: TaskListItem[] = [
  { id: "t-1", name: "修复并发问题", latest_run: { id: "r-1", status: "EXECUTING", iteration: 2, used_tokens: 1000, used_cost: 0.1 } },
  { id: "t-2", name: "补充测试", latest_run: { id: "r-2", status: "WAITING_APPROVAL", iteration: 1, used_tokens: 500, used_cost: 0.05 } },
  { id: "t-3", name: "完成报告", latest_run: { id: "r-3", status: "COMPLETED", iteration: 4, used_tokens: 4000, used_cost: 0.4 } },
  { id: "t-4", name: "尚未运行", latest_run: null },
];

describe("operator workspace presentation", () => {
  it("groups lifecycle statuses without hiding approvals", () => {
    expect(taskFilterOf("EXECUTING")).toBe("active");
    expect(taskFilterOf("WAITING_APPROVAL")).toBe("attention");
    expect(taskFilterOf(null)).toBe("pending");
    expect(taskCounts(tasks)).toEqual({ all: 4, active: 1, pending: 1, completed: 1, attention: 1 });
  });
  it("combines query and status filters", () => {
    expect(filterTasks(tasks, "补充", "attention").map((task) => task.id)).toEqual(["t-2"]);
    expect(filterTasks(tasks, "不存在", "all")).toEqual([]);
  });
  it("uses semantic status treatments", () => {
    expect(statusClass("COMPLETED")).toBe("badge-success");
    expect(statusClass("BUDGET_EXHAUSTED")).toBe("badge-critical");
  });
});

describe("shared interaction accessibility", () => {
  it("keeps a global reduced-motion contract for the conversational home", () => {
    const css = readFileSync(`${process.cwd()}/app/globals.css`, "utf8");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("transition-duration: .01ms !important");
  });
});

describe("guided task creation", () => {
  it("defines all API budget limits for every preset", () => {
    for (const preset of Object.values(BUDGET_PRESETS)) expect(Object.keys(preset)).toHaveLength(6);
  });
  it("rejects missing text, relative workspace and invalid runtime", () => {
    const errors = validateTaskDraft({ name: "", description: "", workdir: "relative/path", budget: { ...BUDGET_PRESETS.standard, max_active_runtime_seconds: 1300 } });
    expect(errors.name).toBeTruthy(); expect(errors.description).toBeTruthy(); expect(errors.workdir).toContain("绝对路径"); expect(errors.max_active_runtime_seconds).toBeTruthy();
  });
  it("accepts the standard safe configuration", () => {
    expect(validateTaskDraft({ name: "修复问题", description: "定位并修复竞态", workdir: "/workspace/project", budget: BUDGET_PRESETS.standard })).toEqual({});
  });
  it("blocks full access without an absolute project folder", () => {
    const base = { name: "修复问题", description: "定位并修复竞态", workdir: "/workspace/project", budget: BUDGET_PRESETS.standard };
    expect(validateTaskDraft({ ...base, folderAccess: "full_access", projectDir: "" }).projectDir).toBeTruthy();
    expect(validateTaskDraft({ ...base, folderAccess: "full_access", projectDir: "relative/path" }).projectDir).toContain("绝对路径");
    expect(validateTaskDraft({ ...base, folderAccess: "full_access", projectDir: "/Users/you/project" })).toEqual({});
  });
  it("does not require a project folder for the default isolated mode", () => {
    const base = { name: "修复问题", description: "定位并修复竞态", workdir: "/workspace/project", budget: BUDGET_PRESETS.standard };
    expect(validateTaskDraft({ ...base, folderAccess: "isolated", projectDir: "" })).toEqual({});
    expect(validateTaskDraft({ ...base, folderAccess: "isolated", projectDir: "relative/path" })).toEqual({});
  });
});

describe("run command center", () => {
  it("clamps used plus reserved budget to a readable ratio", () => {
    expect(budgetUsageRatio(40, 10, 100)).toBe(0.5);
    expect(budgetUsageRatio(120, 0, 100)).toBe(1);
    expect(budgetUsageRatio(10, 0, 0)).toBe(0);
  });
  it("explains pressure modes without color-only meaning", () => {
    expect(pressureExplanation("CONSERVATIVE")).toContain("剩余资源收紧");
    expect(pressureExplanation("CRITICAL")).toContain("接近上限");
  });
  it("marks full access distinctly from the isolated default", () => {
    expect(folderAccessMode("full_access")).toEqual({ label: "完全访问模式", badgeClass: "badge-warning" });
    expect(folderAccessMode("isolated")).toEqual({ label: "隔离工作区", badgeClass: "badge-success" });
    expect(folderAccessMode(undefined)).toEqual({ label: "隔离工作区", badgeClass: "badge-success" });
  });
  it("does not label a terminal run as preparing", () => {
    const labels = { scan: "扫描代码库" };
    expect(runPhaseLabel(null, true, labels)).toBe("已结束");
    expect(runPhaseLabel(null, false, labels)).toBe("准备中");
    expect(runPhaseLabel("scan", true, labels)).toBe("已结束");
    expect(runPhaseLabel("scan", false, labels)).toBe("扫描代码库");
  });
});

describe("outcome reporting", () => {
  it("distinguishes success, partial and failed outcomes", () => {
    expect(outcomeTone("COMPLETED", true)).toBe("success");
    expect(outcomeTone("BUDGET_EXHAUSTED", false)).toBe("warning");
    expect(outcomeTone("FAILED", false)).toBe("critical");
  });
  it("does not fabricate an average when scores are absent", () => {
    expect(averageScore([])).toBeNull();
    expect(averageScore([0.5, 1])).toBe(0.75);
  });
});
