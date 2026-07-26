"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertCircle, ArrowLeft, ArrowRight, CircleStop, Clock3, Pause, RefreshCw, ShieldAlert, Wifi, WifiOff } from "lucide-react";
import ApprovalModal from "@/components/ApprovalModal";
import BudgetView from "@/components/BudgetView";
import LlmCallsTable from "@/components/LlmCallsTable";
import Timeline from "@/components/Timeline";
import TokenObservatory from "@/components/TokenObservatory";
import { apiFetch } from "@/lib/api";
import { approvalIdOf, fetchEvents } from "@/lib/events";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/format";
import { statusClass, STATUS_LABELS, TERMINAL_STATUS } from "@/lib/presentation";
import { budgetUsageRatio, folderAccessMode, pressureExplanation, runPhaseLabel } from "@/lib/run-presentation";
import { ProgressBar, Tabs } from "@/components/ui";
import type { ApprovalAction, ApprovalPayload, BudgetDetail, ExecutionEvent, LlmCall, RunDetail } from "@/lib/types";

type Tab = "observatory" | "timeline" | "calls" | "budget" | "info";
const PHASE_LABELS: Record<string, string> = { scan: "扫描代码库", analyze: "分析问题", modify: "修改代码", verify: "执行验证", repair: "修复回归", summarize: "总结交付" };
const PRESSURE_LABELS: Record<string, string> = { NORMAL: "正常模式", CONSERVATIVE: "保守模式", CRITICAL: "紧急模式" };

function BudgetMetric({ label, used, total, reserved }: { label: string; used: string; total: string; reserved?: string }) {
  return <div className="min-w-0"><p className="text-xs font-semibold text-muted-foreground">{label}</p><p className="mt-1 font-mono text-lg font-semibold tabular-nums">{used} <span className="text-sm font-normal text-muted-foreground">/ {total}</span></p>{reserved ? <p className="mt-1 text-xs text-muted-foreground">已预留 {reserved}</p> : null}</div>;
}

