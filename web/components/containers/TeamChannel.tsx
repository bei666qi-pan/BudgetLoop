"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  Filter,
  Lock,
  MessageSquare,
  Send,
  Terminal,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatDateTime } from "@/lib/format";
import type {
  ContainerLifecycle,
  TeamChatMessage,
  TeamMessageType,
  WorkSessionSummary,
} from "@/lib/types";

/* ── 本地辅助类型 ── */

type ChannelFilter = "all" | string; // "all" = 团队频道, 其他为 session id

/* ── 状态标签 ── */

const DELIVERY_LABELS: Record<string, string> = {
  queued: "已排队",
  injected: "等待下次执行检查点",
  acknowledged: "已送达",
  failed: "送达失败",
  delivered: "已送达",
  recorded: "已记录",
};

const DELIVERY_CLASS: Record<string, string> = {
  queued: "badge-muted",
  injected: "badge-warning",
  acknowledged: "badge-success",
  failed: "badge-critical",
  delivered: "badge-success",
  recorded: "badge-info",
};

function deliveryLabel(state: string): string {
  return DELIVERY_LABELS[state] ?? state;
}

function deliveryClass(state: string): string {
  return DELIVERY_CLASS[state] ?? "badge-muted";
}

/* ── 消息类型图标 ── */

function MessageTypeIcon({ entryType }: { entryType: string }) {
  switch (entryType) {
    case "handoff":
      return <ArrowRight className="h-4 w-4" />;
    case "progress_update":
      return <ClipboardCheck className="h-4 w-4" />;
    case "system_fact":
      return <AlertTriangle className="h-4 w-4" />;
    default:
      return <MessageSquare className="h-4 w-4" />;
  }
}

/* ── Handoff 结构化渲染 ── */

