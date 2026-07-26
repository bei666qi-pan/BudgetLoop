"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Folder, GitBranch, Layers3, LoaderCircle, Settings2, Sparkles, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GoalRecommender } from "@/components/containers/GoalRecommender";
import { ExecutionEnginePicker } from "@/components/containers/ExecutionEnginePicker";
import { PresetBrowser } from "@/components/containers/PresetBrowser";
import { PresetRoleList } from "@/components/containers/PresetRoleList";
import { PresetSources } from "@/components/containers/PresetSources";
import { TeamPresetPreview } from "@/components/containers/TeamPresetPreview";
import { ApiError, apiFetch, idempotencyKey } from "@/lib/api";
import { deriveProjectName, roleBoundsValid, roleBudgetValid, roleDrafts, roleOverride } from "@/lib/team-presets";
import type {
  CreateTeamFromPresetRequest,
  CreateTeamFromPresetResponse,
  CreateWorkContainerRequest,
  AIGatewayStatus,
  ExecutionEngineInfo,
  ExecutionEnginesResponse,
  TeamPreset,
  TeamPresetCatalogResponse,
  TeamPresetRecommendation,
  TeamPresetRecommendationResponse,
  TeamRoleDraft,
  WorkContainer,
  WorkspacePolicy,
} from "@/lib/types";

type PageMode = "smart" | "browse";
type BusyAction = "start" | "later" | "manual" | null;
type TeamMode = "guided" | "autonomous";
type BudgetMode = "bounded" | "max";

const MODE_OPTIONS = [
  { value: "smart" as const, label: "智能推荐", icon: Sparkles },
  { value: "browse" as const, label: "浏览模板", icon: UsersRound },
];

