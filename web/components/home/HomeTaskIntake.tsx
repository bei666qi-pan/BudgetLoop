"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  FileCheck2,
  Folder,
  FolderOpen,
  LockKeyhole,
  MessageSquareText,
  PencilLine,
  Send,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
  UsersRound,
} from "lucide-react";
import {
  FormEvent,
  KeyboardEvent,
  type RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { PresetRoleList } from "@/components/containers/PresetRoleList";
import { BudgetLoopActivityMark } from "@/components/brand/BudgetLoopActivityMark";
import { ApiError, apiFetch, idempotencyKey, uploadProjectFolder } from "@/lib/api";
import {
  createTeamRequestFromDraft,
  DEFAULT_WORKSPACE_ACCESS,
  editableTaskDraft,
  rolesForTaskDraft,
  teamDraftError,
} from "@/lib/home-draft";
import { aggregateTeamBudget, enabledRoles } from "@/lib/team-presets";
import type {
  CreateTaskDraftRequest,
  CreateTeamFromPresetResponse,
  ProjectUploadSummary,
  TaskSetupDraft,
  TeamRoleDraft,
  WorkspaceAccessSelection,
} from "@/lib/types";

declare global {
  interface Window {
    budgetloopSetProjectDir?: (path: string) => void;
    webkit?: {
      messageHandlers?: {
        budgetloopPickProjectDir?: { postMessage: (value: null) => void };
      };
    };
  }
}

const EXAMPLES = [
  "修复订单接口并发超扣，并补充回归测试",
  "做一个可安装、可通关的移动解谜游戏试玩版",
  "分析这批销售数据，找出下滑原因并给出行动建议",
];

type PlanningState = "idle" | "planning" | "ready" | "needs_input" | "error";

function DraftProvenance({ draft }: { draft: TaskSetupDraft }) {
  const ai = draft.provenance.source === "ai";
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 font-medium hover:text-foreground [&::-webkit-details-marker]:hidden">
        {ai ? <Sparkles className="h-3.5 w-3.5 text-accent" /> : <ShieldCheck className="h-3.5 w-3.5" />}
        {ai ? "AI 建议 · 已校验" : "本地建议 · AI 暂不可用"}<ChevronDown className="h-3 w-3" />
      </summary>
      <p className="mt-2 max-w-2xl rounded-lg bg-muted/35 px-3 py-2 leading-relaxed">{draft.provenance.explanation}{draft.provenance.fallback_reason ? `（${draft.provenance.fallback_reason}）` : ""}</p>
    </details>
  );
}

interface ReviewProps {
  focusRef: RefObject<HTMLElement | null>;
  draft: TaskSetupDraft;
  roles: TeamRoleDraft[];
  access: WorkspaceAccessSelection;
  confirming: boolean;
  confirmationError: string | null;
  onDraftChange: (draft: TaskSetupDraft) => void;
  onRolesChange: (roles: TeamRoleDraft[]) => void;
  onEngineChange: (engineId: string) => void;
  onAccessChange: (access: WorkspaceAccessSelection) => void;
  onConfirm: () => void;
  projectUpload: ProjectUploadSummary | null;
  onRequestBrowserUpload: () => void;
  nativePickerAvailable: boolean;
}

