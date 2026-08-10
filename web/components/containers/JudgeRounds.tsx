"use client";

import {
  AlertTriangle,
  Check,
  CircleDashed,
  Gavel,
  LoaderCircle,
  MessageSquareReply,
  Play,
  ShieldCheck,
  X,
} from "lucide-react";
import { formatDateTime } from "@/lib/format";
import type { JudgeRound, JudgeState, TeamChatMessage, WorkSessionSummary } from "@/lib/types";

const GATE_LABELS: Record<string, string> = {
  required_roles_completed: "必要角色完成",
  message_confirmations: "消息确认与回复",
  evidence_verifiable: "证据可验证",
  workspace_compliant: "工作区合规",
  integration_published: "集成分支已发布",
  tests_passed: "声明测试通过",
  build_passed: "构建通过",
  target_artifacts_exist: "目标工件存在",
};

function StageLabel({ state, round }: { state: string | null | undefined; round: JudgeRound | null | undefined }) {
  const waiting = round?.pending_session_ids.length ?? 0;
  if (!round) return <><CircleDashed className="h-4 w-4" />等待首轮证据</>;
  if (state === "gating" || round.phase === "deterministic_gates") {
    return <><LoaderCircle className="h-4 w-4 animate-spin" />执行硬门禁</>;
  }
  if (state === "waiting_replies") {
    return <><MessageSquareReply className="h-4 w-4" />等待 {waiting} 个 Agent 确认/回复</>;
  }
  if (round.phase === "model_evaluation" && !round.verdict) {
    return <><LoaderCircle className="h-4 w-4 animate-spin" />模型正在评价</>;
  }
  if (round.status === "approved") return <><ShieldCheck className="h-4 w-4" />裁判已通过</>;
  if (round.status.startsWith("paused") || round.status === "blocked") {
    return <><AlertTriangle className="h-4 w-4" />裁判已暂停，等待人工恢复</>;
  }
  return <><CircleDashed className="h-4 w-4" />汇总 {round.evidence_refs.length} 份证据</>;
}

