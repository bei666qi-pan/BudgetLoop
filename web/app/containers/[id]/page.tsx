"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  Clock3,
  Pause,
  Play,
  Plus,
  RefreshCw,
  StopCircle,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CreateSessionDialog } from "@/components/containers/CreateSessionDialog";
import { SessionRail } from "@/components/containers/SessionRail";
import { TeamChannel } from "@/components/containers/TeamChannel";
import { TeamInspector } from "@/components/containers/TeamInspector";
import {
  CONTAINER_LIFECYCLE_LABELS,
  lifecycleTone,
} from "@/lib/container-presentation";
import {
  apiFetch,
  cancelSession,
  fetchTeamProgress,
  fetchTeamUsage,
  idempotencyKey,
  pauseContainer,
  pauseSession as apiPauseSession,
  resumeContainer,
  stopContainer,
} from "@/lib/api";
import {
  formatCost,
  formatDurationSec,
  formatTokens,
} from "@/lib/format";
import {
  CONNECTION_STATUS_LABELS,
  TEAM_STATUS_LABELS,
} from "@/lib/types";
import type {
  ConnectionState,
  CreateWorkSessionRequest,
  TeamAlert,
  TeamChatMessage,
  TeamMessageType,
  TeamObservatoryResponse,
  TeamStatus,
  TeamStreamEvent,
  TeamUsageSummary,
  WorkContainer,
  WorkSessionSummary,
} from "@/lib/types";

/* ── Mobile tab type ── */
type MobileTab = "sessions" | "conversation" | "control";

/* ── Connection state helpers ── */
const CONNECTION_DOT: Record<ConnectionState, string> = {
  connected: "bg-success",
  stale: "bg-warning",
  disconnected: "bg-critical",
};

const TEAM_STATUS_TONE: Record<TeamStatus, string> = {
  active: "badge-success",
  paused: "badge-warning",
  blocked: "badge-critical",
  completed: "badge-muted",
};

/* ── Skeleton loader ── */
function DashboardSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1536px] animate-in px-0 py-5 sm:px-6 sm:py-7" aria-busy="true">
      <div className="px-4 sm:px-0 space-y-5">
        <div className="skeleton h-4 w-28" />
        <div className="skeleton h-8 w-72" />
        <div className="skeleton h-5 w-96 max-w-full" />
        <div className="skeleton h-12 w-full rounded-xl" />
        <div className="skeleton h-[680px] rounded-xl" />
      </div>
    </div>
  );
}

/* ── Connection indicator ── */
function ConnectionDot({ state }: { state: ConnectionState }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <span className={`inline-block h-2 w-2 rounded-full ${CONNECTION_DOT[state]}`} />
      <span className={
        state === "connected" ? "text-muted-foreground" :
        state === "stale" ? "text-warning" : "text-critical"
      }>
        {CONNECTION_STATUS_LABELS[state]}
      </span>
    </span>
  );
}