function HandoffBody({ msg }: { msg: TeamChatMessage }) {
  let parsed: Record<string, unknown> = {};
  try {
    const value = JSON.parse(msg.content) as unknown;
    if (value && typeof value === "object" && !Array.isArray(value)) parsed = value as Record<string, unknown>;
  } catch { /* ordinary text handoff */ }
  const meta = { ...parsed, ...(msg.metadata ?? {}) };
  const conclusion = typeof meta.conclusion === "string" ? meta.conclusion : null;
  const evidence = typeof meta.evidence === "string"
    ? meta.evidence
    : Array.isArray(meta.evidence)
      ? meta.evidence.map(String).join("\n")
      : null;
  const openQuestions: string[] = Array.isArray(meta.open_questions)
    ? meta.open_questions.filter((q): q is string => typeof q === "string")
    : [];
  const nextStep = typeof meta.next_step === "string" ? meta.next_step : null;

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/20 bg-accent/[0.025] p-4">
      <div className="flex items-center gap-2 text-xs font-semibold text-accent">
        <ArrowRight className="h-4 w-4" />
        Handoff
        {msg.sender_role && msg.recipient_role ? (
          <span className="font-normal text-muted-foreground">
            {msg.sender_role} → {msg.recipient_role}
          </span>
        ) : null}
      </div>

      {conclusion ? (
        <section>
          <h4 className="text-[11px] font-semibold text-foreground">结论</h4>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-foreground/85">
            {conclusion}
          </p>
        </section>
      ) : null}

      {evidence ? (
        <section>
          <h4 className="text-[11px] font-semibold text-foreground">证据</h4>
          <p className="mt-1 whitespace-pre-wrap font-mono text-xs leading-5 text-muted-foreground">
            {evidence}
          </p>
        </section>
      ) : null}

      {openQuestions.length > 0 ? (
        <section>
          <h4 className="text-[11px] font-semibold text-foreground">未决问题</h4>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm leading-6 text-foreground/85">
            {openQuestions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {nextStep ? (
        <section>
          <h4 className="text-[11px] font-semibold text-foreground">下一步</h4>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-foreground/85">
            {nextStep}
          </p>
        </section>
      ) : null}

      {/* fallback: 无结构化字段时展示原始 content */}
      {!conclusion && !evidence && openQuestions.length === 0 && !nextStep && msg.content ? (
        <p className="whitespace-pre-wrap text-sm leading-6 text-foreground/80">
          {msg.content}
        </p>
      ) : null}
    </div>
  );
}

/* ── Progress Update 渲染 ── */

function ProgressUpdateBody({ msg }: { msg: TeamChatMessage }) {
  const meta = msg.metadata ?? {};
  const summary = typeof meta.summary === "string" ? meta.summary : null;
  const milestone = typeof meta.milestone === "string" ? meta.milestone : null;
  const completedItems =
    typeof meta.completed_items === "number"
      ? meta.completed_items
      : typeof meta.completed_items === "string"
        ? parseInt(meta.completed_items, 10)
        : null;
  const nextStep = typeof meta.next_step === "string" ? meta.next_step : null;
  const blocked = meta.blocked === true || meta.blocked === "true";

  return (
    <div
      className={`mt-3 rounded-lg border p-4 ${
        blocked
          ? "border-critical/20 bg-critical/[0.03]"
          : "border-warning/15 bg-warning/[0.02]"
      }`}
    >
      <div className="flex items-center gap-2">
        <ClipboardCheck className="h-4 w-4 text-info" />
        <span className="text-xs font-semibold text-foreground">进度更新</span>
        {blocked ? (
          <span className="badge badge-critical ml-auto text-[10px]">阻塞</span>
        ) : null}
        {milestone ? (
          <span className="badge badge-info ml-auto text-[10px]">{milestone}</span>
        ) : null}
      </div>

      {summary ? (
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/85">
          {summary}
        </p>
      ) : null}

      {completedItems !== null && Number.isFinite(completedItems) ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Check className="h-3.5 w-3.5 text-success" />
          已完成 {completedItems} 项
        </p>
      ) : null}

      {nextStep ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">下一步：</span>
          {nextStep}
        </p>
      ) : null}

      {!summary && completedItems === null && !nextStep && msg.content ? (
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/80">
          {msg.content}
        </p>
      ) : null}
    </div>
  );
}

/* ── 单条消息气泡 ── */

