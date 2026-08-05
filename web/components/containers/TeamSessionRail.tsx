"use client";

import { AlertTriangle, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { ProgressBar } from "@/components/ui";
import { CreateSessionDialog } from "@/components/containers/CreateSessionDialog";
import { relativeTime } from "@/lib/format";
import type { CreateWorkSessionRequest, PressureMode, TeamSessionView } from "@/lib/types";

type FilterMode = "all" | "mine" | "blocked";

const FILTER_OPTIONS: { value: FilterMode; label: string }[] = [
  { value: "all", label: "全部消息" },
  { value: "mine", label: "@我的" },
  { value: "blocked", label: "仅阻塞" },
];

const PRESSURE_ORDER: Record<PressureMode, number> = {
  CRITICAL: 0,
  CONSERVATIVE: 1,
  NORMAL: 2,
};

const PRESSURE_LABELS: Record<PressureMode, string> = {
  NORMAL: "正常",
  CONSERVATIVE: "保守",
  CRITICAL: "紧急",
};

const PRESSURE_BADGE_CLASS: Record<PressureMode, string> = {
  NORMAL: "badge-success",
  CONSERVATIVE: "badge-warning",
  CRITICAL: "badge-critical",
};

/** 状态圆点颜色：green=running, yellow=paused, gray=waiting, red=blocked/error */
function statusDotColor(status: string): string {
  if (["FAILED", "BUDGET_EXHAUSTED", "CANCELLED"].includes(status)) return "bg-critical";
  if (["PAUSED", "WAITING_APPROVAL"].includes(status)) return "bg-warning";
  if (["PENDING"].includes(status)) return "bg-muted-foreground";
  if (["COMPLETED", "PARTIAL_COMPLETED"].includes(status)) return "bg-info";
  return "bg-success";
}

/** 排序：CRITICAL 最先 → CONSERVATIVE → NORMAL；同压力按 last_activity 降序 */
function sortSessions(list: TeamSessionView[]): TeamSessionView[] {
  return [...list].sort((a, b) => {
    const pa = PRESSURE_ORDER[a.pressure_mode] ?? 99;
    const pb = PRESSURE_ORDER[b.pressure_mode] ?? 99;
    if (pa !== pb) return pa - pb;
    const aTime = a.last_activity ? new Date(a.last_activity).getTime() : 0;
    const bTime = b.last_activity ? new Date(b.last_activity).getTime() : 0;
    return bTime - aTime;
  });
}

function applyFilter(list: TeamSessionView[], filter: FilterMode): TeamSessionView[] {
  if (filter === "blocked") return list.filter((s) => s.blocked || s.needs_operator);
  if (filter === "mine") return list.filter((s) => s.needs_operator);
  return list;
}

function SessionItem({
  session,
  selected,
  onSelect,
}: {
  session: TeamSessionView;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const hasAlert = session.blocked || session.needs_operator;
  return (
    <button
      type="button"
      onClick={() => onSelect(session.id)}
      aria-pressed={selected}
      className={`relative w-full border-b border-border px-4 py-4 text-left transition-colors duration-fast ${
        selected ? "bg-accent/[0.055]" : "hover:bg-muted/45"
      }`}
    >
      {selected ? <span className="absolute inset-y-0 left-0 w-0.5 bg-accent" /> : null}

      {/* Row 1: status dot + role + pressure badge + alert */}
      <span className="flex items-center gap-2">
        <span
          className={`h-2 w-2 shrink-0 rounded-full ${statusDotColor(session.status)}`}
          aria-label={`状态: ${session.status}`}
        />
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
          {session.role}
        </span>
        {hasAlert ? (
          <AlertTriangle
            className="h-4 w-4 shrink-0 text-critical"
            aria-label={
              session.blocked && session.needs_operator
                ? "阻塞且需要操作员介入"
                : session.blocked
                  ? "已阻塞"
                  : "需要操作员介入"
            }
          />
        ) : null}
        <span className={`badge text-2xs shrink-0 ${PRESSURE_BADGE_CLASS[session.pressure_mode] ?? "badge-muted"}`}>
          {PRESSURE_LABELS[session.pressure_mode] ?? session.pressure_mode}
        </span>
      </span>

      {/* Row 2: current phase + last activity */}
      <span className="mt-1.5 flex items-center justify-between gap-2">
        <span className="truncate text-xs text-muted-foreground">
          {session.current_phase || "未上报"}
        </span>
        <span className="shrink-0 text-2xs tabular-nums text-muted-foreground">
          {relativeTime(session.last_activity)}
        </span>
      </span>

      {/* Row 3: token usage bar */}
      {typeof session.budget_ratio === "number" ? (
        <span className="mt-2 block">
          <ProgressBar
            ratio={Math.min(1, Math.max(0, session.budget_ratio))}
            color={
              session.pressure_mode === "CRITICAL"
                ? "bg-critical"
                : session.pressure_mode === "CONSERVATIVE"
                  ? "bg-warning"
                  : "bg-accent"
            }
            height="h-1.5"
          />
        </span>
      ) : null}
    </button>
  );
}

export function TeamSessionRail({
  sessions,
  selectedId,
  onSelect,
  isMobile,
  busy,
  createError,
  onCreateSession,
}: {
  sessions: TeamSessionView[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** 移动端标签布局：渲染为扁平可滚动列表，无横向溢出 */
  isMobile?: boolean;
  busy?: boolean;
  createError?: string | null;
  onCreateSession?: (body: CreateWorkSessionRequest) => Promise<void>;
}) {
  const [filter, setFilter] = useState<FilterMode>("all");
  const [dialogOpen, setDialogOpen] = useState(false);

  const filtered = useMemo(() => {
    const filteredByMode = applyFilter(sessions, filter);
    return sortSessions(filteredByMode);
  }, [sessions, filter]);

  const filterSelect = (
    <select
      value={filter}
      onChange={(e) => setFilter(e.target.value as FilterMode)}
      aria-label="筛选 Session"
      className="min-h-9 rounded-lg border border-border bg-white px-3 text-xs font-semibold text-foreground"
    >
      {FILTER_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );

  /* ── 移动端：扁平可滚动列表，无横向溢出 ── */
  if (isMobile) {
    return (
      <div className="flex min-h-0 min-w-[390px] flex-col" aria-label="Session 列表">
        <div className="flex items-center justify-between gap-2 px-4 py-3">
          {filterSelect}
          {onCreateSession ? (
            <button
              type="button"
              onClick={() => setDialogOpen(true)}
              className="btn btn-ghost min-h-9 shrink-0 px-3 text-xs font-semibold"
            >
              <Plus className="h-4 w-4" />
              新建 Session
            </button>
          ) : null}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="px-4 py-8 text-center text-xs text-muted-foreground">
              {filter === "blocked" ? "没有阻塞的 Session" : filter === "mine" ? "没有与你相关的消息" : "暂无 Session"}
            </p>
          ) : (
            filtered.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                selected={session.id === selectedId}
                onSelect={onSelect}
              />
            ))
          )}
        </div>
        {onCreateSession ? (
          <CreateSessionDialog
            open={dialogOpen}
            defaultWorktree={false}
            busy={busy ?? false}
            error={createError ?? null}
            onClose={() => setDialogOpen(false)}
            onCreate={async (body) => {
              await onCreateSession(body);
              setDialogOpen(false);
            }}
          />
        ) : null}
      </div>
    );
  }

  /* ── 桌面端：侧栏 w-72 ── */
  return (
    <aside
      className="flex min-h-0 w-72 flex-col border-r border-border bg-white/60"
      aria-label="Session 列表"
    >
      {/* 筛选栏 */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        {filterSelect}
        <span className="font-mono text-xs text-muted-foreground">{filtered.length}</span>
      </div>

      {/* Session 列表 */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-muted-foreground">
            {filter === "blocked" ? "没有阻塞的 Session" : filter === "mine" ? "没有与你相关的消息" : "暂无 Session"}
          </p>
        ) : (
          filtered.map((session) => (
            <SessionItem
              key={session.id}
              session={session}
              selected={session.id === selectedId}
              onSelect={onSelect}
            />
          ))
        )}
      </div>

      {/* 底部新建按钮 */}
      {onCreateSession ? (
        <>
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="flex min-h-14 items-center gap-2 border-t border-border px-5 text-sm font-semibold text-accent transition-colors hover:bg-accent/5"
          >
            <Plus className="h-4 w-4" />
            新建 Session
          </button>
          <CreateSessionDialog
            open={dialogOpen}
            defaultWorktree={false}
            busy={busy ?? false}
            error={createError ?? null}
            onClose={() => setDialogOpen(false)}
            onCreate={async (body) => {
              await onCreateSession(body);
              setDialogOpen(false);
            }}
          />
        </>
      ) : null}
    </aside>
  );
}