/* ── Top bar ── */
function TopBar({
  teamStatus,
  phaseLabel,
  usage,
  connection,
  activeCount,
  totalCount,
  busy,
  onPause,
  onResume,
  onStop,
}: {
  teamStatus: TeamStatus;
  phaseLabel: string | null;
  usage: TeamUsageSummary | null;
  connection: ConnectionState;
  activeCount: number;
  totalCount: number;
  busy: boolean;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}) {
  return (
    <div className="surface px-4 py-3 sm:px-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-wrap">
        <div className="flex flex-wrap items-center gap-3 min-w-0">
          <span className={TEAM_STATUS_TONE[teamStatus]}>
            {TEAM_STATUS_LABELS[teamStatus]}
          </span>
          {phaseLabel ? (
            <span className="text-xs text-muted-foreground">
              阶段: <span className="font-semibold text-foreground">{phaseLabel}</span>
            </span>
          ) : null}
          {usage ? (
            <>
              <span className="tabular-nums text-xs text-muted-foreground">
                Tok <span className="font-semibold text-foreground">{formatTokens(usage.total_tokens)}</span>
                <span className="hidden sm:inline">/{formatTokens(usage.max_tokens)}</span>
              </span>
              <span className="tabular-nums text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{formatCost(usage.total_cost, "未上报")}</span>
                <span className="hidden sm:inline">/{formatCost(usage.max_cost, "未上报")}</span>
              </span>
              <span className="tabular-nums text-xs text-muted-foreground">
                <Clock3 className="inline h-3 w-3 mr-1" />
                <span className="font-semibold text-foreground">{formatDurationSec(usage.elapsed_seconds)}</span>
              </span>
            </>
          ) : null}
          <span className="text-xs text-muted-foreground">
            {activeCount}/{totalCount} 运行中
          </span>
        </div>
        <div className="flex items-center gap-3 sm:ml-auto">
          <ConnectionDot state={connection} />
          <div className="flex gap-1.5">
            {teamStatus === "active" ? (
              <button
                type="button"
                onClick={onPause}
                disabled={busy}
                className="btn btn-secondary min-h-8 px-3 text-xs"
              >
                <Pause className="h-3.5 w-3.5" />暂停
              </button>
            ) : null}
            {teamStatus === "paused" ? (
              <button
                type="button"
                onClick={onResume}
                disabled={busy}
                className="btn btn-primary min-h-8 px-3 text-xs"
              >
                <Play className="h-3.5 w-3.5" />恢复
              </button>
            ) : null}
            {(teamStatus === "active" || teamStatus === "paused") ? (
              <button
                type="button"
                onClick={onStop}
                disabled={busy}
                className="btn btn-ghost min-h-8 px-3 text-xs text-critical hover:bg-critical/10"
              >
                <StopCircle className="h-3.5 w-3.5" />停止
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Alert banner (cross-tab) ── */
function AlertBanner({ alerts }: { alerts: TeamAlert[] }) {
  if (alerts.length === 0) return null;

  const blockingCount = alerts.filter((a) => a.kind === "blocking").length;
  const approvalCount = alerts.filter((a) => a.kind === "approval").length;
  const overspendCount = alerts.filter((a) => a.kind === "overspend" || a.kind === "budget_exhausted").length;

  const parts: string[] = [];
  if (blockingCount > 0) parts.push(`${blockingCount} 个阻塞`);
  if (approvalCount > 0) parts.push(`${approvalCount} 个待审批`);
  if (overspendCount > 0) parts.push(`${overspendCount} 个超支`);

  return (
    <div role="alert" className="mx-4 mt-4 rounded-lg border border-critical/20 bg-critical/5 px-4 py-3 sm:mx-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-critical">
            <AlertCircle className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            {parts.join(" · ")}
            {parts.length === 0 && alerts.length > 0 ? `${alerts.length} 条告警` : null}
            {" · 需处理"}
          </p>
          <ul className="mt-1.5 space-y-0.5">
            {alerts.slice(0, 3).map((alert, i) => (
              <li key={i} className="text-xs text-critical/80 truncate">
                {alert.session_role ? `${alert.session_role}: ` : ""}{alert.message}
              </li>
            ))}
            {alerts.length > 3 ? (
              <li className="text-xs text-muted-foreground">还有 {alerts.length - 3} 条告警…</li>
            ) : null}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ── Custom hook: SSE + polling + connection state ── */
function useTeamStream(containerId: string, isMobile: boolean, onEvent: (event: TeamStreamEvent) => void) {
  const [connection, setConnection] = useState<ConnectionState>("connected");
  const lastSeqRef = useRef<number>(0);
  const staleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disconnectedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const clearTimers = useCallback(() => {
    if (staleTimerRef.current) { clearTimeout(staleTimerRef.current); staleTimerRef.current = null; }
    if (disconnectedTimerRef.current) { clearTimeout(disconnectedTimerRef.current); disconnectedTimerRef.current = null; }
  }, []);

  const resetConnectionTimers = useCallback(() => {
    setConnection("connected");
    clearTimers();
    staleTimerRef.current = setTimeout(() => {
      setConnection("stale");
    }, 10_000);
    disconnectedTimerRef.current = setTimeout(() => {
      setConnection("disconnected");
    }, 30_000);
  }, [clearTimers]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
  }, []);

  const startPolling = useCallback((interval: number) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `/api/control/api/work-containers/${containerId}/stream?after_seq=${lastSeqRef.current}`,
          {
            headers: lastSeqRef.current > 0
              ? { "Last-Event-ID": String(lastSeqRef.current) }
              : {},
            cache: "no-store",
          },
        );
        if (res.ok) {
          const data: TeamStreamEvent[] = await res.json();
          if (Array.isArray(data)) {
            for (const event of data) {
              if (event.seq > lastSeqRef.current) {
                lastSeqRef.current = event.seq;
                onEventRef.current(event);
              }
            }
          }
          resetConnectionTimers();
        }
      } catch {
        // polling failed, keep last state
      }
    }, interval);
  }, [containerId, resetConnectionTimers, stopPolling]);

  // SSE on desktop, polling only on mobile
  useEffect(() => {
    if (isMobile) {
      startPolling(5_000);
      return () => { stopPolling(); clearTimers(); };
    }

    // Desktop: SSE
    const es = new EventSource(`/api/control/api/work-containers/${containerId}/stream`);
    resetConnectionTimers();

    es.onmessage = (event) => {
      try {
        const parsed: TeamStreamEvent = JSON.parse(event.data);
        if (parsed.seq > lastSeqRef.current) {
          lastSeqRef.current = parsed.seq;
          onEventRef.current(parsed);
        }
      } catch { /* ignore malformed events */ }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        clearTimers();
        setConnection("disconnected");
        startPolling(3_000);
      }
    };

    es.onopen = () => {
      stopPolling();
      resetConnectionTimers();
    };

    return () => {
      es.close();
      stopPolling();
      clearTimers();
    };
  }, [containerId, isMobile, resetConnectionTimers, clearTimers, startPolling, stopPolling]);

  // Mobile: visibilitychange pause/resume
  useEffect(() => {
    if (!isMobile) return;
    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling(5_000);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [isMobile, startPolling, stopPolling]);

  return { connection };
}