export default function NewContainerPage() {
  const router = useRouter();
  const [mode, setMode] = useState<PageMode>("smart");
  const [manualMode, setManualMode] = useState(false);
  const [catalog, setCatalog] = useState<TeamPresetCatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [engines, setEngines] = useState<ExecutionEngineInfo[]>([]);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [gatewayStatus, setGatewayStatus] = useState<AIGatewayStatus | null>(null);
  const [gatewayStatusError, setGatewayStatusError] = useState<string | null>(null);
  const [defaultEngine, setDefaultEngine] = useState("openhands");
  const [teamMode, setTeamMode] = useState<TeamMode>("guided");
  const [budgetMode, setBudgetMode] = useState<BudgetMode>("bounded");
  const [goal, setGoal] = useState("");
  const [industry, setIndustry] = useState("");
  const [pace, setPace] = useState<"steady" | "fast">("steady");
  const [risk, setRisk] = useState<"steady" | "balanced" | "creative">("balanced");
  const [recommendations, setRecommendations] = useState<TeamPresetRecommendation[]>([]);
  const [recommending, setRecommending] = useState(false);
  const [recommendError, setRecommendError] = useState<string | null>(null);
  const [recommendationRuntime, setRecommendationRuntime] = useState<TeamPresetRecommendationResponse | null>(null);
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<TeamPreset | null>(null);
  const [roles, setRoles] = useState<TeamRoleDraft[]>([]);
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [sharedContext, setSharedContext] = useState("");
  const [workdir, setWorkdir] = useState("/workspace/project");
  const [policy, setPolicy] = useState<WorkspacePolicy>("isolated");
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const requestSequence = useRef(0);
  const creationKey = useRef<string | null>(null);

  const selectPreset = useCallback((preset: TeamPreset) => {
    setSelected(preset);
    setRoles(roleDrafts(preset));
    setPolicy(preset.default_workspace_policy);
    setName((current) => current.trim() ? current : deriveProjectName(goal, preset));
  }, [goal]);

  useEffect(() => {
    let active = true;
    void Promise.allSettled([
      apiFetch<TeamPresetCatalogResponse>("/api/work-container-presets"),
      apiFetch<ExecutionEnginesResponse>("/api/execution-engines"),
      apiFetch<AIGatewayStatus>("/api/ai-gateway/status"),
    ]).then(([catalogResult, engineResult, gatewayResult]) => {
      if (!active) return;
      if (catalogResult.status === "fulfilled") setCatalog(catalogResult.value);
      else setCatalogError(catalogResult.reason instanceof Error ? catalogResult.reason.message : "团队模板加载失败。");
      if (engineResult.status === "fulfilled") {
        setEngines(engineResult.value.engines);
        setDefaultEngine(engineResult.value.default_engine);
      } else {
        setEngineError(engineResult.reason instanceof Error ? engineResult.reason.message : "执行引擎目录加载失败。");
      }
      if (gatewayResult.status === "fulfilled") setGatewayStatus(gatewayResult.value);
      else setGatewayStatusError("暂时无法读取 AI 网关状态。");
    });
    return () => { active = false; };
  }, []);

  const requestRecommendations = useCallback(async (targetGoal: string, signal?: AbortSignal) => {
    if (targetGoal.trim().length < 3) return;
    const sequence = ++requestSequence.current;
    setRecommending(true);
    setRecommendError(null);
    try {
      const result = await apiFetch<TeamPresetRecommendationResponse>("/api/work-container-presets/recommend", {
        method: "POST",
        signal,
        body: JSON.stringify({ goal: targetGoal.trim(), industry: industry.trim() || null, pace, risk }),
      });
      if (signal?.aborted || sequence !== requestSequence.current) return;
      setRecommendations(result.recommendations);
      setRecommendationRuntime(result);
      if (result.recommendations[0]) selectPreset(result.recommendations[0].preset);
    } catch (error) {
      if (!signal?.aborted && sequence === requestSequence.current) setRecommendError(error instanceof Error ? error.message : "暂时无法完成推荐，请浏览模板。");
    } finally {
      if (!signal?.aborted && sequence === requestSequence.current) setRecommending(false);
    }
  }, [industry, pace, risk, selectPreset]);

  useEffect(() => {
    if (mode !== "smart" || goal.trim().length < 6) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => void requestRecommendations(goal, controller.signal), 650);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [goal, industry, mode, pace, requestRecommendations, risk]);

  const valid = useMemo(() => Boolean(
    selected
    && name.trim()
    && goal.trim().length >= 3
    && workdir.startsWith("/")
    && roleBoundsValid(roles)
    && roles.filter((role) => role.enabled).every((role) => role.role.trim() && role.goal.trim() && roleBudgetValid(role.budget)),
  ), [goal, name, roles, selected, workdir]);

  const startValid = useMemo(() => {
    const available = new Set(engines.filter((engine) => engine.runtime_available).map((engine) => engine.id));
    return roles.filter((role) => role.enabled).every((role) => available.has(role.execution_engine));
  }, [engines, roles]);

  function changeGoal(value: string) {
    setGoal(value);
    setSubmitError(null);
    setRecommendationRuntime(null);
    if (!nameEdited) setName(deriveProjectName(value, selected));
  }

  function chooseRecommendation(recommendation: TeamPresetRecommendation) {
    selectPreset(recommendation.preset);
    setManualMode(false);
  }

  function switchMode(nextMode: PageMode) {
    setMode(nextMode);
    setManualMode(false);
    if (nextMode === "browse" && !selected && catalog?.presets[0]) selectPreset(catalog.presets[0]);
  }

  function selectDefaultEngine(engineId: string) {
    setDefaultEngine(engineId);
    setRoles((current) => current.map((role) => ({ ...role, execution_engine: engineId })));
  }

  async function createPresetTeam(startImmediately: boolean) {
    if (!selected || !valid) return;
    setBusyAction(startImmediately ? "start" : "later");
    setSubmitError(null);
    creationKey.current ??= idempotencyKey();
    const body: CreateTeamFromPresetRequest = {
      preset_id: selected.id,
      preset_version: selected.version,
      name: name.trim(),
      project_goal: goal.trim(),
      shared_context: sharedContext.trim(),
      base_workdir: workdir.trim(),
      default_workspace_policy: policy,
      role_overrides: roles.map(roleOverride),
      start_immediately: startImmediately,
      default_execution_engine: defaultEngine,
      team_mode: teamMode,
      budget_mode: budgetMode,
    };
    try {
      const result = await apiFetch<CreateTeamFromPresetResponse>("/api/work-containers/from-preset", {
        method: "POST",
        headers: { "Idempotency-Key": creationKey.current },
        body: JSON.stringify(body),
      });
      router.push(`/containers/${result.container.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "团队创建失败，请重试。");
      if (error instanceof ApiError && error.status !== null && error.status < 500) creationKey.current = null;
      setBusyAction(null);
    }
  }

  async function createManualContainer() {
    const manualValid = name.trim() && goal.trim().length >= 3 && workdir.startsWith("/");
    if (!manualValid) return;
    setBusyAction("manual");
    setSubmitError(null);
    const body: CreateWorkContainerRequest = {
      name: name.trim(), project_goal: goal.trim(), shared_context: sharedContext.trim(), base_workdir: workdir.trim(), default_workspace_policy: policy,
    };
    try {
      const created = await apiFetch<WorkContainer>("/api/work-containers", { method: "POST", body: JSON.stringify(body) });
      router.push(`/containers/${created.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "空白容器创建失败。");
      setBusyAction(null);
    }
  }

  return (
    <div className="page-shell animate-in pb-56 xl:pb-10">
      <Link href="/containers" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />返回 Agent Team</Link>
      <header className="mt-6 max-w-3xl"><div className="flex items-center gap-2 text-xs font-semibold text-accent"><span className="h-1.5 w-1.5 rounded-full bg-accent" />无需配置，创建后即可工作</div><h1 className="page-heading mt-3">创建 Agent Team</h1><p className="page-subtitle">告诉我们项目目标，BudgetLoop 会从经过验证的开源协作模式中组装一支隔离、可审计且有硬预算的团队。</p></header>

      <div className="mt-7 inline-flex rounded-xl border border-border bg-white p-1 shadow-control" role="tablist" aria-label="创建方式">{MODE_OPTIONS.map((option) => <button key={option.value} type="button" role="tab" aria-selected={!manualMode && mode === option.value} onClick={() => switchMode(option.value)} className={`flex min-h-10 items-center gap-2 rounded-lg px-4 text-sm font-semibold transition ${!manualMode && mode === option.value ? "bg-accent text-white shadow-control" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><option.icon className="h-4 w-4" />{option.label}</button>)}</div>

      {catalogError || engineError ? <div role="alert" className="mt-6 rounded-xl border border-critical/20 bg-critical/5 p-4 text-sm text-critical">{catalogError ?? engineError}<button type="button" onClick={() => window.location.reload()} className="ml-2 font-semibold underline">重新加载</button></div> : null}

      {manualMode ? (
        <section className="surface mt-6 max-w-3xl overflow-hidden"><div className="border-b border-border px-5 py-5 sm:px-7"><h2 className="section-title">创建空白工作容器</h2><p className="mt-1 text-sm text-muted-foreground">保留原有高级路径：只创建容器，之后自行逐个添加 Session。</p></div><div className="space-y-5 p-5 sm:p-7"><label className="block"><span className="field-label">容器名称</span><input value={name} onChange={(event) => { setName(event.target.value); setNameEdited(true); }} className="input-base mt-2 w-full" /></label><label className="block"><span className="field-label">项目目标</span><textarea value={goal} onChange={(event) => changeGoal(event.target.value)} rows={4} className="input-base mt-2 w-full resize-y" /></label><WorkspaceSettings name={name} setName={(value) => { setName(value); setNameEdited(true); }} sharedContext={sharedContext} setSharedContext={setSharedContext} workdir={workdir} setWorkdir={setWorkdir} policy={policy} setPolicy={setPolicy} hideName /><div className="flex flex-wrap gap-3">{submitError ? <p role="alert" className="w-full text-sm text-critical">{submitError}</p> : null}<button type="button" onClick={() => void createManualContainer()} disabled={busyAction !== null || !name.trim() || goal.trim().length < 3 || !workdir.startsWith("/")} className="btn btn-primary">{busyAction === "manual" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}创建空白容器</button><button type="button" onClick={() => setManualMode(false)} className="btn btn-secondary">返回模板创建</button></div></div></section>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <main className="min-w-0 space-y-6">
            {mode === "smart" ? <GoalRecommender goal={goal} industry={industry} pace={pace} risk={risk} busy={recommending} recommendations={recommendations} gatewayStatus={gatewayStatus} gatewayStatusError={gatewayStatusError} recommendationRuntime={recommendationRuntime} selectedId={selected?.id ?? null} onGoalChange={changeGoal} onIndustryChange={setIndustry} onPaceChange={setPace} onRiskChange={setRisk} onRecommend={() => void requestRecommendations(goal)} onSelect={chooseRecommendation} /> : catalog ? <PresetBrowser presets={catalog.presets} categories={catalog.categories} category={category} selectedId={selected?.id ?? null} onCategoryChange={setCategory} onSelect={(preset) => { selectPreset(preset); if (!goal.trim()) setGoal(""); }} /> : <div className="surface p-7"><div className="skeleton h-7 w-52" /><div className="skeleton mt-5 h-24" /><div className="skeleton mt-3 h-24" /></div>}

            {recommendError ? <div role="alert" className="rounded-xl border border-warning/25 bg-warning/5 p-4 text-sm text-warning">{recommendError}</div> : null}

            {selected ? <><section className="surface overflow-hidden"><div className="border-b border-border bg-gradient-to-r from-white to-background px-5 py-5 sm:px-7"><div className="flex flex-wrap items-center gap-2"><span className="badge badge-info">已选择</span><span className="text-xs font-semibold text-muted-foreground">v{selected.version}</span></div><h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em]">{selected.name}</h2><p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{selected.summary}</p></div><div className="p-5 sm:p-7"><PresetSources sources={selected.sources} /></div></section><TeamAutonomySettings teamMode={teamMode} budgetMode={budgetMode} onTeamModeChange={setTeamMode} onBudgetModeChange={setBudgetMode} />{engines.length ? <ExecutionEnginePicker engines={engines} selectedId={defaultEngine} onSelect={selectDefaultEngine} /> : null}<PresetRoleList preset={selected} roles={roles} engines={engines} budgetMode={budgetMode} onChange={setRoles} /><details className="surface overflow-hidden"><summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-5 sm:px-7 [&::-webkit-details-marker]:hidden"><span className="flex items-center gap-3"><Settings2 className="h-4 w-4 text-accent" /><span><span className="block font-semibold">项目与工作区设置</span><span className="mt-0.5 block text-xs text-muted-foreground">名称、共享上下文、路径与 Worktree 策略</span></span></span><span className="text-xs font-semibold text-accent">展开设置</span></summary><div className="border-t border-border p-5 sm:p-7"><WorkspaceSettings name={name} setName={(value) => { setName(value); setNameEdited(true); }} sharedContext={sharedContext} setSharedContext={setSharedContext} workdir={workdir} setWorkdir={setWorkdir} policy={policy} setPolicy={setPolicy} /></div></details></> : mode === "smart" ? <section className="rounded-xl border border-dashed border-border-strong bg-white/55 px-6 py-10 text-center"><Sparkles className="mx-auto h-6 w-6 text-accent" /><h2 className="mt-3 font-semibold">描述目标后，团队会在这里就绪</h2><p className="mt-1 text-sm text-muted-foreground">你也可以切换到“浏览模板”直接选择。</p></section> : null}

            <button type="button" onClick={() => setManualMode(true)} className="btn btn-ghost w-full border border-dashed border-border-strong">高级用户：不使用模板，创建空白容器</button>
          </main>
          {selected ? <TeamPresetPreview preset={selected} roles={roles} teamMode={teamMode} budgetMode={budgetMode} valid={valid} startValid={startValid} busyAction={busyAction === "manual" ? null : busyAction} error={!roleBoundsValid(roles) ? "请启用 2–8 个角色。" : !startValid ? "所选引擎尚未在 worker 运行时启用；可以先创建，稍后启用再启动。" : submitError} onSubmit={(start) => void createPresetTeam(start)} /> : null}
        </div>
      )}
    </div>
  );
}

function TeamAutonomySettings({ teamMode, budgetMode, onTeamModeChange, onBudgetModeChange }: { teamMode: TeamMode; budgetMode: BudgetMode; onTeamModeChange: (mode: TeamMode) => void; onBudgetModeChange: (mode: BudgetMode) => void; }) {
  return <section className="surface overflow-hidden"><div className="border-b border-border px-5 py-5 sm:px-7"><h2 className="section-title">协作与预算</h2><p className="mt-1 text-sm text-muted-foreground">自主模式按团队阶段并行工作，并将已完成角色的公开输出自动 Handoff 给下一阶段。</p></div><div className="space-y-5 p-5 sm:p-7"><fieldset><legend className="field-label">团队模式</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{[{ id: "guided" as const, title: "引导模式", text: "沿用当前启动方式与人工 Handoff。" }, { id: "autonomous" as const, title: "智能自主模式", text: "角色自行拆解子任务；同阶段并行，依赖阶段自动 Handoff。" }].map((option) => <button key={option.id} type="button" onClick={() => onTeamModeChange(option.id)} aria-pressed={teamMode === option.id} className={`rounded-xl border p-4 text-left ${teamMode === option.id ? "border-accent/35 bg-accent/5 ring-4 ring-accent/5" : "border-border hover:border-border-strong"}`}><span className="block text-sm font-semibold">{option.title}</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{option.text}</span></button>)}</div></fieldset><fieldset><legend className="field-label">预算设置</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{[{ id: "bounded" as const, title: "受限预算", text: "保留每个角色的 Token、调用、成本与时间上限。" }, { id: "max" as const, title: "Max · 无上限", text: "不自动停止；由 AI 在验收完成后收尾，或由你手动暂停/取消。" }].map((option) => <button key={option.id} type="button" onClick={() => onBudgetModeChange(option.id)} aria-pressed={budgetMode === option.id} className={`rounded-xl border p-4 text-left ${budgetMode === option.id ? "border-warning/40 bg-warning/5 ring-4 ring-warning/5" : "border-border hover:border-border-strong"}`}><span className="block text-sm font-semibold">{option.title}</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{option.text}</span></button>)}</div>{budgetMode === "max" ? <p role="note" className="mt-3 rounded-lg border border-warning/25 bg-warning/5 px-3 py-2 text-xs leading-relaxed text-warning">Max 仍会记录用量，并保留工作区隔离、高风险审批与暂停/取消控制；它只移除自动预算和轮次上限。</p> : null}</fieldset></div></section>;
}

interface WorkspaceSettingsProps {
  name: string;
  setName: (value: string) => void;
  sharedContext: string;
  setSharedContext: (value: string) => void;
  workdir: string;
  setWorkdir: (value: string) => void;
  policy: WorkspacePolicy;
  setPolicy: (value: WorkspacePolicy) => void;
  hideName?: boolean;
}

function WorkspaceSettings({ name, setName, sharedContext, setSharedContext, workdir, setWorkdir, policy, setPolicy, hideName = false }: WorkspaceSettingsProps) {
  return <div className="space-y-5">{!hideName ? <label className="block"><span className="field-label">项目名称</span><input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} placeholder="例如：星港谜案试玩版" className="input-base mt-2 w-full" /></label> : null}<label className="block"><span className="field-label">共享上下文 <span className="font-normal text-muted-foreground">（可选）</span></span><textarea value={sharedContext} onChange={(event) => setSharedContext(event.target.value)} rows={4} maxLength={30000} placeholder="所有角色都必须遵守的事实、约束和验收边界" className="input-base mt-2 w-full resize-y" /><span className="field-hint">只有这里的内容与明确 Handoff 会跨 Session；独立对话不会自动互通。</span></label><label className="block"><span className="field-label">基础工作目录</span><span className="relative mt-2 block"><Folder className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input value={workdir} onChange={(event) => setWorkdir(event.target.value)} className="input-base w-full pl-10 font-mono" /></span>{!workdir.startsWith("/") ? <span className="field-error">请输入绝对路径。</span> : null}</label><fieldset><legend className="field-label">Session 工作区</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{[{ id: "isolated" as const, title: "独立工作区", text: "使用隔离的运行工作区", icon: Layers3 }, { id: "worktree" as const, title: "独立 Worktree", text: "每个 Session 独立分支", icon: GitBranch }].map((option) => <button key={option.id} type="button" onClick={() => setPolicy(option.id)} aria-pressed={policy === option.id} className={`rounded-xl border p-4 text-left ${policy === option.id ? "border-accent/35 bg-accent/5 ring-4 ring-accent/5" : "border-border hover:border-border-strong"}`}><span className="flex items-center justify-between"><option.icon className="h-4 w-4 text-accent" />{policy === option.id ? <Check className="h-4 w-4 text-accent" /> : null}</span><span className="mt-3 block text-sm font-semibold">{option.title}</span><span className="mt-1 block text-xs text-muted-foreground">{option.text}</span></button>)}</div></fieldset></div>;
}
