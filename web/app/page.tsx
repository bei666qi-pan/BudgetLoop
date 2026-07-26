"use client";

import Link from "next/link";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowRight, RefreshCw, Search, Settings2, Trash2, X } from "lucide-react";
import { HomeTaskIntake } from "@/components/home/HomeTaskIntake";
import { apiFetch } from "@/lib/api";
import { formatCost, formatDateTime, formatTokens } from "@/lib/format";
import {
  filterTasks,
  statusClass,
  STATUS_LABELS,
  taskCounts,
  type TaskFilter,
} from "@/lib/presentation";
import { isTerminal, type TaskListItem } from "@/lib/types";

const FILTERS: { key: TaskFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "active", label: "运行中" },
  { key: "pending", label: "待处理" },
  { key: "completed", label: "已完成" },
  { key: "attention", label: "需关注" },
];

function LoadingRecentTasks() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="正在加载最近任务">
      <div className="skeleton h-24 w-full rounded-xl" />
      <div className="skeleton h-14 w-full rounded-xl" />
      <div className="skeleton h-48 w-full rounded-xl" />
    </div>
  );
}

function RecentTaskTable({ tasks, onDelete, deletingId }: { tasks: TaskListItem[]; onDelete: (task: TaskListItem) => void; deletingId: string | null }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead><tr><th>任务</th><th>状态</th><th>迭代轮次</th><th>Token</th><th>费用</th><th className="text-right">操作</th></tr></thead>
        <tbody>
          {tasks.map((task) => {
            const run = task.latest_run;
            const href = run ? `/runs/${run.id}` : "/new";
            const action = run?.status === "WAITING_APPROVAL"
              ? "处理审批"
              : run?.status === "COMPLETED"
                || run?.status === "PARTIAL_COMPLETED"
                || run?.status === "BUDGET_EXHAUSTED"
                || run?.status === "FAILED"
                ? "查看结果"
                : run ? "继续监督" : "开始运行";
            return (
              <tr key={task.id}>
                <td><p className="font-semibold text-foreground">{task.name}</p>{task.created_at ? <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(task.created_at)}</p> : null}</td>
                <td><span className={`badge ${statusClass(run?.status)}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{run ? STATUS_LABELS[run.status] ?? run.status : "未运行"}</span></td>
                <td className="font-mono tabular-nums">{run ? `第 ${run.iteration} 轮` : "—"}</td>
                <td className="font-mono tabular-nums">{run ? formatTokens(run.used_tokens ?? 0) : "—"}</td>
                <td className="font-mono tabular-nums">{run?.used_cost != null ? formatCost(run.used_cost) : "—"}</td>
                <td className="text-right"><span className="inline-flex items-center gap-1"><Link href={href} className="btn btn-secondary min-h-9 px-3 text-xs">{action}<ArrowRight className="h-3.5 w-3.5" /></Link>{run && isTerminal(run.status) ? <button type="button" aria-label={`删除任务 ${task.name}`} title="删除历史" disabled={deletingId === task.id} onClick={() => onDelete(task)} className="btn btn-ghost min-h-9 px-2 text-critical"><Trash2 className="h-3.5 w-3.5" /></button> : null}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function HomePage() {
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [deleteTarget, setDeleteTarget] = useState<TaskListItem | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<TaskListItem[] | { tasks?: TaskListItem[] }>("/api/tasks");
      setTasks(Array.isArray(data) ? data : data.tasks ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载任务，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadTasks(); }, [loadTasks]);
  const counts = useMemo(() => taskCounts(tasks), [tasks]);
  const visibleTasks = useMemo(
    () => filterTasks(tasks, deferredQuery, filter),
    [tasks, deferredQuery, filter],
  );
  const hasFilters = query.trim().length > 0 || filter !== "all";

  const deleteTask = useCallback(async () => {
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    setDeleteError(null);
    try {
      await apiFetch<void>(`/api/tasks/${deleteTarget.id}`, { method: "DELETE" });
      setTasks((current) => current.filter((task) => task.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (reason) {
      setDeleteError(reason instanceof Error ? reason.message : "无法删除这条任务历史，请重试。");
    } finally {
      setDeletingId(null);
    }
  }, [deleteTarget]);

  return (
    <div className="page-shell animate-in space-y-10">
      <HomeTaskIntake />

      <section className="space-y-6 border-t border-border pt-8" aria-labelledby="recent-work-heading">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div><h2 id="recent-work-heading" className="text-xl font-semibold tracking-[-0.025em] sm:text-2xl">最近任务</h2><p className="mt-1 text-sm text-muted-foreground">继续监督运行、处理审批或查看结果</p></div>
          <Link href="/new" className="btn btn-ghost self-start sm:self-auto"><Settings2 className="h-4 w-4" />高级手动配置</Link>
        </header>

        {loading ? <LoadingRecentTasks /> : null}

        {!loading && error ? (
          <div role="alert" className="surface flex flex-col gap-4 border-critical/20 bg-critical/5 p-5 sm:flex-row sm:items-center">
            <AlertCircle className="h-6 w-6 shrink-0 text-critical" /><div className="flex-1"><h3 className="font-semibold">最近任务暂时无法加载</h3><p className="mt-1 text-sm text-muted-foreground">{error}</p><p className="mt-1 text-xs text-muted-foreground">上方的新任务描述仍可继续使用。</p></div>
            <button type="button" onClick={() => void loadTasks()} className="btn btn-secondary"><RefreshCw className="h-4 w-4" />重试</button>
          </div>
        ) : null}

        {!loading && !error && tasks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-strong bg-white/55 px-6 py-8 text-center"><h3 className="font-semibold">还没有历史任务</h3><p className="mt-1 text-sm text-muted-foreground">从上方描述第一个目标，确认后这里会出现可监督的运行。</p></div>
        ) : null}

        {!loading && !error && tasks.length > 0 ? (
          <>
            <div className="surface grid grid-cols-2 divide-x divide-y divide-border overflow-hidden sm:grid-cols-4 sm:divide-y-0" aria-label="任务摘要">
              {[
                { label: "全部任务", value: counts.all, color: "bg-info" },
                { label: "运行中", value: counts.active, color: "bg-success" },
                { label: "待处理", value: counts.pending, color: "bg-warning" },
                { label: "需关注", value: counts.attention, color: "bg-critical" },
              ].map((item) => <div key={item.label} className="p-4 sm:p-5"><div className="flex items-center gap-2 text-xs font-medium text-muted-foreground"><span className={`h-2.5 w-2.5 rounded-sm ${item.color}`} />{item.label}</div><p className="mt-1 text-2xl font-semibold tabular-nums">{item.value}</p></div>)}
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center" aria-label="任务筛选">
              <label className="relative block lg:w-[390px]"><span className="sr-only">搜索任务</span><Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索最近任务" className="input-base w-full pl-10 pr-10" />{query ? <button type="button" aria-label="清除搜索" onClick={() => setQuery("")} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-muted-foreground hover:bg-muted"><X className="h-4 w-4" /></button> : null}</label>
              <div className="flex min-h-11 overflow-x-auto rounded-lg border border-border bg-white p-1 shadow-control" role="group" aria-label="按状态筛选">{FILTERS.map((item) => <button key={item.key} type="button" onClick={() => setFilter(item.key)} aria-pressed={filter === item.key} className={`shrink-0 rounded-md px-4 py-2 text-sm font-semibold transition-colors ${filter === item.key ? "bg-muted text-accent ring-1 ring-inset ring-accent/20" : "text-muted-foreground hover:text-foreground"}`}>{item.label}</button>)}</div>
            </div>

            <div className="surface overflow-hidden" aria-label="任务列表">
              {visibleTasks.length === 0 ? <div className="flex min-h-52 flex-col items-center justify-center p-8 text-center"><Search className="h-7 w-7 text-muted-foreground" /><h3 className="mt-3 font-semibold">没有匹配的任务</h3><p className="mt-1 text-sm text-muted-foreground">调整搜索词或状态筛选后再试。</p><button type="button" onClick={() => { setQuery(""); setFilter("all"); }} className="btn btn-secondary mt-4">重置筛选</button></div> : <RecentTaskTable tasks={visibleTasks} onDelete={(task) => { setDeleteError(null); setDeleteTarget(task); }} deletingId={deletingId} />}
            </div>
            <p className="text-xs text-muted-foreground">显示 {visibleTasks.length} / {tasks.length} 个任务{hasFilters ? " · 已应用筛选" : ""}</p>
          </>
        ) : null}
      </section>
      {deleteTarget ? <div className="fixed inset-0 z-50 grid place-items-center bg-[#07152D]/25 p-4 backdrop-blur-sm" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !deletingId) setDeleteTarget(null); }}><section role="dialog" aria-modal="true" aria-labelledby="delete-task-title" className="surface w-full max-w-md p-5 shadow-elevated"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-critical/10 text-critical"><Trash2 className="h-5 w-5" /></div><h2 id="delete-task-title" className="mt-4 text-lg font-semibold">删除“{deleteTarget.name}”？</h2><p className="mt-2 text-sm leading-relaxed text-muted-foreground">这会删除该任务及运行历史，且无法撤销。不会删除项目文件或其他任务。</p>{deleteError ? <p role="alert" className="mt-3 text-sm text-critical">{deleteError}</p> : null}<div className="mt-5 flex justify-end gap-2"><button type="button" className="btn btn-secondary" disabled={Boolean(deletingId)} onClick={() => setDeleteTarget(null)}>取消</button><button type="button" className="btn btn-destructive" disabled={Boolean(deletingId)} onClick={() => void deleteTask()}>{deletingId ? "正在删除…" : "确认删除"}</button></div></section></div> : null}
    </div>
  );
}
