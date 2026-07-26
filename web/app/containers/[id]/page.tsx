"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, GitFork, Play, Plus, RefreshCw, Server, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CreateSessionDialog } from "@/components/containers/CreateSessionDialog";
import { HandoffComposer } from "@/components/containers/HandoffComposer";
import { SessionInspector } from "@/components/containers/SessionInspector";
import { SessionRail } from "@/components/containers/SessionRail";
import { SessionTranscript } from "@/components/containers/SessionTranscript";
import { apiFetch, idempotencyKey } from "@/lib/api";
import {
  CONTAINER_LIFECYCLE_LABELS,
  lifecycleTone,
  SESSION_STATUS_LABELS,
  sessionTone,
} from "@/lib/container-presentation";
import type {
  CreateWorkSessionRequest,
  MessageKind,
  TeamDispatchResult,
  WorkContainer,
  WorkSessionDetailResponse,
  WorkSessionSummary,
} from "@/lib/types";

type MobileTab = "sessions" | "conversation" | "context";

function LoadingWorkspace() {
  return <div className="page-shell space-y-6" aria-busy="true"><div className="skeleton h-5 w-56" /><div className="space-y-3"><div className="skeleton h-9 w-96 max-w-full" /><div className="skeleton h-5 w-[32rem] max-w-full" /></div><div className="skeleton h-[680px] rounded-xl" /></div>;
}