export default function RunDetailPage() {
  const runId = useParams<{ id: string }>().id;
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [calls, setCalls] = useState<LlmCall[]>([]);
  const [budgetDetail, setBudgetDetail] = useState<BudgetDetail | null>(null);
  const [tab, setTab] = useState<Tab>("observatory");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [approvalPayload, setApprovalPayload] = useState<ApprovalPayload | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const lastSeq = useRef(0);
  const dismissedApprovalId = useRef<string | null>(null);
  const resolvedApprovalIds = useRef(new Set<string>());

  const load = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    const [runResult, callsResult, budgetResult, eventsResult] = await Promise.allSettled([
      apiFetch<RunDetail>(`/api/runs/${runId}`), apiFetch<LlmCall[] | { llm_calls: LlmCall[] }>(`/api/runs/${runId}/llm-calls`),
      apiFetch<BudgetDetail>(`/api/runs/${runId}/budget`), fetchEvents(runId, lastSeq.current),
    ]);
    if (runResult.status === "fulfilled") { setDetail(runResult.value); setError(null); setConnected(true); }
    else { setConnected(false); setError(runResult.reason instanceof Error ? runResult.reason.message : "运行详情加载失败。"); }
    if (callsResult.status === "fulfilled") { const v = callsResult.value; setCalls(Array.isArray(v) ? v : v.llm_calls ?? []); }
    if (budgetResult.status === "fulfilled") setBudgetDetail(budgetResult.value);
    if (eventsResult.status === "fulfilled" && eventsResult.value.events.length > 0) {
      const incoming = eventsResult.value.events as ExecutionEvent[];
      lastSeq.current = Math.max(lastSeq.current, ...incoming.map((event) => event.seq));
      setEvents((current) => { const seen = new Set(current.map((event) => event.seq)); return [...current, ...incoming.filter((event) => !seen.has(event.seq))].sort((a, b) => a.seq - b.seq); });
      for (const event of [...incoming].reverse()) {
        if (event.type === "approval_requested") { const id = approvalIdOf(event.payload); if (id && !resolvedApprovalIds.current.has(id)) { setApprovalId(id); setApprovalPayload(event.payload as ApprovalPayload); if (dismissedApprovalId.current !== id) setApprovalOpen(true); } break; }
      }
    }
    if (initial) setLoading(false);
  }, [runId]);

  useEffect(() => { void load(true); const timer = window.setInterval(() => void load(false), 3000); return () => window.clearInterval(timer); }, [load]);

  const run = detail?.run;
  const task = detail?.task;
  const budget = budgetDetail?.budget ?? detail?.budget;
  const terminal = run ? TERMINAL_STATUS.has(run.status) : false;
  const tokenRatio = budget ? budgetUsageRatio(budget.used_tokens, budget.reserved_tokens, budget.max_total_tokens) : 0;
  const pressure = run?.pressure_mode ?? "NORMAL";
  const latestEvent = events.length > 0 ? events[events.length - 1] : undefined;
  const currentActivity = useMemo(() => {
    if (terminal) return "本次运行已经结束。请查看执行结果与后续建议。";
    if (latestEvent?.type === "agent_message" && typeof latestEvent.payload.text === "string") return latestEvent.payload.text.slice(0, 180);
    return run?.current_phase ? `Agent 正在${PHASE_LABELS[run.current_phase] ?? run.current_phase}，新的事件会在这里实时更新。` : "Agent 正在准备下一步执行计划。";
  }, [latestEvent, run?.current_phase, terminal]);

  const folderAccess = folderAccessMode(run?.model_config?.folder_access);
  const infoItems: [string, ReactNode][] = [
    ["任务名称", task?.name],
    ["工作目录", task?.workdir],
    ["验收条件", task?.acceptance_criteria ?? "未显式设置"],
    ["策略", run?.strategy],
    ["运行状态", STATUS_LABELS[run?.status ?? ""]],
    ["开始时间", run?.started_at ? new Date(run.started_at).toLocaleString() : "尚未开始"],
    ["权限模式", <span key="folder-access" className={`badge ${folderAccess.badgeClass}`}>{folderAccess.label}</span>],
    ["项目文件夹", run?.model_config?.project_dir?.trim() || null],
  ];

  const runAction = async (action: "pause" | "cancel") => { setActionBusy(true); setError(null); try { await apiFetch(`/api/runs/${runId}/${action}`, { method: "POST" }); await load(false); } catch (err) { setError(err instanceof Error ? err.message : "操作失败，请重试。"); } finally { setActionBusy(false); } };
  const decideApproval = async (action: ApprovalAction, note: string) => { if (!approvalId) return; await apiFetch(`/api/approvals/${approvalId}/decide`, { method: "POST", body: JSON.stringify({ action, note }) }); resolvedApprovalIds.current.add(approvalId); dismissedApprovalId.current = approvalId; setApprovalId(null); setApprovalPayload(null); setApprovalOpen(false); await load(false); };

  if (loading) return <div className="page-shell space-y-6" aria-busy="true"><div className="skeleton h-12 w-2/3" /><div className="grid gap-4 lg:grid-cols-2"><div className="skeleton h-52" /><div className="skeleton h-52" /></div><div className="skeleton h-96" /></div>;

  if (!detail) return <div className="page-shell"><section role="alert" className="surface mx-auto mt-20 max-w-xl p-7 text-center"><AlertCircle className="mx-auto h-8 w-8 text-critical" /><h1 className="mt-4 text-xl font-semibold">无法打开运行指挥台</h1><p className="mt-2 text-sm text-muted-foreground">{error ?? "运行数据暂不可用。"}</p><div className="mt-5 flex justify-center gap-3"><button onClick={() => void load(true)} className="btn btn-primary"><RefreshCw className="h-4 w-4" />重试</button><Link href="/" className="btn btn-secondary">返回工作台</Link></div></section></div>;

  return (
    <div className="page-shell animate-in space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted-foreground">{run?.work_container_id ? <Link href={`/containers/${run.work_container_id}`} className="inline-flex items-center gap-1 hover:text-accent"><ArrowLeft className="h-3.5 w-3.5" />Agent Team · {run.work_session_role}</Link> : <Link href="/" className="inline-flex items-center gap-1 hover:text-accent"><ArrowLeft className="h-3.5 w-3.5" />任务工作台</Link>}<span>/</span><span>运行指挥台</span></div>
      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-3"><h1 className="page-heading truncate">{task?.name ?? "运行指挥台"}</h1><span className={`badge ${statusClass(run?.status)}`}><span className={`h-1.5 w-1.5 rounded-full bg-current ${!terminal ? "animate-pulse-subtle" : ""}`} />{STATUS_LABELS[run?.status ?? "PENDING"]}</span></div><p className="mt-2 break-all font-mono text-xs text-muted-foreground">{runId}</p></div><div className="flex flex-wrap gap-2">{terminal ? <Link href={`/runs/${runId}/report`} className="btn btn-primary">查看执行结果<ArrowRight className="h-4 w-4" /></Link> : <><button onClick={() => void runAction("pause")} disabled={actionBusy} className="btn btn-secondary"><Pause className="h-4 w-4" />{run?.status === "PAUSED" ? "继续" : "暂停"}</button><button onClick={() => void runAction("cancel")} disabled={actionBusy} className="btn btn-destructive"><CircleStop className="h-4 w-4" />取消运行</button></>}</div></header>

      {error ? <div role="alert" className="rounded-lg border border-critical/20 bg-critical/5 p-3 text-sm text-critical">{error}</div> : null}

      <section className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <div className="surface p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="section-title">当前活动</h2><div className={`inline-flex items-center gap-2 text-xs font-semibold ${connected ? "text-success" : "text-critical"}`}>{connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}{connected ? "实时更新" : "连接中断"}</div></div><p className="mt-3 min-h-12 text-sm leading-relaxed text-muted-foreground">{currentActivity}</p><div className="mt-5 grid grid-cols-3 divide-x divide-border border-t border-border pt-4 text-center"><div><p className="text-xs text-muted-foreground">当前阶段</p><p className="mt-1 font-semibold">{runPhaseLabel(run?.current_phase, terminal, PHASE_LABELS)}</p></div><div><p className="text-xs text-muted-foreground">压力模式</p><p className={`mt-1 font-semibold ${pressure === "CRITICAL" ? "text-critical" : pressure === "CONSERVATIVE" ? "text-warning" : "text-success"}`}>{PRESSURE_LABELS[pressure]}</p></div><div><p className="text-xs text-muted-foreground">轮次</p><p className="mt-1 font-mono font-semibold">第 {run?.iteration ?? 0} 轮</p></div></div></div>

        <div className="surface p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="section-title">预算健康</h2><span className={`badge ${pressure === "CRITICAL" ? "badge-critical" : pressure === "CONSERVATIVE" ? "badge-warning" : "badge-success"}`}>{PRESSURE_LABELS[pressure]}</span></div>{budget ? <><div className="mt-4"><ProgressBar ratio={tokenRatio} color={pressure === "CRITICAL" ? "bg-critical" : pressure === "CONSERVATIVE" ? "bg-warning" : "bg-accent"} /></div><div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4"><BudgetMetric label="Tokens" used={formatTokens(budget.used_tokens)} total={formatTokens(budget.max_total_tokens)} reserved={formatTokens(budget.reserved_tokens)} /><BudgetMetric label="执行时间" used={formatDurationMs(run?.active_runtime_ms ?? 0)} total={`${budget.max_active_runtime_seconds}s`} /><BudgetMetric label="调用次数" used={String(budget.used_calls)} total={String(budget.max_llm_calls)} /><BudgetMetric label="费用" used={formatCost(budget.used_cost)} total={formatCost(budget.max_cost)} /></div><p className="mt-5 text-xs leading-relaxed text-muted-foreground">{pressureExplanation(pressure)}</p></> : <p className="mt-4 text-sm text-muted-foreground">该运行没有可用的预算明细，可能使用了仅硬限制策略。</p>}</div>
      </section>

      {approvalId && approvalPayload ? <section className="surface border-warning/30 bg-gradient-to-r from-warning/10 to-white p-5"><div className="grid gap-5 lg:grid-cols-[auto_1fr_auto] lg:items-center"><div className="flex items-center gap-3 text-warning"><span className="flex h-11 w-11 items-center justify-center rounded-full bg-warning/10"><ShieldAlert className="h-5 w-5" /></span><div><p className="font-semibold">需要你的确认</p><p className="mt-1 text-xs text-muted-foreground">Agent 正在等待高风险操作审批</p></div></div><div className="border-border lg:border-l lg:pl-6"><p className="font-semibold">{String(approvalPayload.description ?? approvalPayload.action_type ?? "执行高风险操作")}</p><p className="mt-1 text-xs text-muted-foreground">{String(approvalPayload.reason ?? "审批前请确认操作范围、风险与预期资源消耗。")}</p></div><button onClick={() => setApprovalOpen(true)} className="btn btn-primary">处理审批<ArrowRight className="h-4 w-4" /></button></div></section> : null}

      <section className="surface overflow-hidden"><Tabs tabs={[{ key: "observatory", label: "观测" }, { key: "timeline", label: "事件时间线", count: events.length }, { key: "calls", label: "模型调用", count: calls.length }, { key: "budget", label: "阶段预算" }, { key: "info", label: "运行信息" }] as { key: Tab; label: string; count?: number }[]} active={tab} onChange={setTab} ariaLabel="运行诊断" /><div className="p-4 sm:p-6">{tab === "observatory" ? <TokenObservatory calls={calls} /> : null}{tab === "timeline" ? <Timeline events={events} pendingApprovalId={approvalId} onOpenApproval={() => setApprovalOpen(true)} /> : null}{tab === "calls" ? <LlmCallsTable calls={calls} /> : null}{tab === "budget" ? <BudgetView detail={budgetDetail} events={events} /> : null}{tab === "info" ? <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">{infoItems.map(([label, value]) => <div key={label} className="rounded-lg border border-border bg-muted/25 p-4"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-2 break-all font-medium">{value ?? "—"}</dd></div>)}</dl> : null}</div></section>

      <div className="flex items-center justify-between text-xs text-muted-foreground"><span className="inline-flex items-center gap-2"><Clock3 className="h-3.5 w-3.5" />{terminal ? "运行已结束" : "每 3 秒自动刷新"}</span>{!connected ? <button onClick={() => void load(false)} className="inline-flex items-center gap-1 font-semibold text-accent"><RefreshCw className="h-3.5 w-3.5" />立即重试</button> : null}</div>

      {approvalOpen && approvalId && approvalPayload ? <ApprovalModal approvalId={approvalId} payload={approvalPayload} onDecide={decideApproval} onClose={() => { dismissedApprovalId.current = approvalId; setApprovalOpen(false); }} /> : null}
    </div>
  );
}