/* ── Main dashboard component ── */
export default function TeamObservatoryDashboard() {
  const { id } = useParams<{ id: string }>();
  const [container, setContainer] = useState<WorkContainer | null>(null);
  const [observatory, setObservatory] = useState<TeamObservatoryResponse | null>(null);
  const [channelMessages, setChannelMessages] = useState<TeamChatMessage[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>("conversation");
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile breakpoint
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1280);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // SSE event handler
  const handleStreamEvent = useCallback((event: TeamStreamEvent) => {
    if (event.type === "session_message" && event.payload) {
      const msg = event.payload as unknown as TeamChatMessage;
      setChannelMessages((prev) => [...prev, msg]);
    }
  }, []);

  // SSE / polling
  const { connection } = useTeamStream(id, isMobile, handleStreamEvent);

  // Load container
  const loadContainer = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const data = await apiFetch<WorkContainer>(`/api/work-containers/${id}`);
      setContainer(data);
      setSelectedId((current) =>
        current && data.sessions.some((item) => item.id === current)
          ? current
          : data.sessions[0]?.id ?? null,
      );
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载工作容器。");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [id]);

  // Load observatory data
  const loadObservatory = useCallback(async () => {
    try {
      const data = await apiFetch<TeamObservatoryResponse>(`/api/work-containers/${id}`);
      setObservatory(data);
    } catch {
      // observatory data is best-effort
    }
  }, [id]);

  // Initial load
  useEffect(() => { void loadContainer(); }, [loadContainer]);

  // Poll for observatory data + container refresh
  useEffect(() => {
    void loadObservatory();
    const timer = window.setInterval(() => {
      void Promise.all([loadObservatory(), loadContainer(true)]);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [loadContainer, loadObservatory]);

  // Open dialog via custom event
  useEffect(() => {
    const open = () => setDialogOpen(true);
    window.addEventListener("budgetloop:new-session", open);
    return () => window.removeEventListener("budgetloop:new-session", open);
  }, []);

  const selectedSummary = useMemo(
    () => container?.sessions.find((item) => item.id === selectedId) ?? null,
    [container, selectedId],
  );

  // Actions
  async function createSession(body: CreateWorkSessionRequest) {
    setBusy(true);
    setActionError(null);
    try {
      const response = await apiFetch<{ session: WorkSessionSummary }>(
        `/api/work-containers/${id}/sessions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey() },
          body: JSON.stringify(body),
        },
      );
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

  async function sendMessage(
    kind: TeamMessageType,
    content: string,
    targetSessionId: string,
  ) {
    setBusy(true);
    setActionError(null);
    try {
      await apiFetch(`/api/work-containers/${id}/sessions/${targetSessionId}/messages`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          message_type: kind,
          content,
        }),
      });
      await loadContainer(true);
    } catch (sendError) {
      setActionError(sendError instanceof Error ? sendError.message : "消息发送失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handlePauseContainer() {
    setBusy(true);
    try {
      await pauseContainer(id);
      await Promise.all([loadContainer(true), loadObservatory()]);
    } catch (pauseError) {
      setActionError(pauseError instanceof Error ? pauseError.message : "暂停失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleResumeContainer() {
    setBusy(true);
    try {
      await resumeContainer(id);
      await Promise.all([loadContainer(true), loadObservatory()]);
    } catch (resumeError) {
      setActionError(resumeError instanceof Error ? resumeError.message : "恢复失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleStopContainer() {
    if (!confirm("确定要停止团队运行？此操作不可撤销。")) return;
    setBusy(true);
    try {
      await stopContainer(id);
      await Promise.all([loadContainer(true), loadObservatory()]);
    } catch (stopError) {
      setActionError(stopError instanceof Error ? stopError.message : "停止失败。");
    } finally {
      setBusy(false);
    }
  }

  // Derive team status
  const teamStatus: TeamStatus = observatory?.team_status ?? (
    container?.lifecycle_state === "active" ? "active" :
    container?.lifecycle_state === "paused" ? "paused" :
    container?.lifecycle_state === "completed" ? "completed" : "active"
  );

  const phaseLabel = observatory?.phase?.current_phase ?? null;
  const alerts = observatory?.alerts ?? [];
  const usage = observatory?.usage ?? null;

  // Loading
  if (loading) return <DashboardSkeleton />;

  // Error
  if (error || !container) {
    return (
      <div className="page-shell">
        <section role="alert" className="surface flex flex-col items-center px-6 py-16 text-center">
          <AlertCircle className="h-9 w-9 text-critical" />
          <h1 className="mt-4 text-xl font-semibold">团队观测台无法打开</h1>
          <p className="mt-2 max-w-lg text-sm text-muted-foreground">
            {error ?? "容器不存在。"}
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/containers" className="btn btn-secondary">
              <ArrowLeft className="h-4 w-4" />Agent Team
            </Link>
            <button onClick={() => void loadContainer()} className="btn btn-primary">
              <RefreshCw className="h-4 w-4" />重试
            </button>
          </div>
        </section>
      </div>
    );
  }

  // Empty state: no sessions
  if (container.sessions.length === 0) {
    return (
      <div className="mx-auto w-full max-w-[1536px] animate-in px-0 py-5 sm:px-6 sm:py-7">
        <div className="px-4 sm:px-0">
          <Link href="/containers" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />Agent Team
          </Link>
          <h1 className="page-heading mt-5">{container.name}</h1>
        </div>
        <section className="mx-4 mt-6 flex min-h-[520px] flex-col items-center justify-center rounded-xl border border-border bg-white/85 px-6 text-center sm:mx-0">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <UsersRound className="h-7 w-7" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">此团队暂无活动 Session</h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
            每个 Session 都有独立目标、私有上下文、对话、运行状态与硬预算。只有共享上下文和明确 Handoff 会跨越边界。
          </p>
          <button onClick={() => setDialogOpen(true)} className="btn btn-primary mt-6">
            <Plus className="h-4 w-4" />新建 Session
          </button>
        </section>
        <CreateSessionDialog
          open={dialogOpen}
          defaultWorktree={container.default_workspace_policy === "worktree"}
          busy={busy}
          error={actionError}
          onClose={() => { if (!busy) setDialogOpen(false); }}
          onCreate={createSession}
        />
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="mx-auto w-full max-w-[1536px] animate-in px-0 py-5 sm:px-6 sm:py-7">
      {/* Header */}
      <div className="px-4 sm:px-0">
        <Link href="/containers" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />Agent Team
        </Link>
        <header className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="page-heading">{container.name}</h1>
              <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset ${lifecycleTone(container.lifecycle_state)}`}>
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {CONTAINER_LIFECYCLE_LABELS[container.lifecycle_state]}
              </span>
            </div>
            <p className="page-subtitle max-w-3xl">{container.project_goal}</p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-2">
              <UsersRound className="h-4 w-4" />{container.counts.sessions} 个 Session
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-success" />{container.counts.running} 运行中
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-critical" />{container.counts.attention} 需关注
            </span>
          </div>
        </header>
      </div>

      {/* Action error */}
      {actionError ? (
        <div role="alert" className="mx-4 mt-5 flex items-start justify-between gap-3 rounded-lg border border-critical/20 bg-critical/5 px-4 py-3 text-sm text-critical sm:mx-0">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="font-semibold">关闭</button>
        </div>
      ) : null}

      {/* Top bar */}
      <div className="mx-4 mt-5 sm:mx-0">
        <TopBar
          teamStatus={teamStatus}
          phaseLabel={phaseLabel}
          usage={usage}
          connection={connection}
          activeCount={container.counts.running}
          totalCount={container.counts.sessions}
          busy={busy}
          onPause={() => void handlePauseContainer()}
          onResume={() => void handleResumeContainer()}
          onStop={() => void handleStopContainer()}
        />
      </div>

      {/* Cross-tab alerts */}
      <AlertBanner alerts={alerts} />

      {/* Mobile tab bar */}
      <div className="mx-4 mt-5 flex rounded-lg border border-border bg-white p-1 xl:hidden" role="tablist" aria-label="观测台区域">
        {([
          { key: "sessions" as const, label: "成员" },
          { key: "conversation" as const, label: "对话" },
          { key: "control" as const, label: "控制" },
        ]).map((tab) => (
          <button
            key={tab.key}
            id={`obs-tab-${tab.key}`}
            role="tab"
            aria-controls={`obs-panel-${tab.key}`}
            aria-selected={mobileTab === tab.key}
            onClick={() => setMobileTab(tab.key)}
            className={`min-h-9 flex-1 rounded-md text-sm font-semibold ${
              mobileTab === tab.key ? "bg-muted text-accent" : "text-muted-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Desktop 3-panel grid */}
      <section
        className="mx-0 mt-4 hidden min-h-[680px] overflow-hidden border-y border-border bg-white/85 shadow-surface sm:mx-0 sm:mt-6 sm:rounded-xl sm:border xl:grid xl:h-[calc(100dvh-340px)] xl:min-h-0 xl:grid-cols-[288px_1fr_320px]"
        aria-label="团队观测台三栏布局"
      >
        {/* Left: SessionRail */}
        <div id="obs-panel-sessions" role="tabpanel" aria-labelledby="obs-tab-sessions" className="hidden xl:flex xl:min-h-0">
          <SessionRail
            sessions={container.sessions}
            selectedId={selectedId}
            onSelect={(sessionId) => { setSelectedId(sessionId); }}
            onAdd={() => setDialogOpen(true)}
          />
        </div>

        {/* Center: TeamChannel */}
        <div id="obs-panel-conversation" role="tabpanel" aria-labelledby="obs-tab-conversation" className="hidden xl:flex xl:min-h-0 xl:min-w-0 xl:overflow-hidden">
          <TeamChannel
            messages={channelMessages}
            sessions={container.sessions}
            containerLifecycle={container.lifecycle_state}
            selectedSessionId={selectedId}
            onSelectSession={(sessionId) => setSelectedId(sessionId)}
            onSendMessage={sendMessage}
          />
        </div>

        {/* Right: TeamInspector */}
        <div id="obs-panel-control" role="tabpanel" aria-labelledby="obs-tab-control" className="hidden xl:block xl:min-h-0">
          <TeamInspector
            containerId={id}
            container={container}
            sessions={container.sessions}
            selectedSessionId={selectedId}
            sseConnected={connection === "connected"}
            dataStale={connection !== "connected"}
          />
        </div>
      </section>

      {/* Mobile tab panels */}
      <section className="xl:hidden mx-0 mt-4 min-h-[620px] overflow-hidden border-y border-border bg-white/85 shadow-surface sm:mx-0 sm:mt-6 sm:rounded-xl sm:border">
        {/* Sessions tab */}
        <div
          id="obs-panel-sessions"
          role="tabpanel"
          aria-labelledby="obs-tab-sessions"
          className={mobileTab === "sessions" ? "flex min-h-[620px]" : "hidden"}
        >
          <SessionRail
            sessions={container.sessions}
            selectedId={selectedId}
            onSelect={(sessionId) => { setSelectedId(sessionId); setMobileTab("conversation"); }}
            onAdd={() => setDialogOpen(true)}
          />
        </div>

        {/* Conversation tab */}
        <div
          id="obs-panel-conversation"
          role="tabpanel"
          aria-labelledby="obs-tab-conversation"
          className={mobileTab === "conversation" ? "flex min-h-[620px] min-w-0 flex-col" : "hidden"}
        >
          <TeamChannel
            messages={channelMessages}
            sessions={container.sessions}
            containerLifecycle={container.lifecycle_state}
            selectedSessionId={selectedId}
            onSelectSession={(sessionId) => setSelectedId(sessionId)}
            onSendMessage={sendMessage}
          />
        </div>

        {/* Control tab */}
        <div
          id="obs-panel-control"
          role="tabpanel"
          aria-labelledby="obs-tab-control"
          className={mobileTab === "control" ? "block min-h-[620px]" : "hidden"}
        >
          <TeamInspector
            containerId={id}
            container={container}
            sessions={container.sessions}
            selectedSessionId={selectedId}
            sseConnected={connection === "connected"}
            dataStale={connection !== "connected"}
          />
        </div>
      </section>

      {/* Create session dialog */}
      <CreateSessionDialog
        open={dialogOpen}
        defaultWorktree={container.default_workspace_policy === "worktree"}
        busy={busy}
        error={actionError}
        onClose={() => { if (!busy) setDialogOpen(false); }}
        onCreate={createSession}
      />
    </div>
  );
}