function TaskSetupReview({
  focusRef,
  draft,
  roles,
  access,
  confirming,
  confirmationError,
  onDraftChange,
  onRolesChange,
  onEngineChange,
  onAccessChange,
  onConfirm,
  projectUpload,
  onRequestBrowserUpload,
  nativePickerAvailable,
}: ReviewProps) {
  const enabled = enabledRoles(roles);
  const total = aggregateTeamBudget(roles);
  const validationError = teamDraftError(draft, roles, access);
  const [folderPickerError, setFolderPickerError] = useState<string | null>(null);
  const defaultEngine = draft.execution.engines.find(
    (engine) => engine.id === draft.execution.default_engine,
  );

  const updateIntent = (field: keyof TaskSetupDraft["intent"], value: string) => {
    onDraftChange({ ...draft, intent: { ...draft.intent, [field]: value } });
  };

  const changeAccess = (patch: Partial<WorkspaceAccessSelection>) => {
    onAccessChange({ ...access, ...patch, full_access_acknowledged: false });
  };

  const requestFolder = () => {
    const bridge = window.webkit?.messageHandlers?.budgetloopPickProjectDir;
    if (bridge) {
      setFolderPickerError(null);
      bridge.postMessage(null);
    } else {
      setFolderPickerError(null);
      onRequestBrowserUpload();
    }
  };

  return (
    <section
      ref={focusRef}
      tabIndex={-1}
      className="surface overflow-hidden"
      aria-labelledby="setup-review-heading"
    >
      <div className="border-b border-border bg-gradient-to-r from-white via-white to-accent/[0.035] px-5 py-5 sm:px-7 sm:py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-accent"><CheckCircle2 className="h-4 w-4" />建议配置已就绪</div>
            <h2 id="setup-review-heading" className="mt-2 text-xl font-semibold tracking-[-0.025em] sm:text-2xl">确认这份配置，就可以开始</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">所有内容都能修改；确认前不会创建任务、调用 Agent 或访问文件。</p>
          </div>
        </div>
      </div>

      <div className="space-y-5 p-5 sm:p-7">
        <div className="grid gap-4 rounded-xl border border-border bg-muted/20 p-4 md:grid-cols-[1fr_1.15fr]" aria-label="核心配置">
          <div><span className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><UsersRound className="h-4 w-4 text-accent" />Agent 团队</span><strong className="mt-2 block text-base">{draft.team.preset.name}</strong><span className="mt-1 block text-xs text-muted-foreground">{enabled.length} 个角色协作</span></div>
          <label><span className="field-label">执行 Agent</span><select aria-label="执行 Agent" value={draft.execution.default_engine} onChange={(event) => onEngineChange(event.target.value)} className="input-base mt-2 w-full">{draft.execution.engines.filter((engine) => ["openhands", "codex", "gemini-cli"].includes(engine.id)).map((engine) => <option key={engine.id} value={engine.id} disabled={!engine.runtime_available}>{engine.name}{engine.id === draft.execution.recommended_engine ? "（推荐）" : ""}{engine.runtime_available ? "" : " · 未就绪"}</option>)}</select><span className={`mt-1.5 block text-xs ${defaultEngine?.runtime_available ? "text-muted-foreground" : "text-critical"}`}>{defaultEngine?.runtime_available ? `${defaultEngine.name} 已就绪` : `${defaultEngine?.name ?? "所选 Agent"} 当前未就绪，请选择可用的 Agent`}</span></label>
        </div>

        <div className="rounded-xl border border-border p-4 sm:p-5">
          <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent"><FileCheck2 className="h-4 w-4" /></span><div className="min-w-0 flex-1"><span className="text-xs font-semibold text-muted-foreground">要完成什么</span><h3 className="mt-1 text-lg font-semibold">{draft.intent.title}</h3><p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{draft.intent.goal}</p></div></div>
          <div className="mt-4 rounded-lg bg-muted/45 px-4 py-3"><span className="text-xs font-semibold text-muted-foreground">怎样算完成</span><p className="mt-1 whitespace-pre-line text-sm leading-relaxed">{draft.intent.acceptance_criteria}</p></div>
        </div>

        <details className="rounded-xl border border-border">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 font-semibold [&::-webkit-details-marker]:hidden"><span className="flex items-center gap-2"><PencilLine className="h-4 w-4 text-accent" />修改目标与验收条件</span><ChevronDown className="h-4 w-4 text-muted-foreground" /></summary>
          <div className="grid gap-4 border-t border-border p-4 sm:p-5"><label><span className="field-label">任务名称</span><input value={draft.intent.title} maxLength={200} onChange={(event) => updateIntent("title", event.target.value)} className="input-base mt-2 w-full" /></label><label><span className="field-label">目标</span><textarea value={draft.intent.goal} maxLength={10000} rows={4} onChange={(event) => updateIntent("goal", event.target.value)} className="input-base mt-2 w-full resize-y" /></label><label><span className="field-label">验收条件</span><textarea value={draft.intent.acceptance_criteria} maxLength={20000} rows={4} onChange={(event) => updateIntent("acceptance_criteria", event.target.value)} className="input-base mt-2 w-full resize-y" /></label><label><span className="field-label">全队共享约束 <span className="font-normal text-muted-foreground">（可选）</span></span><textarea value={draft.intent.shared_context} maxLength={30000} rows={3} onChange={(event) => updateIntent("shared_context", event.target.value)} className="input-base mt-2 w-full resize-y" /></label></div>
        </details>

        <details className="rounded-xl border border-border">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 font-semibold [&::-webkit-details-marker]:hidden"><span className="flex items-center gap-2"><Settings2 className="h-4 w-4 text-accent" />查看或调整 Agent 角色与预算</span><span className="flex items-center gap-2 text-xs text-muted-foreground">{enabled.length} 个角色<ChevronDown className="h-4 w-4" /></span></summary>
          <div className="border-t border-border bg-muted/15 p-3 sm:p-4"><div className="mb-3 rounded-lg bg-white px-3 py-2 text-xs text-muted-foreground">总上限 {Math.round(total.tokens / 1000)}k Token · {total.calls} 次调用 · ${total.cost.toFixed(2)} · 高风险操作需确认</div><PresetRoleList preset={draft.team.preset} roles={roles} engines={draft.execution.engines} onChange={onRolesChange} /><div className="mt-3 text-right"><Link href="/containers/new" className="text-xs font-semibold text-accent hover:underline">打开完整 Agent Team 配置</Link></div></div>
        </details>

        <fieldset className={`rounded-xl border p-4 sm:p-5 ${access.folder_access === "full_access" ? "border-warning/35 bg-warning/[0.035]" : "border-success/25 bg-success/[0.025]"}`}>
          <legend className="px-1 text-sm font-semibold">文件与权限</legend>
          <div className="mt-1 grid gap-3 md:grid-cols-2">
            <label className={`flex cursor-pointer items-start gap-3 rounded-xl border bg-white p-4 ${access.folder_access === "isolated" ? "border-accent/40 ring-4 ring-accent/5" : "border-border"}`}><input type="radio" name="home-folder-access" checked={access.folder_access === "isolated"} onChange={() => { setFolderPickerError(null); changeAccess({ folder_access: "isolated", project_dir: "" }); }} className="mt-1 h-4 w-4" /><span><strong className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-success" />隔离工作区 · 上传副本（推荐）</strong><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">网页上传只复制项目快照，Agent 不会直接改动你的本地文件夹。</span></span></label>
            <label className={`flex items-start gap-3 rounded-xl border bg-white p-4 ${nativePickerAvailable ? "cursor-pointer" : "cursor-not-allowed opacity-60"} ${access.folder_access === "full_access" ? "border-warning/45 ring-4 ring-warning/10" : "border-border"}`}><input type="radio" name="home-folder-access" checked={access.folder_access === "full_access"} disabled={!nativePickerAvailable} onChange={() => { setFolderPickerError(null); changeAccess({ folder_access: "full_access", project_upload_id: null }); }} className="mt-1 h-4 w-4" /><span><strong className="flex items-center gap-2"><FolderOpen className="h-4 w-4 text-warning" />直接修改项目（macOS App）</strong><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{nativePickerAvailable ? "每个 Agent 使用独立 Git worktree，但会写入项目及 `.git`。" : "网页版不提供本地写入权限；请在 BudgetLoop macOS App 中使用。"}</span></span></label>
          </div>

          {access.folder_access === "isolated" ? <div className="mt-4 flex flex-col gap-3 rounded-lg border border-success/25 bg-white p-3 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><strong className="flex items-center gap-2 text-sm"><Upload className="h-4 w-4 text-success" />{projectUpload ? `已上传 ${projectUpload.folder_name ?? "项目文件夹"}` : "可上传项目文件夹"}</strong><p className="mt-1 text-xs text-muted-foreground">{projectUpload ? `${projectUpload.file_count} 个文件 · ${(projectUpload.total_bytes / 1024).toFixed(1)} KB；每个 Agent 获得独立副本。` : "普通浏览器只上传隔离副本，不会获得本地写入权限。"}</p></div><button type="button" onClick={onRequestBrowserUpload} className="btn btn-secondary shrink-0"><Upload className="h-4 w-4" />{projectUpload ? "重新上传" : "上传文件夹"}</button></div> : null}

          {access.folder_access === "full_access" ? (
            <div className="mt-4 space-y-3">
              <div role="alert" className="flex items-start gap-2 rounded-lg border border-warning/30 bg-white p-3 text-xs leading-relaxed text-warning"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /><span><strong>完全访问模式</strong>：只授权你选择的项目文件夹，但 Agent 可以直接修改其中所有内容，包括 Git 分支与元数据。</span></div>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]"><label><span className="field-label">项目文件夹</span><span className="relative mt-2 block"><Folder className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input id="home-project-dir" value={access.project_dir} readOnly aria-readonly="true" placeholder="尚未选择项目文件夹" className="input-base w-full cursor-default bg-muted/30 pl-10 font-mono text-xs" /></span></label><button type="button" onClick={requestFolder} className="btn btn-secondary self-end"><FolderOpen className="h-4 w-4" />选择文件夹</button></div>
              {folderPickerError ? <p role="alert" className="field-error">{folderPickerError}</p> : null}
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-warning/25 bg-white p-3"><input type="checkbox" checked={access.full_access_acknowledged} onChange={(event) => onAccessChange({ ...access, full_access_acknowledged: event.target.checked })} className="mt-0.5 h-4 w-4" /><span className="text-xs leading-relaxed"><strong>我确认：</strong>这些 Agent 可以直接修改 <span className="font-mono">{access.project_dir || "所选文件夹"}</span>，包括其中的 `.git`。</span></label>
            </div>
          ) : null}
        </fieldset>

        {confirmationError ? <div role="alert" className="flex items-start gap-2 rounded-lg border border-critical/20 bg-critical/5 p-3 text-sm text-critical"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{confirmationError}</div> : null}
        {validationError ? <p role="status" className="text-sm text-warning">还差一步：{validationError}</p> : null}

        <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl text-xs leading-relaxed text-muted-foreground"><ShieldCheck className="mr-1 inline h-3.5 w-3.5 text-success" />确认后才会创建并启动 {enabled.length} 个 Agent；硬预算和人工审批始终由 BudgetLoop 控制。</p>
          <button type="button" onClick={onConfirm} disabled={Boolean(validationError) || confirming} className="btn btn-primary min-h-12 shrink-0 px-6">{confirming ? <BudgetLoopActivityMark compact label="正在创建…" /> : <>确认并启动<ArrowRight className="h-4 w-4" /></>}</button>
        </div>
        <DraftProvenance draft={draft} />
      </div>
    </section>
  );
}

