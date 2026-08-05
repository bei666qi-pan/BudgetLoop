"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowRight, Bell, GitBranch, Plus, RefreshCw, Search, UsersRound, X } from "lucide-react";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  aggregateContainerCounts,
  CONTAINER_LIFECYCLE_LABELS,
  CONTAINER_TEAM_STATUS_LABELS,
  deriveTeamStatus,
  filterContainers,
  lifecycleTone,
  teamStatusTone,
  type ContainerFilter,
} from "@/lib/container-presentation";
import { formatDateTime } from "@/lib/format";
import type { WorkContainer } from "@/lib/types";

const FILTERS: { key: ContainerFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "active", label: "活跃" },
  { key: "paused", label: "已暂停" },
  { key: "completed", label: "已完成" },
];

function LoadingOverview() {
  return (
    <div className="page-shell space-y-7" aria-busy="true">
      <div className="space-y-3">
        <div className="skeleton h-10 w-56" />
        <div className="skeleton h-5 w-96 max-w-full" />
      </div>
      <div className="skeleton h-36 rounded-xl" />
      <div className="skeleton h-12 w-full" />
      <div className="skeleton h-[360px] rounded-xl" />
    </div>
  );
}

function ActiveSessionText({ container }: { container: WorkContainer }) {
  const active = container.active_session_count ?? container.counts.running;
  const total = container.counts.sessions;
  return (
    <span className="tabular-nums">
      <span className="text-foreground">{active}</span>
      <span className="text-border-strong">/</span>
      <span>{total}</span>
      <span className="ml-1 text-xs text-muted-foreground">活跃</span>
    </span>
  );
}