export default function ContainerWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const [container, setContainer] = useState<WorkContainer | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkSessionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>("conversation");

  const loadContainer = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const data = await apiFetch<WorkContainer>(`/api/work-containers/${id}`);
      setContainer(data);
      setSelectedId((current) => current && data.sessions.some((item) => item.id === current) ? current : data.sessions[0]?.id ?? null);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载工作容器。");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [id]);

  const loadDetail = useCallback(async (sessionId: string, quiet = false) => {
    if (!quiet) setDetail(null);
    try {
      const data = await apiFetch<WorkSessionDetailResponse>(`/api/work-containers/${id}/sessions/${sessionId}`);
      setDetail(data);
      setActionError(null);
    } catch (loadError) {
      setActionError(loadError instanceof Error ? loadError.message : "无法加载 Session。 ");
    }
  }, [id]);

  useEffect(() => { void loadContainer(); }, [loadContainer]);
  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    void loadDetail(selectedId);
    const timer = window.setInterval(() => {
      void Promise.all([loadContainer(true), loadDetail(selectedId, true)]);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [loadContainer, loadDetail, selectedId]);
  useEffect(() => {
    const open = () => setDialogOpen(true);
    window.addEventListener("budgetloop:new-session", open);
    return () => window.removeEventListener("budgetloop:new-session", open);
  }, []);

  const selectedSummary = useMemo(
    () => container?.sessions.find((item) => item.id === selectedId) ?? null,
    [container, selectedId],
  );

  const stagedRunCount = useMemo(() => {
    if (!container?.preset_snapshot) return 0;
    const dispatched = new Set(container.preset_snapshot.dispatch?.dispatched_run_ids ?? []);
    return container.sessions.filter((item) => item.status === "PENDING" && !dispatched.has(item.current_run_id)).length;
  }, [container]);

  async function createSession(body: CreateWorkSessionRequest) {
    setBusy(true);
    setActionError(null);
    try {
      const response = await apiFetch<{ session: WorkSessionSummary }>(`/api/work-containers/${id}/sessions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify(body),
      });
      await loadContainer(true);
      setSelectedId(response.session.id);
      setDialogOpen(false);
      setMobileTab("conversation");
    } catch (createError) {
      setActionError(createError instanceof Error ? createError.message : "Session 创建失败。");
    } finally {
      setBusy(false);
    }
  }

  async function send(kind: MessageKind, content: string, recipientId: string) {
    if (!selectedSummary) return;
    setBusy(true);
    setActionError(null);
    try {
      await apiFetch(`/api/work-containers/${id}/sessions/${recipientId}/messages`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          sender_session_id: kind === "handoff" ? selectedSummary.id : null,
          kind,
          content,
        }),
      });
      await Promise.all([loadContainer(true), loadDetail(selectedSummary.id, true)]);
    } catch (sendError) {
      setActionError(sendError instanceof Error ? sendError.message : "消息发送失败。");
    } finally {
      setBusy(false);
    }
  }

  async function pauseSession() {
    if (!selectedId) return;
    setBusy(true);
    try {
      await apiFetch(`/api/work-containers/${id}/sessions/${selectedId}/pause`, { method: "POST" });
      await Promise.all([loadContainer(true), loadDetail(selectedId, true)]);
    } catch (pauseError) {
      setActionError(pauseError instanceof Error ? pauseError.message : "暂停失败。");
    } finally {
      setBusy(false);
    }
  }

  async function saveContext(value: string) {
    setBusy(true);
    try {
      const updated = await apiFetch<WorkContainer>(`/api/work-containers/${id}`, { method: "PATCH", body: JSON.stringify({ shared_context: value }) });
      setContainer(updated);
    } catch (saveError) {
      setActionError(saveError instanceof Error ? saveError.message : "共享上下文保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function startTeam() {
    setBusy(true);
    setActionError(null);
    try {
      const result = await apiFetch<TeamDispatchResult>(`/api/work-containers/${id}/start`, { method: "POST" });
      if (result.warnings.length) setActionError(`有 ${result.warnings.length} 个 Session 尚未启动：${result.warnings[0].message}`);
      await loadContainer(true);
    } catch (startError) {
      setActionError(startError instanceof Error ? startError.message : "团队启动失败。");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingWorkspace />;
  if (error || !container) return <div className="page-shell"><section role="alert" className="surface flex flex-col items-center px-6 py-16 text-center"><AlertCircle className="h-9 w-9 text-critical" /><h1 className="mt-4 text-xl font-semibold">工作容器无法打开</h1><p className="mt-2 max-w-lg text-sm text-muted-foreground">{error ?? "容器不存在。"}</p><div className="mt-6 flex gap-3"><Link href="/containers" className="btn btn-secondary"><ArrowLeft className="h-4 w-4" />Agent Team</Link><button onClick={() => void loadContainer()} className="btn btn-primary"><RefreshCw className="h-4 w-4" />重试</button></div></section></div>;

  return (
    <div className="mx-auto w-full max-w-[1536px] animate-in px-0 py-5 sm:px-6 sm:py-7">
      <div className="px-4 sm:px-0">
        <Link href="/containers" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Agent Team</Link>
        <header className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div><div className="flex flex-wrap items-center gap-3"><h1 className="page-heading">{container.name}</h1><span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset ${lifecycleTone(container.lifecycle_state)}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{CONTAINER_LIFECYCLE_LABELS[container.lifecycle_state]}</span></div><p className="page-subtitle max-w-3xl">{container.project_goal}</p></div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground"><span className="flex items-center gap-2"><UsersRound className="h-4 w-4" />{container.counts.sessions} 个 Session</span><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-success" />{container.counts.running} 运行中</span><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-critical" />{container.counts.attention} 需关注</span></div>
        </header>
      </div>

      {actionError ? <div role="alert" className="mx-4 mt-5 flex items-start justify-between gap-3 rounded-lg border border-critical/20 bg-critical/5 px-4 py-3 text-sm text-critical sm:mx-0"><span>{actionError}</span><button onClick={() => setActionError(null)} className="font-semibold">关闭</button></div> : null}

      {container.preset_snapshot ? <section className="mx-4 mt-5 rounded-xl border border-accent/15 bg-gradient-to-r from-accent/[0.055] to-white p-4 sm:mx-0 sm:p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="badge badge-info">{container.preset_snapshot.preset.name} · v{container.preset_version}</span><span className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground"><Server className="h-3.5 w-3.5" />{Array.from(new Set(container.preset_snapshot.applied_roles.map((role) => role.execution_engine))).join(" · ")}</span><span className="text-xs text-muted-foreground">{container.preset_snapshot.team_mode === "autonomous" ? "智能自主协作" : "LangGraph 激活图"}</span>{container.preset_snapshot.budget_mode === "max" ? <span className="badge border-warning/30 bg-warning/10 text-warning">Max · 无上限</span> : null}</div><p className="mt-2 text-xs leading-relaxed text-muted-foreground">{container.preset_snapshot.team_mode === "autonomous" ? "同阶段角色会并行工作；只有前置阶段成功完成，公开输出才会自动 Handoff 到下一阶段。" : "团队来源、实际角色、预算、执行引擎与 Handoff 阶段已固化到创建快照；引擎不会接管 BudgetLoop 的状态和审批。"}</p><div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">{container.preset_snapshot.preset.sources.map((source) => <a key={source.repository} href={source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent hover:underline"><GitFork className="h-3 w-3" />{source.repository}</a>)}</div></div>{stagedRunCount > 0 ? <button type="button" onClick={() => void startTeam()} disabled={busy} className="btn btn-primary shrink-0"><Play className="h-4 w-4" />{busy ? "正在启动…" : `启动团队 · ${stagedRunCount} 个 Session`}</button> : <span className="badge badge-success shrink-0">团队已提交运行</span>}</div></section> : null}

      <div className="mx-4 mt-6 flex rounded-lg border border-border bg-white p-1 xl:hidden" role="tablist" aria-label="工作区区域">{[
        { key: "sessions" as const, label: "Session" },
        { key: "conversation" as const, label: "对话" },
        { key: "context" as const, label: "上下文" },
      ].map((tab) => <button key={tab.key} id={`workspace-tab-${tab.key}`} role="tab" aria-controls={`workspace-panel-${tab.key}`} aria-selected={mobileTab === tab.key} onClick={() => setMobileTab(tab.key)} className={`min-h-9 flex-1 rounded-md text-sm font-semibold ${mobileTab === tab.key ? "bg-muted text-accent" : "text-muted-foreground"}`}>{tab.label}</button>)}</div>

      {container.sessions.length === 0 ? <section className="mx-4 mt-6 flex min-h-[520px] flex-col items-center justify-center rounded-xl border border-border bg-white/85 px-6 text-center sm:mx-0"><div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent"><UsersRound className="h-7 w-7" /></div><h2 className="mt-5 text-xl font-semibold">为团队添加第一个 Session</h2><p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">每个 Session 都有独立目标、私有上下文、对话、运行状态与硬预算。只有共享上下文和明确 Handoff 会跨越边界。</p><button onClick={() => setDialogOpen(true)} className="btn btn-primary mt-6"><Plus className="h-4 w-4" />新建 Session</button></section> : (
        <section className="mx-0 mt-4 min-h-[680px] overflow-hidden border-y border-border bg-white/85 shadow-surface sm:mx-0 sm:mt-6 sm:rounded-xl sm:border xl:grid xl:h-[calc(100dvh-250px)] xl:max-h-[calc(100dvh-250px)] xl:grid-cols-[280px_minmax(480px,1fr)_320px]" aria-label="多 Session 协作工作区">
          <div id="workspace-panel-sessions" role="tabpanel" aria-labelledby="workspace-tab-sessions" className={`${mobileTab === "sessions" ? "flex min-h-[620px]" : "hidden"} xl:flex`}><SessionRail sessions={container.sessions} selectedId={selectedId} onSelect={(sessionId) => { setSelectedId(sessionId); setMobileTab("conversation"); }} onAdd={() => setDialogOpen(true)} /></div>
          <section id="workspace-panel-conversation" role="tabpanel" aria-labelledby="workspace-tab-conversation" className={`${mobileTab === "conversation" ? "flex min-h-[620px]" : "hidden"} min-w-0 flex-col xl:flex xl:h-full xl:min-h-0 xl:overflow-hidden`}>
            {selectedSummary ? <><header className="border-b border-border px-5 py-4 sm:px-6"><div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold tracking-tight">{selectedSummary.role}</h2><p className="mt-1 text-xs leading-relaxed text-muted-foreground">私有目标：{selectedSummary.goal}</p></div><span className="flex shrink-0 items-center gap-1.5 text-xs font-semibold text-muted-foreground"><span className={`h-1.5 w-1.5 rounded-full ${sessionTone(selectedSummary.status)}`} />{SESSION_STATUS_LABELS[selectedSummary.status] ?? selectedSummary.status}</span></div><p className="mt-3 font-mono text-[11px] text-muted-foreground">第 {selectedSummary.iteration} 轮 · {selectedSummary.status}{detail?.session.budget ? detail.session.budget.unlimited ? " · Max" : ` · 预算 ${Math.round((detail.session.budget.used_tokens / detail.session.budget.max_total_tokens) * 100)}%` : ""}</p></header><div className="min-h-0 flex-1 overflow-y-auto">{detail ? <SessionTranscript entries={detail.transcript} /> : <div className="p-6"><div className="skeleton h-20" /><div className="skeleton mt-4 h-28" /></div>}</div><HandoffComposer selected={selectedSummary} sessions={container.sessions} busy={busy} onSend={send} /></> : null}
          </section>
          <div id="workspace-panel-context" role="tabpanel" aria-labelledby="workspace-tab-context" className={`${mobileTab === "context" ? "block min-h-[620px]" : "hidden"} xl:block xl:min-h-0`}>{detail ? <SessionInspector container={container} session={detail.session} transcript={detail.transcript} busy={busy} onPause={pauseSession} onSaveContext={saveContext} /> : <div className="p-5"><div className="skeleton h-36" /><div className="skeleton mt-4 h-52" /></div>}</div>
        </section>
      )}

      <CreateSessionDialog open={dialogOpen} defaultWorktree={container.default_workspace_policy === "worktree"} busy={busy} error={actionError} onClose={() => { if (!busy) setDialogOpen(false); }} onCreate={createSession} />
    </div>
  );
}