export function HomeTaskIntake() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<TaskSetupDraft | null>(null);
  const [roles, setRoles] = useState<TeamRoleDraft[]>([]);
  const [access, setAccess] = useState<WorkspaceAccessSelection>({ ...DEFAULT_WORKSPACE_ACCESS });
  const [state, setState] = useState<PlanningState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmationError, setConfirmationError] = useState<string | null>(null);
  const [composerFolderPickerError, setComposerFolderPickerError] = useState<string | null>(null);
  const [projectUpload, setProjectUpload] = useState<ProjectUploadSummary | null>(null);
  const [projectUploading, setProjectUploading] = useState(false);
  const [nativePickerAvailable, setNativePickerAvailable] = useState(false);
  const requestSequence = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const creationKey = useRef<string | null>(null);
  const explicitEngine = useRef<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const reviewRef = useRef<HTMLElement>(null);
  const browserFolderInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  useEffect(() => {
    setNativePickerAvailable(Boolean(window.webkit?.messageHandlers?.budgetloopPickProjectDir));
  }, []);

  useEffect(() => {
    if (state === "ready" || state === "needs_input") {
      reviewRef.current?.focus();
    }
  }, [state]);

  useEffect(() => {
    window.budgetloopSetProjectDir = (path: string) => {
      setComposerFolderPickerError(null);
      setProjectUpload(null);
      setAccess({
        folder_access: "full_access",
        project_dir: path,
        full_access_acknowledged: false,
        project_upload_id: null,
      });
    };
    return () => { delete window.budgetloopSetProjectDir; };
  }, []);

  useEffect(() => {
    if (access.folder_access === "isolated" && !access.project_upload_id) {
      setProjectUpload(null);
    }
  }, [access.folder_access, access.project_upload_id]);

  function requestComposerFolder() {
    const bridge = window.webkit?.messageHandlers?.budgetloopPickProjectDir;
    if (bridge) {
      setComposerFolderPickerError(null);
      bridge.postMessage(null);
    } else {
      setComposerFolderPickerError(null);
      browserFolderInputRef.current?.click();
    }
  }

  async function handleBrowserFolder(files: FileList | null) {
    if (!files?.length) return;
    setProjectUploading(true);
    setComposerFolderPickerError(null);
    try {
      const selected = Array.from(files);
      const summary = await uploadProjectFolder<ProjectUploadSummary>(selected);
      const firstPath = selected[0]?.webkitRelativePath;
      setProjectUpload({
        ...summary,
        folder_name: firstPath?.split("/")[0] || "项目文件夹",
      });
      setAccess({
        folder_access: "isolated",
        project_dir: "",
        full_access_acknowledged: false,
        project_upload_id: summary.upload_id,
      });
    } catch (reason) {
      setComposerFolderPickerError(
        reason instanceof Error ? `文件夹上传失败：${reason.message}` : "文件夹上传失败，请重试。",
      );
    } finally {
      setProjectUploading(false);
      if (browserFolderInputRef.current) browserFolderInputRef.current.value = "";
    }
  }

  async function plan(event?: FormEvent) {
    event?.preventDefault();
    const normalized = message.trim();
    if (normalized.length < 3) {
      setError("请用一句话描述你想完成的结果。");
      setState("error");
      composerRef.current?.focus();
      return;
    }
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const sequence = ++requestSequence.current;
    setState("planning");
    setError(null);
    setConfirmationError(null);
    const body: CreateTaskDraftRequest = {
      message: normalized,
      previous_draft: draft ? editableTaskDraft(draft) : null,
    };
    try {
      const next = await apiFetch<TaskSetupDraft>("/api/task-drafts", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(body),
      });
      if (controller.signal.aborted || sequence !== requestSequence.current) return;
      const selectedEngine = explicitEngine.current ?? next.execution.default_engine;
      const selectedFact = next.execution.engines.find((engine) => engine.id === selectedEngine);
      const selectedDraft = { ...next, execution: { ...next.execution, default_engine: selectedEngine, ready: Boolean(selectedFact?.runtime_available) } };
      setDraft(selectedDraft);
      setRoles(rolesForTaskDraft(selectedDraft));
      setState(next.state);
      setMessage("");
      creationKey.current = null;
    } catch (reason) {
      if (controller.signal.aborted || sequence !== requestSequence.current) return;
      setError(reason instanceof Error ? reason.message : "暂时无法生成配置，请重试。");
      setState("error");
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && state !== "planning" && message.trim().length >= 3) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function selectEngine(engineId: string) {
    if (!draft) return;
    const engine = draft.execution.engines.find((item) => item.id === engineId);
    if (!engine?.runtime_available) return;
    explicitEngine.current = engineId;
    setDraft({ ...draft, execution: { ...draft.execution, default_engine: engineId, ready: true } });
    setRoles((current) => current.map((role) => ({ ...role, execution_engine: engineId })));
  }

  async function confirm() {
    if (!draft || teamDraftError(draft, roles, access)) return;
    setConfirming(true);
    setConfirmationError(null);
    creationKey.current ??= idempotencyKey();
    try {
      const result = await apiFetch<CreateTeamFromPresetResponse>(
        "/api/work-containers/from-preset",
        {
          method: "POST",
          headers: { "Idempotency-Key": creationKey.current },
          body: JSON.stringify(createTeamRequestFromDraft(draft, roles, access)),
        },
      );
      router.push(`/containers/${result.container.id}`);
    } catch (reason) {
      setConfirmationError(reason instanceof Error ? reason.message : "团队创建失败，请重试。");
      if (reason instanceof ApiError && reason.status !== null && reason.status < 500) {
        creationKey.current = null;
      }
      setConfirming(false);
    }
  }

  const selectedProjectName = access.project_dir
    ? access.project_dir.split("/").filter(Boolean).at(-1) ?? access.project_dir
    : projectUpload?.folder_name ?? null;
  return (
    <div className="space-y-5">
      <section className="relative overflow-hidden rounded-2xl border border-accent/15 bg-white px-5 py-7 shadow-surface sm:px-8 sm:py-9">
        <div aria-hidden className="absolute -right-20 -top-28 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
        <div className="relative mx-auto max-w-4xl text-center">
          <h1 className="text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">你想完成什么？</h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">描述目标，BudgetLoop 会推荐团队、拆解任务并生成验收条件。</p>

          <form onSubmit={(event) => void plan(event)} className="mx-auto mt-6 max-w-3xl text-left">
            <div className="rounded-2xl border border-border-strong bg-white p-2 shadow-elevated transition focus-within:border-accent/45 focus-within:ring-4 focus-within:ring-accent/10">
              <label htmlFor="home-goal" className="sr-only">描述想完成的目标</label>
              <textarea ref={composerRef} id="home-goal" value={message} maxLength={10000} rows={4} onChange={(event) => { setMessage(event.target.value); setError(null); }} onKeyDown={handleComposerKeyDown} placeholder={draft ? "继续补充约束，例如：还要覆盖移动端和无障碍…" : "例如：修复订单接口并发超扣，并补充能防止复发的测试…"} className="min-h-28 w-full resize-y rounded-xl border-0 bg-transparent px-3 py-3 text-base leading-relaxed outline-none placeholder:text-muted-foreground/65" />
              <div className="border-t border-border px-2 pt-2">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
                    <input ref={browserFolderInputRef} data-testid="browser-folder-input" type="file" multiple hidden aria-hidden="true" tabIndex={-1} {...({ webkitdirectory: "", directory: "" } as Record<string, string>)} onChange={(event) => void handleBrowserFolder(event.currentTarget.files)} />
                    <button type="button" onClick={requestComposerFolder} disabled={projectUploading} aria-label={access.project_dir ? `更换项目文件夹，当前 ${access.project_dir}` : projectUpload ? `重新上传项目文件夹，当前 ${projectUpload.folder_name}` : nativePickerAvailable ? "选择项目文件夹" : "上传项目文件夹"} aria-describedby={composerFolderPickerError ? "home-composer-folder-error" : undefined} title={access.project_dir || "macOS App 直接选择；普通浏览器上传隔离副本"} className="btn btn-secondary min-h-10 min-w-0 shrink-0 px-3">{projectUploading ? <BudgetLoopActivityMark compact label="正在上传" /> : <><FolderOpen className="h-4 w-4" /><span className="max-w-52 truncate">{selectedProjectName ?? (nativePickerAvailable ? "选择项目文件夹" : "上传项目文件夹")}</span></>}</button>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between lg:justify-end">
                    <span className="hidden text-[11px] text-muted-foreground sm:inline">Enter 发送 · Shift Enter 换行</span>
                    <button type="submit" disabled={message.trim().length < 3} className="btn btn-primary min-h-11 px-5">{state === "planning" ? <BudgetLoopActivityMark compact label={draft ? "正在更新建议配置" : "正在生成建议配置"} /> : <><Send className="h-4 w-4" />{draft ? "更新建议配置" : "生成建议配置"}</>}</button>
                  </div>
                </div>
                {composerFolderPickerError ? <p id="home-composer-folder-error" role="alert" className="field-error pb-1">{composerFolderPickerError}</p> : null}
              </div>
            </div>
          </form>

          {!draft ? <div className="mt-4 flex flex-wrap justify-center gap-2" aria-label="示例目标">{EXAMPLES.map((example) => <button key={example} type="button" onClick={() => { setMessage(example); composerRef.current?.focus(); }} className="rounded-full border border-border bg-white px-3 py-1.5 text-xs text-muted-foreground shadow-control hover:border-accent/30 hover:text-accent">{example}</button>)}</div> : null}
          <div className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-2 text-xs"><Link href="/new" className="font-semibold text-muted-foreground hover:text-accent">手动配置单个任务</Link><Link href="/containers/new" className="font-semibold text-muted-foreground hover:text-accent">浏览全部 Agent Team</Link></div>
        </div>
      </section>

      <div aria-live="polite" aria-atomic="true" className="sr-only">{state === "planning" ? "正在分析目标并组建 Agent 队伍" : state === "ready" ? "建议配置已就绪" : state === "needs_input" ? "需要补充信息" : state === "error" ? `生成失败：${error}` : ""}</div>
      {error ? <div role="alert" className="flex items-start justify-between gap-4 rounded-xl border border-critical/20 bg-critical/5 p-4 text-sm text-critical"><span className="flex items-start gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</span><button type="button" onClick={() => void plan()} className="shrink-0 font-semibold underline">重试</button></div> : null}
      {draft?.clarifications.length ? <section className="surface p-5"><h2 className="font-semibold">还需要你补充</h2><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{draft.clarifications.slice(0, 2).map((question) => <li key={question}>{question}</li>)}</ul></section> : null}
      {state === "planning" && !draft ? <div className="surface flex min-h-44 flex-col items-center justify-center gap-3 p-6 text-center"><BudgetLoopActivityMark label="正在分析目标" /><p className="text-sm text-muted-foreground">正在理解目标并选择合适的 Agent 团队…</p></div> : null}
      {draft ? <TaskSetupReview focusRef={reviewRef} draft={draft} roles={roles} access={access} confirming={confirming} confirmationError={confirmationError} onDraftChange={setDraft} onRolesChange={setRoles} onEngineChange={selectEngine} onAccessChange={setAccess} onConfirm={() => void confirm()} projectUpload={projectUpload} onRequestBrowserUpload={() => browserFolderInputRef.current?.click()} nativePickerAvailable={nativePickerAvailable} /> : null}
    </div>
  );
}