function MessageBubble({ msg }: { msg: TeamChatMessage }) {
  const isHandoff = msg.entry_type === "handoff";
  const isProgress = msg.entry_type === "progress_update";
  const isSystem = msg.entry_type === "system_fact";

  return (
    <article
      className={`px-5 py-4 sm:px-6 ${
        isSystem
          ? "border-l-2 border-warning bg-warning/[0.03]"
          : isHandoff
            ? "border-l-2 border-accent/30 bg-accent/[0.015]"
            : ""
      }`}
    >
      {/* header */}
      <div className="flex items-start gap-3">
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
            isSystem
              ? "bg-warning/10 text-warning"
              : isHandoff
                ? "bg-accent/10 text-accent"
                : isProgress
                  ? "bg-info/10 text-info"
                  : "bg-muted text-muted-foreground"
          }`}
        >
          <MessageTypeIcon entryType={msg.entry_type} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-sm font-semibold text-foreground">
              {msg.sender_role || msg.author_type}
            </span>

            {isHandoff && msg.recipient_role ? (
              <span className="text-xs text-muted-foreground">
                → {msg.recipient_role}
              </span>
            ) : null}

            <span
              className={`badge ml-auto shrink-0 text-[10px] ${deliveryClass(msg.delivery_state)}`}
            >
              {deliveryLabel(msg.delivery_state)}
            </span>

            <span className="font-mono text-[11px] text-muted-foreground">
              {formatDateTime(msg.created_at)}
            </span>
          </div>

          {/* body */}
          {isHandoff ? (
            <HandoffBody msg={msg} />
          ) : isProgress ? (
            <ProgressUpdateBody msg={msg} />
          ) : isSystem ? (
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/90">
              {msg.content}
            </p>
          ) : (
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/90">
              {msg.content}
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

/* ── 聊天输入区 ── */

const MESSAGE_TYPE_OPTIONS: { value: TeamMessageType; label: string }[] = [
  { value: "message", label: "消息" },
  { value: "handoff", label: "Handoff" },
  { value: "progress_update", label: "进度" },
  { value: "system_fact", label: "系统" },
];

function ChatComposer({
  sessions,
  selectedSessionId,
  disabled,
  cliEngine,
  onSend,
}: {
  sessions: WorkSessionSummary[];
  selectedSessionId: string | null;
  disabled: boolean;
  cliEngine: boolean;
  onSend: (
    kind: TeamMessageType,
    content: string,
    targetSessionId: string,
  ) => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [targetSessionId, setTargetSessionId] = useState(
    selectedSessionId ?? sessions[0]?.id ?? "",
  );
  const [messageType, setMessageType] = useState<TeamMessageType>("message");
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (selectedSessionId && sessions.some((s) => s.id === selectedSessionId)) {
      setTargetSessionId(selectedSessionId);
    }
  }, [selectedSessionId, sessions]);

  async function handleSend() {
    const clean = content.trim();
    if (!clean || !targetSessionId) return;
    setSending(true);
    try {
      await onSend(messageType, clean, targetSessionId);
      setContent("");
      if (messageType === "handoff") {
        setNotice("Handoff 已提交；送达状态会在收件箱中更新。");
      } else {
        setNotice("消息已提交；送达状态会在对话中更新。");
      }
    } catch {
      setNotice("发送失败，请重试。");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <div className="border-t border-border bg-white px-4 py-3 sm:px-6">
      {/* session 选择 & 消息类型 */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          @目标
          <select
            value={targetSessionId}
            onChange={(e) => setTargetSessionId(e.target.value)}
            disabled={disabled || sessions.length === 0}
            className="min-h-9 rounded-lg border border-border bg-white px-3 text-xs font-semibold text-foreground"
          >
            {sessions.length === 0 ? (
              <option value="">无可用 Session</option>
            ) : null}
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.role}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          类型
          <select
            value={messageType}
            onChange={(e) => setMessageType(e.target.value as TeamMessageType)}
            disabled={disabled}
            className="min-h-9 rounded-lg border border-border bg-white px-3 text-xs font-semibold text-foreground"
          >
            {MESSAGE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* handoff 指引 */}
      {messageType === "handoff" ? (
        <p className="mt-2 text-[11px] leading-relaxed text-warning">
          Handoff 只包含结论、证据、未决问题和接收方下一步。
        </p>
      ) : null}

      {/* 输入区域 */}
      <textarea
        ref={textareaRef}
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          setNotice(null);
        }}
        onKeyDown={handleKeyDown}
        rows={messageType === "handoff" ? 4 : 2}
        maxLength={8000}
        placeholder={
          disabled
            ? "团队已暂停，无法发送消息。"
            : messageType === "handoff"
              ? "结论：\n\n证据：\n\n未决问题：\n\n下一步："
              : "输入消息…"
        }
        disabled={disabled}
        className="input-base mt-2 min-h-0 w-full resize-none py-2 leading-5"
      />

      {/* 底部操作栏 */}
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          {cliEngine ? (
            <span className="flex items-center gap-1 text-amber-600">
              <Terminal className="h-3 w-3" />
              CLI 引擎: 消息在安全检查点注入
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <ChevronDown className="h-3 w-3" />
              ⌘+Enter 发送
            </span>
          )}
        </span>

        <button
          type="button"
          onClick={() => void handleSend()}
          disabled={disabled || sending || !content.trim() || !targetSessionId}
          className="btn btn-primary min-h-9 px-4 text-xs"
        >
          <Send className="h-4 w-4" />
          发送
        </button>
      </div>

      {notice ? (
        <p
          role="status"
          className={`mt-2 text-[11px] font-medium ${
            notice.includes("失败") ? "text-critical" : "text-success"
          }`}
        >
          {notice}
        </p>
      ) : null}
    </div>
  );
}

/* ── 主组件 ── */

export function TeamChannel({
  messages,
  sessions,
  containerLifecycle,
  selectedSessionId,
  onSelectSession,
  onSendMessage,
}: {
  messages: TeamChatMessage[];
  sessions: WorkSessionSummary[];
  containerLifecycle: ContainerLifecycle;
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
  onSendMessage: (
    kind: TeamMessageType,
    content: string,
    targetSessionId: string,
  ) => Promise<void>;
}) {
  const [filter, setFilter] = useState<ChannelFilter>(
    selectedSessionId ?? "all",
  );

  // 同步外部 session 选中到 filter
  useEffect(() => {
    setFilter(selectedSessionId ?? "all");
  }, [selectedSessionId]);

  const isPaused = containerLifecycle === "paused";

  // 去重 & 排序 & 过滤
  const displayMessages = useMemo(() => {
    const deduped: TeamChatMessage[] = [];
    const localSeen = new Set<string>();

    for (const msg of messages) {
      const key = msg.idempotency_key ?? msg.id;
      if (localSeen.has(key)) continue;
      localSeen.add(key);
      deduped.push(msg);
    }

    // 按时间排序（最新在上）
    deduped.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );

    // 过滤
    if (filter === "all") return deduped;
    return deduped.filter(
      (msg) =>
        msg.sender_session_id === filter ||
        msg.recipient_session_id === filter,
    );
  }, [messages, filter]);

  // 判断选中的 session 是否为 CLI 引擎
  const selectedSession = useMemo(
    () => sessions.find((s) => s.id === selectedSessionId),
    [sessions, selectedSessionId],
  );
  const cliEngine = useMemo(() => {
    if (!selectedSession) return false;
    const meta = selectedSession as unknown as Record<string, unknown>;
    const engine = typeof meta.execution_engine === "string" ? meta.execution_engine : null;
    return engine === "codex" || engine === "gemini-cli" || engine === "opencode";
  }, [selectedSession]);

  const toggleFilter = useCallback(() => {
    setFilter((prev) => {
      if (prev === "all" && selectedSessionId) return selectedSessionId;
      return "all";
    });
  }, [selectedSessionId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col" aria-label="团队频道">
      {/* filter bar */}
      <div className="flex min-h-12 items-center justify-between border-b border-border px-4 sm:px-6">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          {filter === "all" ? "团队频道" : "会话对话"}
        </h2>
        <div className="flex items-center gap-2">
          {isPaused ? (
            <span className="flex items-center gap-1 text-[11px] font-medium text-warning">
              <Lock className="h-3.5 w-3.5" />
              已暂停
            </span>
          ) : null}
          <button
            type="button"
            onClick={toggleFilter}
            disabled={!selectedSessionId}
            className={`btn-ghost flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${
              filter !== "all"
                ? "text-accent"
                : "text-muted-foreground"
            }`}
          >
            <Filter className="h-3.5 w-3.5" />
            {filter === "all" ? "全部消息" : "仅此会话"}
          </button>
        </div>
      </div>

      {/* message stream */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {displayMessages.length === 0 ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center px-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
              <MessageSquare className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-foreground">
              暂无消息
            </h3>
            <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
              {filter === "all"
                ? "团队频道中还没有消息，使用下方输入框开始对话。"
                : "当前会话还没有消息记录。"}
            </p>
          </div>
        ) : (
          <ol className="divide-y divide-border/80" aria-label="团队消息流">
            {displayMessages.map((msg) => (
              <li key={msg.id}>
                <MessageBubble msg={msg} />
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* chat composer */}
      <ChatComposer
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        disabled={isPaused}
        cliEngine={cliEngine}
        onSend={onSendMessage}
      />
    </div>
  );
}