export default function ContainersPage() {
  const router = useRouter();
  const [containers, setContainers] = useState<WorkContainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [filter, setFilter] = useState<ContainerFilter>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<{ containers: WorkContainer[] }>("/api/work-containers");
      setContainers(data.containers);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载工作容器。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  const totals = useMemo(() => aggregateContainerCounts(containers), [containers]);
  const visible = useMemo(
    () => filterContainers(containers, deferredQuery, filter),
    [containers, deferredQuery, filter],
  );

  if (loading) return <LoadingOverview />;

  return (
    <div className="page-shell animate-in space-y-7">
      <header>
        <div>
          <h1 className="page-heading">Agent Team</h1>
          <p className="page-subtitle">将独立会话组织为可控、可审计的项目团队</p>
        </div>
      </header>

      {error ? (
        <section role="alert" className="surface flex flex-col gap-4 border-critical/20 bg-critical/5 p-5 sm:flex-row sm:items-center">
          <AlertCircle className="h-6 w-6 shrink-0 text-critical" />
          <div className="flex-1">
            <h2 className="font-semibold">Agent Team 暂时无法加载</h2>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          </div>
          <button onClick={() => void load()} className="btn btn-secondary">
            <RefreshCw className="h-4 w-4" />重试
          </button>
        </section>
      ) : null}

      {!error && containers.length === 0 ? (
        <section className="surface flex min-h-[460px] flex-col items-center justify-center px-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <UsersRound className="h-7 w-7" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">创建第一个隔离的 Agent Team</h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
            先定义项目目标与共享上下文，再按角色启动多个拥有独立预算、对话和可选 worktree 的 Session。
          </p>
          <Link href="/containers/new" className="btn btn-primary mt-6">
            <Plus className="h-4 w-4" />创建工作容器
          </Link>
        </section>
      ) : null}

      {!error && containers.length > 0 ? (
        <>
          <section
            className="surface grid grid-cols-2 divide-x divide-y divide-border overflow-hidden sm:grid-cols-4 sm:divide-y-0"
            aria-label="Agent Team 摘要"
          >
            {[
              { label: "工作容器", value: totals.containers, color: "bg-info" },
              { label: "运行中的 Session", value: totals.running, color: "bg-success" },
              { label: "等待处理", value: totals.waiting, color: "bg-warning" },
              { label: "需要关注", value: totals.attention, color: "bg-critical" },
            ].map((item) => (
              <div key={item.label} className="p-5 sm:p-7">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <span className={`h-2.5 w-2.5 rounded-sm ${item.color}`} />
                  {item.label}
                </div>
                <p className="mt-2 text-3xl font-semibold tabular-nums">{item.value}</p>
              </div>
            ))}
          </section>

          <section className="flex flex-col gap-3 lg:flex-row" aria-label="工作容器筛选">
            <label className="relative block lg:w-[390px]">
              <span className="sr-only">搜索工作容器</span>
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索工作容器"
                className="input-base w-full pl-10 pr-10"
              />
              {query ? (
                <button
                  onClick={() => setQuery("")}
                  aria-label="清除搜索"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-muted-foreground hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null}
            </label>
            <div
              className="flex min-h-11 overflow-x-auto rounded-lg border border-border bg-white p-1 shadow-control"
              role="group"
              aria-label="按生命周期筛选"
            >
              {FILTERS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setFilter(item.key)}
                  aria-pressed={filter === item.key}
                  className={`shrink-0 rounded-md px-5 py-2 text-sm font-semibold transition-colors ${
                    filter === item.key
                      ? "bg-muted text-accent ring-1 ring-inset ring-accent/20"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>

          <section className="surface overflow-hidden" aria-label="工作容器列表">
            {visible.length === 0 ? (
              <div className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
                <Search className="h-8 w-8 text-muted-foreground" />
                <h2 className="mt-3 font-semibold">没有匹配的工作容器</h2>
                <button
                  onClick={() => { setQuery(""); setFilter("all"); }}
                  className="btn btn-secondary mt-4"
                >
                  重置筛选
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table min-w-[1280px] xl:min-w-[1400px]">
                  <thead>
                    <tr>
                      <th>工作容器</th>
                      <th>团队状态</th>
                      <th>Session 数</th>
                      <th>活跃中</th>
                      <th>运行 / 关注</th>
                      <th>告警</th>
                      <th>工作区策略</th>
                      <th>最近活动</th>
                      <th className="text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((container) => {
                      const teamStatus = deriveTeamStatus(container);
                      const alertCount = container.alert_count ?? container.counts.attention;
                      const hasAlerts = alertCount > 0;

                      return (
                        <tr
                          key={container.id}
                          onClick={() => router.push(`/containers/${container.id}`)}
                          className="cursor-pointer"
                          role="link"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              router.push(`/containers/${container.id}`);
                            }
                          }}
                          aria-label={`打开团队 ${container.name}`}
                        >
                          <td className="max-w-[390px]">
                            <div className="flex items-start gap-3">
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/8 text-accent">
                                <UsersRound className="h-4 w-4" />
                              </span>
                              <span>
                                <span className="font-semibold text-foreground">{container.name}</span>
                                <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                                  {container.project_goal}
                                </span>
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className={`badge ${teamStatusTone(teamStatus)}`}>
                              {CONTAINER_TEAM_STATUS_LABELS[teamStatus]}
                            </span>
                          </td>
                          <td className="font-mono tabular-nums">{container.counts.sessions}</td>
                          <td>
                            <ActiveSessionText container={container} />
                          </td>
                          <td className="font-mono tabular-nums">
                            <span>{container.counts.running}</span>
                            <span className="mx-2 text-border-strong">/</span>
                            <span className={container.counts.attention ? "text-critical" : ""}>
                              {container.counts.attention}
                            </span>
                          </td>
                          <td>
                            {hasAlerts ? (
                              <Link
                                href={`/containers/${container.id}`}
                                onClick={(e) => e.stopPropagation()}
                                className="badge badge-critical inline-flex items-center gap-1.5 cursor-pointer hover:ring-2"
                                aria-label={`${alertCount} 条告警`}
                              >
                                <Bell className="h-3 w-3" />
                                {alertCount}
                              </Link>
                            ) : (
                              <span className="badge badge-muted">—</span>
                            )}
                          </td>
                          <td>
                            <span className="flex items-center gap-2 text-xs font-medium">
                              <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
                              {container.default_workspace_policy === "worktree" ? "默认 Worktree" : "独立工作区"}
                            </span>
                          </td>
                          <td className="text-xs text-muted-foreground">
                            {formatDateTime(container.updated_at)}
                          </td>
                          <td className="text-right">
                            <span className="inline-flex items-center gap-1 text-muted-foreground">
                              <ArrowRight className="h-4 w-4" />
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <p className="text-xs text-muted-foreground">
            显示 {visible.length} / {containers.length} 个工作容器
          </p>
        </>
      ) : null}
    </div>
  );
}
