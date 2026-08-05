"use client";

import {
  AlertTriangle,
  Ban,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Gauge,
  Info,
  Pause,
  Play,
  RefreshCw,
  Send,
  Settings2,
  Shuffle,
  Square,
  TrendingUp,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  appendSessionInstruction,
  cancelSession,
  fetchTeamProgress,
  fetchTeamUsage,
  pauseContainer,
  pauseSession as apiPauseSession,
  patchContainerBudget,
  patchSessionBudget,
  resumeContainer,
  resumeSession as apiResumeSession,
  stopContainer,
} from "@/lib/api";
import { formatCost, formatDurationMs, formatTokens, percent } from "@/lib/format";
import { STATUS_LABELS, statusClass } from "@/lib/presentation";
import type {
  PressureMode,
  SessionBudgetPatch,
  SessionProgressSignal,
  TeamBudgetPatch,
  TeamInspectorProgress,
  TeamInspectorUsage,
  WorkContainer,
  WorkSessionSummary,
} from "@/lib/types";
import { EmptyState, KeyValue, ProgressBar } from "@/components/ui";

/* ── 折叠区块 ── */

function CollapsibleSection({
  title,
  icon,
  defaultExpanded,
  badge,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  defaultExpanded: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const Icon = expanded ? ChevronDown : ChevronRight;

  return (
    <section className="border-b border-border">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-muted/40 transition-colors duration-fast"
        aria-expanded={expanded}
      >
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          {icon}
          {title}
        </span>
        {badge ? <span className="ml-auto">{badge}</span> : null}
      </button>
      {expanded ? (
        <div className="px-4 pb-4 pt-1 space-y-4">{children}</div>
      ) : null}
    </section>
  );
}

/* ── 确认对话框 ── */

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  confirmClass,
  onConfirm,
  onCancel,
  busy,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  confirmClass?: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
      <div
        className="card mx-4 w-full max-w-sm animate-in p-6"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
      >
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <AlertTriangle className="h-4 w-4 text-warning" />
          {title}
        </h3>
        <p className="mt-3 text-sm text-muted-foreground">{message}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn btn-ghost min-h-9 px-3 text-xs"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`btn min-h-9 px-3 text-xs ${confirmClass ?? "btn-destructive"}`}
          >
            {busy ? "处理中…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── 内联预算调整表单 ── */

function BudgetAdjustForm({
  label,
  currentValue,
  maxValue,
  usedValue,
  reservedValue,
  onConfirm,
  onCancel,
  busy,
}: {
  label: string;
  currentValue: number;
  maxValue?: number;
  usedValue?: number;
  reservedValue?: number;
  onConfirm: (newValue: number) => Promise<void>;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [draft, setDraft] = useState(String(currentValue));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const newVal = Number(draft);
  const isValid =
    !Number.isNaN(newVal) && newVal > 0 && draft.trim() !== "";
  const minAllowed =
    usedValue !== undefined && reservedValue !== undefined
      ? usedValue + reservedValue
      : 0;

  async function handleSubmit() {
    if (!isValid) return;
    if (newVal < minAllowed) {
      setError(`新预算不能低于已使用+已预留 (${minAllowed.toLocaleString()})`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm(newVal);
      onCancel();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "调整失败，请重试",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">
          当前: {currentValue.toLocaleString()}
        </span>
      </div>

      {usedValue !== undefined && (
        <div className="text-xs text-muted-foreground">
          已使用: {usedValue.toLocaleString()}
          {reservedValue !== undefined && reservedValue > 0
            ? ` · 已预留: ${reservedValue.toLocaleString()}`
            : ""}
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          type="number"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setError(null);
          }}
          min={minAllowed}
          className="input-base min-h-9 flex-1 px-2 py-1.5 text-xs"
          placeholder="新预算值"
          aria-label={`${label}新值`}
        />
      </div>

      {isValid && newVal !== currentValue && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="h-3 w-3" />
          {newVal > currentValue
            ? `${currentValue.toLocaleString()} → ${newVal.toLocaleString()}（增加 ${(newVal - currentValue).toLocaleString()}）`
            : `${currentValue.toLocaleString()} → ${newVal.toLocaleString()}（减少 ${(currentValue - newVal).toLocaleString()}）`}
        </div>
      )}

      {error ? <p className="text-xs text-critical">{error}</p> : null}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy || submitting}
          className="btn btn-ghost min-h-8 flex-1 px-2 text-xs"
        >
          取消
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={busy || submitting || !isValid}
          className="btn btn-primary min-h-8 flex-1 px-2 text-xs"
        >
          {submitting ? "提交中…" : "确认调整"}
        </button>
      </div>
    </div>
  );
}

/* ── 健康状态标识 ── */

function HealthBadge({ health }: { health: PressureMode }) {
  const map: Record<PressureMode, { label: string; cls: string }> = {
    NORMAL: { label: "正常", cls: "badge-success" },
    CONSERVATIVE: { label: "保守", cls: "badge-warning" },
    CRITICAL: { label: "危急", cls: "badge-critical" },
  };
  const { label, cls } = map[health] ?? { label: health, cls: "badge-muted" };
  return <span className={`badge ${cls}`}>{label}</span>;
}

/* ── 空值占位 ── */

function MaybeValue({
  value,
  format,
}: {
  value: number | null | undefined;
  format: (v: number) => string;
}) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground italic">未上报</span>;
  }
  return <span className="tabular-nums">{format(value)}</span>;
}

/* ── 进度区块 ── */

function ProgressSection({
  progress,
  selectedSessionId,
  sessions,
  loading,
}: {
  progress: TeamInspectorProgress | null;
  selectedSessionId: string | null;
  sessions: WorkSessionSummary[];
  loading: boolean;
}) {
  const selectedSession = useMemo(() => {
    if (!selectedSessionId || !progress) return null;
    return (
      progress.sessions.find((s) => s.session_id === selectedSessionId) ?? null
    );
  }, [progress, selectedSessionId]);

  const selectedSummary = useMemo(() => {
    if (!selectedSessionId) return null;
    return sessions.find((s) => s.id === selectedSessionId) ?? null;
  }, [sessions, selectedSessionId]);

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-4 w-1/2" />
        <div className="skeleton h-4 w-2/3" />
      </div>
    );
  }

  if (!progress) {
    return (
      <EmptyState
        title="暂无进度数据"
        hint="团队尚未产生任何进度信号"
      />
    );
  }

  const summary = progress.team_summary;

  return (
    <div className="space-y-4">
      {/* 团队摘要 */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          团队摘要
        </h4>
        <div className="flex flex-wrap gap-2">
          {summary.running > 0 && (
            <span className="badge badge-info tabular-nums">
              <Play className="h-3 w-3" />运行中 {summary.running}
            </span>
          )}
          {summary.waiting > 0 && (
            <span className="badge badge-muted tabular-nums">
              <Clock className="h-3 w-3" />等待中 {summary.waiting}
            </span>
          )}
          {summary.paused > 0 && (
            <span className="badge badge-warning tabular-nums">
              <Pause className="h-3 w-3" />已暂停 {summary.paused}
            </span>
          )}
          {summary.blocked > 0 && (
            <span className="badge badge-critical tabular-nums">
              <Ban className="h-3 w-3" />已阻塞 {summary.blocked}
            </span>
          )}
          {summary.completed > 0 && (
            <span className="badge badge-success tabular-nums">
              <CheckCircle2 className="h-3 w-3" />已完成 {summary.completed}
            </span>
          )}
          {summary.running === 0 &&
            summary.waiting === 0 &&
            summary.paused === 0 &&
            summary.blocked === 0 &&
            summary.completed === 0 && (
              <span className="text-xs text-muted-foreground">
                暂无活跃 Session
              </span>
            )}
        </div>
        {progress.active_stage && (
          <KeyValue k="当前阶段" v={progress.active_stage} />
        )}
        {progress.next_focus != null && (
          <KeyValue
            k="下一步焦点"
            v={Array.isArray(progress.next_focus)
              ? progress.next_focus.map((f: Record<string, unknown>) => f.role ?? f.session_id).join("、")
              : String(progress.next_focus)
            }
          />
        )}
      </div>

      {/* 选中 Session 详情 */}
      {selectedSessionId && (
        <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            选中 Session{" "}
            {selectedSummary ? `: ${selectedSummary.role}` : ""}
          </h4>

          {selectedSession ? (
            <SessionProgressDetail signal={selectedSession} />
          ) : (
            <EmptyState title="Agent 未声明进度" hint="该 Session 尚未产生进度信号" />
          )}
        </div>
      )}
    </div>
  );
}

