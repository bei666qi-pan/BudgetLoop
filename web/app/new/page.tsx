"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AlertCircle, ArrowRight, Bug, Check, FlaskConical, Folder, LocateFixed, Rocket, ShieldAlert, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { apiFetch, idempotencyKey } from "@/lib/api";
import { BUDGET_PRESETS, validateTaskDraft, type BudgetPreset, type TaskErrors } from "@/lib/task-form";
import type { BudgetConfig, CreateTaskResponse, FolderAccess, Strategy, TaskTemplate } from "@/lib/types";

const TEMPLATES: { id: TaskTemplate; label: string; description: string; Icon: typeof Bug }[] = [
  { id: "fix_bug", label: "修复问题", description: "定位根因并验证修复", Icon: Bug },
  { id: "locate_issue", label: "定位问题", description: "调查并输出诊断结论", Icon: LocateFixed },
  { id: "add_tests", label: "补充测试", description: "增加可靠的回归保护", Icon: FlaskConical },
  { id: "small_feature", label: "小型功能", description: "交付范围明确的能力", Icon: Sparkles },
  { id: "fix_build", label: "修复构建", description: "解决类型、依赖或 CI 失败", Icon: Wrench },
];

const STRATEGIES: { id: Strategy; label: string; description: string }[] = [
  { id: "dynamic", label: "动态调度（推荐）", description: "根据进展和剩余资源调整阶段分配，但不会超过硬上限。" },
  { id: "fixed", label: "固定分配", description: "保持固定预算节奏，只在硬限制处停止。" },
  { id: "none", label: "仅硬限制", description: "不使用动态重分配，适合基线对照。" },
];

const PRESET_COPY: { id: BudgetPreset; label: string; description: string }[] = [
  { id: "light", label: "轻量", description: "快速排查" }, { id: "standard", label: "标准（推荐）", description: "平衡效率与成本" }, { id: "deep", label: "深度", description: "复杂任务与充分验证" },
];

const FOLDER_ACCESS_MODES: { id: FolderAccess; label: string; description: string }[] = [
  { id: "isolated", label: "隔离工作区", description: "Agent 在隔离容器工作区内操作，不会修改你的文件夹。" },
  { id: "full_access", label: "完全访问模式", description: "Agent 将直接读写所选文件夹（包括其中的 .git），仅用于你信任的项目。" },
];

const BUDGET_FIELDS: { key: keyof BudgetConfig; label: string; suffix: string; step?: number }[] = [
  { key: "max_total_tokens", label: "Token 上限", suffix: "tokens" }, { key: "max_wall_time_seconds", label: "绝对截止", suffix: "秒" },
  { key: "max_active_runtime_seconds", label: "执行时间", suffix: "秒" }, { key: "max_llm_calls", label: "调用次数", suffix: "次" },
  { key: "max_cost", label: "费用上限", suffix: "USD", step: 0.5 }, { key: "max_parallel_llm_calls", label: "并发调用", suffix: "个" },
];

function FieldError({ error }: { error?: string }) { return error ? <p className="field-error" role="alert">{error}</p> : null; }