function CommunicationGroup({
  round,
  messages,
  sessions,
  judgeId,
}: {
  round: JudgeRound;
  messages: TeamChatMessage[];
  sessions: WorkSessionSummary[];
  judgeId: string | undefined;
}) {
  const byId = new Map(messages.map((item) => [item.id, item]));
  const feedback = round.feedback_message_ids.map((id) => byId.get(id)).filter(Boolean) as TeamChatMessage[];
  const startedAt = new Date(round.created_at).getTime();
  const replies = messages.filter((item) =>
    item.recipient_session_id === judgeId &&
    item.sender_session_id !== null &&
    new Date(item.created_at).getTime() >= startedAt,
  );
  const role = (id: string | null) => sessions.find((item) => item.id === id)?.role ?? "未知 Agent";
  if (feedback.length === 0 && replies.length === 0) return null;

  return (
    <div className="mt-3 grid gap-3 md:grid-cols-2" aria-label={`裁判第 ${round.sequence} 轮通信`}>
      <section className="rounded-lg border border-border bg-white p-3">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">裁判定向请求</h4>
        <div className="mt-2 space-y-2">
          {feedback.map((message) => (
            <div key={message.id} className="rounded-md bg-muted/55 p-2.5 text-xs">
              <div className="flex items-center justify-between gap-2 font-semibold">
                <span>汇总裁判 → {message.recipient_role ?? role(message.recipient_session_id)}</span>
                <span className="text-[10px] text-muted-foreground">{message.delivery_state}</span>
              </div>
              <p className="mt-1 line-clamp-3 leading-5 text-muted-foreground">{message.content}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="rounded-lg border border-border bg-white p-3">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Agent 确认与回复</h4>
        <div className="mt-2 space-y-2">
          {replies.length > 0 ? replies.map((message) => (
            <div key={message.id} className="rounded-md bg-success/5 p-2.5 text-xs">
              <div className="flex items-center justify-between gap-2 font-semibold">
                <span>{message.sender_role ?? role(message.sender_session_id)} → 汇总裁判</span>
                <span className="text-[10px] text-muted-foreground">{message.delivery_state}</span>
              </div>
              <p className="mt-1 line-clamp-3 leading-5 text-muted-foreground">{message.content}</p>
            </div>
          )) : (
            <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
              等待接收者真实确认并回复；不会以模拟状态代替。
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

export function JudgeRounds({
  judge,
  messages,
  sessions,
  loading,
  busy,
  onResume,
}: {
  judge: JudgeState | null;
  messages: TeamChatMessage[];
  sessions: WorkSessionSummary[];
  loading: boolean;
  busy: boolean;
  onResume: () => Promise<void>;
}) {
  if (loading && !judge) {
    return (
      <section className="border-b border-border bg-accent/[0.025] px-4 py-4 sm:px-6" aria-busy="true">
        <div className="flex items-center gap-2 text-sm font-semibold"><LoaderCircle className="h-4 w-4 animate-spin" />加载裁判数据库状态…</div>
        <p className="mt-1 text-xs text-muted-foreground">正在恢复轮次、门禁、消息送达和待回复项。</p>
      </section>
    );
  }
  if (!judge?.enabled) return null;
  const round = judge.current_round;
  const recoverable = round?.status === "blocked" || Boolean(round?.status.startsWith("paused"));

  return (
    <section className="max-h-[45dvh] shrink-0 overflow-y-auto border-b border-border bg-accent/[0.025] px-4 py-4 sm:px-6" aria-label="汇总裁判轮次">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent"><Gavel className="h-4 w-4" /></span>
            <div>
              <h2 className="text-sm font-semibold">汇总裁判{round ? ` · 第 ${round.sequence} 轮` : ""}</h2>
              <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground"><StageLabel state={judge.state} round={round} /></p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {round?.verdict ? (
            <span className={`badge ${round.verdict === "approve" ? "badge-success" : round.verdict === "blocked" ? "badge-critical" : "badge-warning"}`}>
              {round.verdict}
            </span>
          ) : null}
          {recoverable ? (
            <button type="button" onClick={() => void onResume()} disabled={busy} className="btn btn-secondary min-h-8 px-3 text-xs">
              <Play className="h-3.5 w-3.5" />恢复裁判
            </button>
          ) : null}
        </div>
      </div>

      {round ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {round.gates.map((gate) => (
              <div key={gate.id} title={gate.failure_reason ?? undefined} className={`flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] ${gate.passed ? "border-success/15 bg-success/5 text-success" : "border-critical/15 bg-critical/5 text-critical"}`}>
                {gate.passed ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                <span className="truncate">{GATE_LABELS[gate.gate_name] ?? gate.gate_name}</span>
              </div>
            ))}
          </div>
          {round.summary ? (
            <div className="mt-3 rounded-lg border border-border bg-white/80 p-3">
              <p className="text-[11px] font-semibold text-muted-foreground">模型评价摘要 / 确定性结论</p>
              <p className="mt-1 text-xs leading-5 text-foreground">{round.summary}</p>
              <p className="mt-1 text-[10px] text-muted-foreground">记录于 {formatDateTime(round.updated_at)} · 不展示隐藏推理或私有上下文</p>
            </div>
          ) : null}
          <CommunicationGroup round={round} messages={messages} sessions={sessions} judgeId={judge.session?.id} />
          {judge.rounds.length > 1 ? (
            <details className="mt-3 rounded-lg border border-border bg-white/70 px-3 py-2">
              <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
                查看此前 {judge.rounds.length - 1} 个裁判轮次
              </summary>
              <ol className="mt-2 space-y-2">
                {judge.rounds.slice(0, -1).reverse().map((item) => (
                  <li key={item.id} className="flex items-start justify-between gap-3 border-t border-border/70 pt-2 text-xs">
                    <span><strong className="text-foreground">第 {item.sequence} 轮 · {item.verdict ?? item.status}</strong><span className="mt-0.5 block text-muted-foreground">{item.summary ?? "无摘要"}</span></span>
                    <time className="shrink-0 text-[10px] text-muted-foreground">{formatDateTime(item.updated_at)}</time>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