function SessionProgressDetail({
  signal,
}: {
  signal: SessionProgressSignal;
}) {
  const statusLabel =
    STATUS_LABELS[signal.needs_operator ? "WAITING_APPROVAL" : ""] ?? null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {signal.blocked && (
          <span className="badge badge-critical">
            <Ban className="h-3 w-3" />已阻塞
          </span>
        )}
        {signal.needs_operator && (
          <span className="badge badge-warning">
            <AlertTriangle className="h-3 w-3" />需操作员
          </span>
        )}
        {statusLabel && (
          <span className={`badge ${statusClass("WAITING_APPROVAL")}`}>
            {statusLabel}
          </span>
        )}
      </div>

      {signal.summary && (
        <KeyValue k="摘要" v={<span className="whitespace-pre-wrap text-xs">{signal.summary}</span>} />
      )}

      {signal.milestone && (
        <KeyValue
          k="里程碑"
          v={
            <span className="tabular-nums">
              {signal.milestone}
              {signal.completed_items != null &&
              signal.completed_items.length > 0 ? (
                <span className="ml-1 text-muted-foreground">
                  ({signal.completed_items.filter(Boolean).length} 项)
                </span>
              ) : null}
            </span>
          }
        />
      )}

      {signal.completed_items != null &&
        signal.completed_items.length > 0 && (
          <div>
            <span className="text-xs text-muted-foreground">已完成项</span>
            <ul className="mt-1 space-y-0.5">
              {signal.completed_items.filter(Boolean).map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-xs text-foreground"
                >
                  <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-success" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

      {signal.next_step && (
        <KeyValue k="下一步" v={signal.next_step} />
      )}

      {signal.blocked && signal.blocker_reason && (
        <div className="rounded border border-critical/20 bg-critical/5 p-2">
          <span className="text-xs font-semibold text-critical">阻塞原因</span>
          <p className="mt-1 text-xs text-foreground">
            {signal.blocker_reason}
          </p>
        </div>
      )}

      {signal.evidence && (
        <KeyValue
          k="证据"
          v={
            <code className="text-[10px] font-mono text-muted-foreground break-all">
              {signal.evidence}
            </code>
          }
        />
      )}

      <KeyValue
        k="迭代数"
        v={<span className="tabular-nums">{signal.iteration}</span>}
      />
    </div>
  );
}

/* ── 用量区块 ── */

function UsageSection({
  usage,
  loading,
}: {
  usage: TeamInspectorUsage | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-4 w-1/2" />
        <div className="skeleton h-2 w-full" />
      </div>
    );
  }

  if (!usage) {
    return (
      <EmptyState
        title="暂无用量数据"
        hint="团队尚未产生用量信息"
      />
    );
  }

  const tokenRatio = usage.tokens.max > 0 ? usage.tokens.used / usage.tokens.max : 0;
  const costRatio =
    usage.cost.max > 0 && usage.cost.used !== null
      ? usage.cost.used / usage.cost.max
      : 0;
  const timeRatio =
    usage.max_wall_time_ms > 0
      ? usage.wall_time_ms / usage.max_wall_time_ms
      : 0;
  const callsRatio =
    usage.calls.max > 0 ? usage.calls.used / usage.calls.max : 0;

  return (
    <div className="space-y-4">
      {/* 默认显示摘要（折叠时也可见，由父级控制） */}
      <div className="space-y-3">
        {/* Tokens */}
        <div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Tokens</span>
            <span className="tabular-nums font-semibold text-foreground">
              {formatTokens(usage.tokens.used)} / {formatTokens(usage.tokens.max)}
              {usage.tokens.max > 0 && (
                <span className="ml-1 text-muted-foreground">
                  ({percent(usage.tokens.used, usage.tokens.max)}%)
                </span>
              )}
            </span>
          </div>
          <div className="mt-1">
            <ProgressBar ratio={Math.min(1, tokenRatio)} />
          </div>
        </div>

        {/* 费用 */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">费用</span>
          <span className="tabular-nums font-semibold text-foreground">
            <MaybeValue
              value={usage.cost.used}
              format={formatCost}
            />{" "}
            / {formatCost(usage.cost.max)}
            {usage.cost.max > 0 && usage.cost.used !== null && (
              <span className="ml-1 text-muted-foreground">
                ({percent(usage.cost.used, usage.cost.max)}%)
              </span>
            )}
          </span>
        </div>

        {/* 耗时 */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">耗时</span>
          <span className="tabular-nums font-semibold text-foreground">
            {formatDurationMs(usage.wall_time_ms)} /{" "}
            {formatDurationMs(usage.max_wall_time_ms)}
          </span>
        </div>
        <div className="mt-1">
          <ProgressBar ratio={Math.min(1, timeRatio)} />
        </div>

        {/* 健康状态 */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">压力</span>
          <HealthBadge health={usage.health} />
        </div>

        {/* 调用数 */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">调用</span>
          <span className="tabular-nums font-semibold text-foreground">
            {usage.calls.used.toLocaleString()} /{" "}
            {usage.calls.max.toLocaleString()}
          </span>
        </div>
        <div className="mt-1">
          <ProgressBar ratio={Math.min(1, callsRatio)} />
        </div>

        {/* 消耗速率 */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">消耗速率</span>
          <MaybeValue
            value={usage.consumption_rate_tokens_per_min}
            format={(v) => `${v.toFixed(1)} tok/min`}
          />
        </div>

        {/* 预计耗尽 */}
        {usage.estimated_depletion_at && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">预计耗尽</span>
            <span className="tabular-nums font-semibold text-foreground">
              {new Date(usage.estimated_depletion_at).toLocaleTimeString(
                "zh-CN",
                { hour: "2-digit", minute: "2-digit" },
              )}
            </span>
          </div>
        )}
      </div>

      {/* 展开详情 */}
      <details className="group">
        <summary className="cursor-pointer text-xs font-semibold text-accent hover:underline">
          Token 明细
        </summary>
        <div className="mt-3 space-y-2 rounded border border-border p-3">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">Prompt</span>
              <div className="tabular-nums font-semibold text-foreground">
                <MaybeValue
                  value={usage.tokens.prompt}
                  format={(v) => v.toLocaleString()}
                />
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Completion</span>
              <div className="tabular-nums font-semibold text-foreground">
                <MaybeValue
                  value={usage.tokens.completion}
                  format={(v) => v.toLocaleString()}
                />
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Reasoning</span>
              <div className="tabular-nums font-semibold text-foreground">
                <MaybeValue
                  value={usage.tokens.reasoning}
                  format={(v) => v.toLocaleString()}
                />
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Cache</span>
              <div className="tabular-nums font-semibold text-foreground">
                <MaybeValue
                  value={usage.tokens.cache_read}
                  format={(v) => v.toLocaleString()}
                />
              </div>
            </div>
          </div>
        </div>
      </details>

      {/* 额外统计 */}
      <details className="group">
        <summary className="cursor-pointer text-xs font-semibold text-accent hover:underline">
          额外统计
        </summary>
        <div className="mt-3 space-y-2">
          {usage.active_time_ms !== null && (
            <KeyValue
              k="活跃时间"
              v={
                <span className="tabular-nums">
                  {formatDurationMs(usage.active_time_ms)}
                </span>
              }
            />
          )}
          {usage.active_time_ms === null && (
            <KeyValue
              k="活跃时间"
              v={<span className="text-muted-foreground italic">未上报</span>}
            />
          )}
          <KeyValue
            k="并行度"
            v={
              <span className="tabular-nums">
                {usage.parallelism.current} / {usage.parallelism.max}
                <span className="ml-1 text-xs text-muted-foreground">
                  (仅影响新调用)
                </span>
              </span>
            }
          />
        </div>
      </details>
    </div>
  );
}

/* ── 控制区块 ── */

function ControlSection({
  container,
  containerId,
  selectedSessionId,
  sessions,
  sseConnected,
  dataStale,
  usage,
  budgetNeedsResume,
  onRefresh,
  busy,
  setBusy,
}: {
  container: WorkContainer;
  containerId: string;
  selectedSessionId: string | null;
  sessions: WorkSessionSummary[];
  sseConnected: boolean;
  dataStale: boolean;
  usage: TeamInspectorUsage | null;
  budgetNeedsResume: boolean;
  onRefresh?: () => void;
  busy: boolean;
  setBusy: (v: boolean) => void;
}) {
  const controlsDisabled = !sseConnected || dataStale;

  // 团队控制状态
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [budgetAdjusting, setBudgetAdjusting] = useState(false);
  const [parallelismAdjusting, setParallelismAdjusting] = useState(false);

  // Session 控制状态
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [sessionBudgetAdjusting, setSessionBudgetAdjusting] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [instructionNotice, setInstructionNotice] = useState<string | null>(
    null,
  );

  const selectedSummary = useMemo(() => {
    if (!selectedSessionId) return null;
    return sessions.find((s) => s.id === selectedSessionId) ?? null;
  }, [sessions, selectedSessionId]);

  // 团队操作
  const handlePause = useCallback(async () => {
    setBusy(true);
    try {
      await pauseContainer(containerId);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, onRefresh, setBusy]);

  const handleResume = useCallback(async () => {
    setBusy(true);
    try {
      await resumeContainer(containerId);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, onRefresh, setBusy]);

  const handleStop = useCallback(async () => {
    setBusy(true);
    try {
      await stopContainer(containerId);
      setStopDialogOpen(false);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, onRefresh, setBusy]);

  const handleBudgetAdjust = useCallback(
    async (newValue: number) => {
      const body: TeamBudgetPatch = { max_total_tokens: newValue };
      const result = await patchContainerBudget(containerId, body);
      if (result.needs_resume) {
        onRefresh?.();
      }
    },
    [containerId, onRefresh],
  );

  const handleParallelismAdjust = useCallback(
    async (newValue: number) => {
      const body: TeamBudgetPatch = { max_parallel_llm_calls: newValue };
      await patchContainerBudget(containerId, body);
      onRefresh?.();
    },
    [containerId, onRefresh],
  );

  // Session 操作
  const handleSessionPause = useCallback(async () => {
    if (!selectedSessionId) return;
    setBusy(true);
    try {
      await apiPauseSession(containerId, selectedSessionId);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, selectedSessionId, onRefresh, setBusy]);

  const handleSessionResume = useCallback(async () => {
    if (!selectedSessionId) return;
    setBusy(true);
    try {
      await apiResumeSession(containerId, selectedSessionId);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, selectedSessionId, onRefresh, setBusy]);

  const handleSessionCancel = useCallback(async () => {
    if (!selectedSessionId) return;
    setBusy(true);
    try {
      await cancelSession(containerId, selectedSessionId);
      setCancelDialogOpen(false);
      onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [containerId, selectedSessionId, onRefresh, setBusy]);

  const handleSessionBudgetAdjust = useCallback(
    async (newValue: number) => {
      if (!selectedSessionId) return;
      const body: SessionBudgetPatch = { max_total_tokens: newValue };
      const result = await patchSessionBudget(
        containerId,
        selectedSessionId,
        body,
      );
      if (result.needs_resume) {
        onRefresh?.();
      }
    },
    [containerId, selectedSessionId, onRefresh],
  );

  const handleSendInstruction = useCallback(async () => {
    const clean = instruction.trim();
    if (!clean || !selectedSessionId) return;
    setBusy(true);
    try {
      await appendSessionInstruction(containerId, selectedSessionId, clean);
      setInstruction("");
      setInstructionNotice("指令已提交，将在下次执行检查点注入。");
    } catch (err: unknown) {
      setInstructionNotice(
        err instanceof Error ? err.message : "发送失败",
      );
    } finally {
      setBusy(false);
    }
  }, [containerId, selectedSessionId, instruction, setBusy]);

  // 团队模式切换
  const teamMode =
    container.preset_snapshot?.team_mode ?? null;
  const [modeDraft, setModeDraft] = useState(teamMode);

  useEffect(() => {
    setModeDraft(teamMode);
  }, [teamMode]);

  return (
    <div className="space-y-5">
      {/* 团队控制 */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          团队控制
        </h4>

        {controlsDisabled && (
          <div className="mb-3 rounded border border-warning/25 bg-warning/5 px-3 py-2 text-xs text-warning">
            {!sseConnected
              ? "SSE 已断开，控制操作不可用"
              : "数据可能过期，请等待连接恢复"}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handlePause}
            disabled={busy || controlsDisabled}
            className="btn btn-secondary min-h-9 px-3 text-xs"
          >
            <Pause className="h-3.5 w-3.5" />
            暂停
          </button>
          <button
            type="button"
            onClick={handleResume}
            disabled={busy || controlsDisabled}
            className="btn btn-secondary min-h-9 px-3 text-xs"
          >
            <Play className="h-3.5 w-3.5" />
            恢复
          </button>
          <button
            type="button"
            onClick={() => setStopDialogOpen(true)}
            disabled={busy || controlsDisabled}
            className="btn btn-destructive min-h-9 px-3 text-xs"
          >
            <Square className="h-3.5 w-3.5" />
            停止
          </button>
        </div>

        {budgetNeedsResume && (
          <button
            type="button"
            onClick={handleResume}
            disabled={busy || controlsDisabled}
            className="btn btn-primary mt-3 min-h-9 w-full px-3 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            已增加预算，请点击恢复
          </button>
        )}
      </div>

      {/* 预算调整 */}
      <div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            预算:{" "}
            <span className="tabular-nums font-semibold text-foreground">
              {usage
                ? `${formatTokens(usage.tokens.max)}`
                : "—"}
            </span>
          </span>
          {!budgetAdjusting ? (
            <button
              type="button"
              onClick={() => setBudgetAdjusting(true)}
              disabled={busy || controlsDisabled}
              className="btn btn-ghost min-h-8 px-2 text-xs"
            >
              <Settings2 className="h-3 w-3" />
              调整
            </button>
          ) : null}
        </div>
        {budgetAdjusting && usage && (
          <div className="mt-2">
            <BudgetAdjustForm
              label="团队预算 (Tokens)"
              currentValue={usage.tokens.max}
              usedValue={usage.tokens.used}
              reservedValue={0}
              onConfirm={handleBudgetAdjust}
              onCancel={() => setBudgetAdjusting(false)}
              busy={busy}
            />
          </div>
        )}
      </div>

      {/* 并行度调整 */}
      <div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            并行:{" "}
            <span className="tabular-nums font-semibold text-foreground">
              {usage ? `${usage.parallelism.current} / ${usage.parallelism.max}` : "—"}
            </span>
          </span>
          {!parallelismAdjusting ? (
            <button
              type="button"
              onClick={() => setParallelismAdjusting(true)}
              disabled={busy || controlsDisabled}
              className="btn btn-ghost min-h-8 px-2 text-xs"
            >
              <Settings2 className="h-3 w-3" />
              调整
            </button>
          ) : null}
        </div>
        {parallelismAdjusting && usage && (
          <div className="mt-2">
            <BudgetAdjustForm
              label="最大并行度"
              currentValue={usage.parallelism.max}
              onConfirm={handleParallelismAdjust}
              onCancel={() => setParallelismAdjusting(false)}
              busy={busy}
            />
          </div>
        )}
        <p className="field-hint mt-1">仅影响新发起的 LLM 调用</p>
      </div>

      {/* 团队模式切换 */}
      {teamMode && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            团队模式
          </h4>
          <div className="flex items-center gap-3 rounded border border-border p-3">
            <Shuffle className="h-4 w-4 text-accent" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">
                  {teamMode === "guided" ? "引导模式" : "自主模式"}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                {teamMode === "guided"
                  ? "由操作员引导每一步执行，适合复杂或高风险任务。"
                  : "Agent 自主决策执行顺序，适合明确且低风险的任务。"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Session 控制 */}
      {selectedSessionId && selectedSummary && (
        <div className="border-t border-border pt-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            选中 Session: {selectedSummary.role}
          </h4>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSessionPause}
              disabled={busy || controlsDisabled}
              className="btn btn-secondary min-h-9 px-3 text-xs"
            >
              <Pause className="h-3.5 w-3.5" />
              暂停
            </button>
            <button
              type="button"
              onClick={handleSessionResume}
              disabled={busy || controlsDisabled}
              className="btn btn-secondary min-h-9 px-3 text-xs"
            >
              <Play className="h-3.5 w-3.5" />
              恢复
            </button>
            <button
              type="button"
              onClick={() => setCancelDialogOpen(true)}
              disabled={busy || controlsDisabled}
              className="btn btn-destructive min-h-9 px-3 text-xs"
            >
              <Square className="h-3.5 w-3.5" />
              取消
            </button>
          </div>

          {/* Session 预算调整 */}
          <div className="mt-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Session 预算
              </span>
              {!sessionBudgetAdjusting ? (
                <button
                  type="button"
                  onClick={() => setSessionBudgetAdjusting(true)}
                  disabled={busy || controlsDisabled}
                  className="btn btn-ghost min-h-8 px-2 text-xs"
                >
                  <Settings2 className="h-3 w-3" />
                  调整
                </button>
              ) : null}
            </div>
            {sessionBudgetAdjusting && (
              <div className="mt-2">
                <BudgetAdjustForm
                  label="Session 预算 (Tokens)"
                  currentValue={
                    selectedSummary.budget_used_tokens ?? 0
                  }
                  onConfirm={handleSessionBudgetAdjust}
                  onCancel={() => setSessionBudgetAdjusting(false)}
                  busy={busy}
                />
              </div>
            )}
          </div>

          {/* 追加指令 */}
          <div className="mt-3 space-y-2">
            <label
              htmlFor="team-inspector-instruction"
              className="text-xs font-semibold text-foreground"
            >
              追加指令
            </label>
            <textarea
              id="team-inspector-instruction"
              value={instruction}
              onChange={(e) => {
                setInstruction(e.target.value);
                setInstructionNotice(null);
              }}
              rows={3}
              maxLength={8000}
              placeholder="输入纠偏或追加指令..."
              className="input-base w-full resize-none py-2 text-xs leading-5"
            />
            <button
              type="button"
              onClick={handleSendInstruction}
              disabled={
                busy || controlsDisabled || !instruction.trim()
              }
              className="btn btn-primary min-h-9 w-full px-3 text-xs"
            >
              <Send className="h-3.5 w-3.5" />
              发送指令
            </button>
            {instructionNotice && (
              <p
                role="status"
                className="text-[11px] font-medium text-success"
              >
                {instructionNotice}
              </p>
            )}
          </div>
        </div>
      )}

      {/* 停止确认对话框 */}
      <ConfirmDialog
        open={stopDialogOpen}
        title="停止团队"
        message={`停止后不可恢复，已注册的检查点会被保留。确定要停止团队「${container.name}」吗？`}
        confirmLabel="确认停止"
        onConfirm={handleStop}
        onCancel={() => setStopDialogOpen(false)}
        busy={busy}
      />

      {/* 取消 Session 确认对话框 */}
      <ConfirmDialog
        open={cancelDialogOpen}
        title="取消 Session"
        message={`取消后无法恢复，确定要取消「${selectedSummary?.role ?? ""}」吗？`}
        confirmLabel="确认取消"
        onConfirm={handleSessionCancel}
        onCancel={() => setCancelDialogOpen(false)}
        busy={busy}
      />
    </div>
  );
}

/* ── 主组件 ── */

export interface TeamInspectorProps {
  containerId: string;
  container: WorkContainer;
  sessions: WorkSessionSummary[];
  selectedSessionId: string | null;
  sseConnected: boolean;
  dataStale: boolean;
  onRefresh?: () => void;
}

export function TeamInspector({
  containerId,
  container,
  sessions,
  selectedSessionId,
  sseConnected,
  dataStale,
  onRefresh,
}: TeamInspectorProps) {
  const [progress, setProgress] = useState<TeamInspectorProgress | null>(null);
  const [usage, setUsage] = useState<TeamInspectorUsage | null>(null);
  const [progressLoading, setProgressLoading] = useState(true);
  const [usageLoading, setUsageLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [budgetNeedsResume, setBudgetNeedsResume] = useState(false);

  const loadData = useCallback(async () => {
    setProgressLoading(true);
    setUsageLoading(true);
    try {
      const [progressData, usageData] = await Promise.all([
        fetchTeamProgress(containerId),
        fetchTeamUsage(containerId),
      ]);
      setProgress(progressData);
      setUsage(usageData);

      // 检测预算耗尽后是否需要恢复
      if (
        usageData.tokens.max > 0 &&
        usageData.tokens.used >= usageData.tokens.max
      ) {
        setBudgetNeedsResume(true);
      } else {
        setBudgetNeedsResume(false);
      }
    } catch {
      // 保持旧数据或空态
    } finally {
      setProgressLoading(false);
      setUsageLoading(false);
    }
  }, [containerId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <aside
      className="flex min-h-0 flex-col overflow-y-auto border-l border-border bg-white/60"
      aria-label="团队检查器"
    >
      {/* 进度 - 默认展开 */}
      <CollapsibleSection
        title="进度"
        icon={<Gauge className="h-4 w-4 text-accent" />}
        defaultExpanded
      >
        <ProgressSection
          progress={progress}
          selectedSessionId={selectedSessionId}
          sessions={sessions}
          loading={progressLoading}
        />
      </CollapsibleSection>

      {/* 用量 - 默认折叠 */}
      <CollapsibleSection
        title="用量"
        icon={<BarChart3 className="h-4 w-4 text-accent" />}
        defaultExpanded={false}
        badge={
          usage ? (
            <HealthBadge health={usage.health} />
          ) : null
        }
      >
        <UsageSection usage={usage} loading={usageLoading} />
      </CollapsibleSection>

      {/* 控制 - 默认折叠 */}
      <CollapsibleSection
        title="控制"
        icon={<Settings2 className="h-4 w-4 text-accent" />}
        defaultExpanded={false}
      >
        <ControlSection
          container={container}
          containerId={containerId}
          selectedSessionId={selectedSessionId}
          sessions={sessions}
          sseConnected={sseConnected}
          dataStale={dataStale}
          usage={usage}
          budgetNeedsResume={budgetNeedsResume}
          onRefresh={loadData}
          busy={busy}
          setBusy={setBusy}
        />
      </CollapsibleSection>
    </aside>
  );
}