export default function NewTaskPage() {
  const router = useRouter();
  const [template, setTemplate] = useState<TaskTemplate>("fix_bug");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [acceptance, setAcceptance] = useState("");
  const [workdir, setWorkdir] = useState("/workspace/project");
  const [projectDir, setProjectDir] = useState("");
  const [folderAccess, setFolderAccess] = useState<FolderAccess>("isolated");
  const [requireApproval, setRequireApproval] = useState(true);
  const [strategy, setStrategy] = useState<Strategy>("dynamic");
  const [preset, setPreset] = useState<BudgetPreset>("standard");
  const [budget, setBudget] = useState<BudgetConfig>({ ...BUDGET_PRESETS.standard });
  const [errors, setErrors] = useState<TaskErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [folderPickerError, setFolderPickerError] = useState<string | null>(null);

  const selectPreset = (next: BudgetPreset) => { setPreset(next); setBudget({ ...BUDGET_PRESETS[next] }); setErrors({}); };
  const setBudgetValue = (key: keyof BudgetConfig, value: number) => { setBudget((current) => ({ ...current, [key]: value })); setErrors((current) => ({ ...current, [key]: undefined })); };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors = validateTaskDraft({ name, description, workdir, projectDir, folderAccess, budget });
    setErrors(nextErrors); setSubmitError(null);
    if (Object.keys(nextErrors).length > 0 || submitting) return;
    setSubmitting(true);
    try {
      const result = await apiFetch<CreateTaskResponse>("/api/tasks", { method: "POST", headers: { "Idempotency-Key": idempotencyKey() }, body: JSON.stringify({ name: name.trim(), description: description.trim(), workdir: workdir.trim(), acceptance_criteria: acceptance.trim() || null, template, strategy, require_approval: requireApproval, budget, project_dir: projectDir.trim() || null, folder_access: folderAccess }) });
      router.push(`/runs/${result.run_id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "任务创建失败，请检查配置后重试。");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="page-shell animate-in space-y-7">
      <header className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end"><div><h1 className="page-heading">配置任务</h1><p className="page-subtitle">先定义目标，再决定 Agent 可以使用多少资源</p></div><ol className="flex max-w-full items-center gap-2 overflow-x-auto text-xs font-semibold text-muted-foreground" aria-label="配置步骤">{["定义目标", "工作区与安全", "预算策略", "确认并启动"].map((label, index) => <li key={label} className="flex shrink-0 items-center gap-2"><span className={`flex h-7 w-7 items-center justify-center rounded-full border ${index === 0 ? "border-accent bg-accent text-white" : "border-border-strong bg-white"}`}>{index + 1}</span>{label}{index < 3 ? <span className="mx-1 h-px w-8 bg-border" /> : null}</li>)}</ol></header>

      <form onSubmit={submit} noValidate className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="surface divide-y divide-border overflow-hidden">
          <section className="p-5 sm:p-7"><h2 className="section-title">1. 定义目标</h2><div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-5">{TEMPLATES.map(({ id, label, description: hint, Icon }) => <button key={id} type="button" onClick={() => setTemplate(id)} aria-pressed={template === id} className={`min-h-24 rounded-lg border p-3 text-left transition-all ${template === id ? "border-accent bg-accent/5 text-accent ring-4 ring-accent/5" : "border-border bg-white text-muted-foreground hover:border-border-strong hover:text-foreground"}`}><span className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4" />{label}</span><span className="mt-2 block text-xs leading-relaxed">{hint}</span></button>)}</div>
            <div className="mt-6 grid gap-5"><label><span className="field-label">任务名称</span><input value={name} onChange={(e) => { setName(e.target.value); setErrors((current) => ({ ...current, name: undefined })); }} aria-invalid={Boolean(errors.name)} className="input-base mt-2 w-full" placeholder="例如：修复订单接口并发超扣" /><FieldError error={errors.name} /></label><label><span className="field-label">任务描述</span><textarea value={description} onChange={(e) => { setDescription(e.target.value); setErrors((current) => ({ ...current, description: undefined })); }} aria-invalid={Boolean(errors.description)} className="input-base mt-2 min-h-28 w-full resize-y" placeholder="说明问题、期望结果和已知约束。" /><FieldError error={errors.description} /></label><label><span className="field-label">验收条件 <span className="font-normal text-muted-foreground">（可选）</span></span><textarea value={acceptance} onChange={(e) => setAcceptance(e.target.value)} className="input-base mt-2 min-h-20 w-full resize-y" placeholder="例如：并发测试全部通过，库存永不为负。" /></label></div>
          </section>

          <section className="p-5 sm:p-7"><h2 className="section-title">2. 工作区与安全</h2><div className="mt-5 grid gap-5"><label><span className="field-label">工作目录</span><div className="relative mt-2"><Folder className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input value={workdir} onChange={(e) => { setWorkdir(e.target.value); setErrors((current) => ({ ...current, workdir: undefined })); }} aria-invalid={Boolean(errors.workdir)} className="input-base w-full pl-10 font-mono" /></div><FieldError error={errors.workdir} /></label><div><span className="field-label">权限模式</span><div className="mt-2 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="权限模式">{FOLDER_ACCESS_MODES.map((mode) => <label key={mode.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-all ${folderAccess === mode.id ? mode.id === "full_access" ? "border-warning bg-warning/5 ring-4 ring-warning/10" : "border-accent bg-accent/5 ring-4 ring-accent/5" : "border-border bg-white hover:border-border-strong"}`}><input type="radio" name="folder_access" value={mode.id} checked={folderAccess === mode.id} onChange={() => { setFolderAccess(mode.id); setFolderPickerError(null); setErrors((current) => ({ ...current, projectDir: undefined })); }} className="mt-1 h-4 w-4 shrink-0" /><span><span className="font-semibold">{mode.label}</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{mode.description}</span></span></label>)}</div>{folderAccess === "full_access" ? <div role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs leading-relaxed text-warning"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /><span>高风险：Agent 将直接读写所选文件夹（包括其中的 .git），仅用于你信任的项目。</span></div> : null}</div><div><div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><label><span className="field-label">项目文件夹 <span className="font-normal text-muted-foreground">（可选，仅完全访问模式使用）</span></span><div className="relative mt-2"><Folder className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input id="new-project-dir" name="project_dir" value={projectDir} onChange={(e) => { setProjectDir(e.target.value); setFolderPickerError(null); setErrors((current) => ({ ...current, projectDir: undefined })); }} aria-invalid={Boolean(errors.projectDir)} className="input-base w-full pl-10 font-mono" placeholder="例如：/Users/you/my-project" /></div><FieldError error={errors.projectDir} /></label></div>{folderPickerError ? <p role="alert" className="field-error">{folderPickerError}</p> : null}</div><button type="button" role="switch" aria-checked={requireApproval} onClick={() => setRequireApproval((value) => !value)} className="flex w-full items-center gap-4 rounded-lg border border-border bg-muted/30 p-4 text-left hover:border-border-strong"><span className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${requireApproval ? "bg-accent" : "bg-border-strong"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-transform ${requireApproval ? "translate-x-6" : "translate-x-1"}`} /></span><span><span className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4" />高风险操作需人工确认</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">删除文件、修改敏感配置或执行高风险命令前，Agent 会暂停并请求确认。</span></span></button></div></section>

          <section className="p-5 sm:p-7"><h2 className="section-title">3. 预算策略</h2><div className="mt-5 grid gap-3 md:grid-cols-3">{STRATEGIES.map((item) => <button key={item.id} type="button" onClick={() => setStrategy(item.id)} aria-pressed={strategy === item.id} className={`rounded-lg border p-4 text-left ${strategy === item.id ? "border-accent bg-accent/5 ring-4 ring-accent/5" : "border-border bg-white hover:border-border-strong"}`}><span className="flex items-center justify-between font-semibold">{item.label}{strategy === item.id ? <Check className="h-4 w-4 text-accent" /> : null}</span><span className="mt-2 block text-xs leading-relaxed text-muted-foreground">{item.description}</span></button>)}</div><div className="mt-6 grid gap-3 sm:grid-cols-3">{PRESET_COPY.map((item) => <button key={item.id} type="button" onClick={() => selectPreset(item.id)} aria-pressed={preset === item.id} className={`rounded-lg border px-4 py-3 text-left ${preset === item.id ? "border-accent bg-accent/5 text-accent" : "border-border bg-white"}`}><span className="font-semibold">{item.label}</span><span className="mt-1 block text-xs text-muted-foreground">{item.description}</span></button>)}</div><div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{BUDGET_FIELDS.map((field) => <label key={field.key}><span className="text-xs font-semibold text-muted-foreground">{field.label}</span><div className="relative mt-1.5"><input type="number" min="0" step={field.step ?? 1} value={budget[field.key]} onChange={(e) => setBudgetValue(field.key, Number(e.target.value))} aria-invalid={Boolean(errors[field.key])} className="input-base w-full pr-16 font-mono tabular-nums" /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">{field.suffix}</span></div><FieldError error={errors[field.key]} /></label>)}</div></section>
        </div>

        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start"><section className="surface p-5"><h2 className="section-title">任务预览</h2><dl className="mt-5 space-y-4 text-sm"><div><dt className="text-xs text-muted-foreground">任务</dt><dd className="mt-1 font-semibold">{name.trim() || "尚未填写任务名称"}</dd></div><div><dt className="text-xs text-muted-foreground">类型</dt><dd className="mt-1">{TEMPLATES.find((item) => item.id === template)?.label}</dd></div><div><dt className="text-xs text-muted-foreground">工作目录</dt><dd className="mt-1 break-all font-mono text-xs">{workdir}</dd></div><div><dt className="text-xs text-muted-foreground">策略与预算</dt><dd className="mt-1">{STRATEGIES.find((item) => item.id === strategy)?.label} · {PRESET_COPY.find((item) => item.id === preset)?.label}</dd></div><div><dt className="text-xs text-muted-foreground">安全设置</dt><dd className={`mt-1 font-semibold ${requireApproval ? "text-success" : "text-warning"}`}>{requireApproval ? "人工确认已启用" : "不要求人工确认"}</dd></div></dl><div className="mt-5 rounded-lg border border-accent/15 bg-accent/5 p-3 text-xs leading-relaxed text-muted-foreground">实际消耗受硬限制约束，不会超过这里配置的上限。</div></section>{submitError ? <div role="alert" className="rounded-lg border border-critical/20 bg-critical/5 p-4 text-sm text-critical"><div className="flex items-start gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{submitError}</span></div></div> : null}<button type="submit" disabled={submitting} className="btn btn-primary w-full min-h-12"><Rocket className="h-4 w-4" />{submitting ? "正在启动…" : "启动任务"}<ArrowRight className="h-4 w-4" /></button><Link href="/" className="btn btn-secondary w-full">返回任务工作台</Link></aside>
      </form>
    </div>
  );
}
