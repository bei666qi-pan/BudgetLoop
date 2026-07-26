import { ArrowRight, Bot, Check, Clock3, Send, UserRound } from "lucide-react";
import { formatDateTime } from "@/lib/format";
import type { SessionTranscriptEntry } from "@/lib/types";

function EntryIcon({ entry }: { entry: SessionTranscriptEntry }) {
  if (entry.entry_type === "agent_output") return <Bot className="h-4 w-4" />;
  if (entry.entry_type === "handoff") return <ArrowRight className="h-4 w-4" />;
  return entry.author_type === "operator" ? <UserRound className="h-4 w-4" /> : <Send className="h-4 w-4" />;
}

export function SessionTranscript({ entries }: { entries: SessionTranscriptEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center px-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/8 text-accent">
          <Bot className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-sm font-semibold">这个 Session 还没有公开记录</h3>
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
          发送操作员消息，或从另一个 Session 创建明确的 Handoff。Agent 输出会在运行后显示在这里。
        </p>
      </div>
    );
  }

  return (
    <ol className="divide-y divide-border/80" aria-label="Session 对话记录">
      {entries.map((entry) => {
        const agent = entry.entry_type === "agent_output";
        const handoff = entry.entry_type === "handoff";
        return (
          <li key={entry.id} className="px-5 py-5 sm:px-6">
            <article className={handoff ? "rounded-xl border border-accent/25 bg-accent/[0.035] p-4" : ""}>
              <header className="flex items-start gap-3">
                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${agent ? "bg-accent/10 text-accent" : handoff ? "border border-accent/25 bg-white text-accent" : "bg-muted text-muted-foreground"}`}>
                  <EntryIcon entry={entry} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-sm font-semibold text-foreground">
                      {agent ? "Agent 输出" : entry.sender_role}
                    </span>
                    {handoff ? <span className="text-xs text-muted-foreground">→ {entry.recipient_role}</span> : null}
                    <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                      {formatDateTime(entry.created_at)}
                    </span>
                  </div>
                  {handoff ? (
                    <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10px] text-muted-foreground">
                      <span>{entry.id}</span>
                      <span className="flex items-center gap-1">
                        {entry.delivery_state === "delivered" ? <Check className="h-3 w-3 text-success" /> : <Clock3 className="h-3 w-3 text-warning" />}
                        {entry.delivery_state === "delivered" ? "已送达" : "已排队"}
                      </span>
                    </div>
                  ) : null}
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/90">{entry.content}</p>
                  {agent ? (
                    <p className="mt-2 text-[11px] text-muted-foreground">公开 Agent 输出 · 不包含隐藏推理</p>
                  ) : null}
                </div>
              </header>
            </article>
          </li>
        );
      })}
    </ol>
  );
}
