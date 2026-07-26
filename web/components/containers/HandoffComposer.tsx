"use client";

import { ArrowRight, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { availableHandoffRecipients } from "@/lib/container-presentation";
import type { MessageKind, WorkSessionSummary } from "@/lib/types";

export function HandoffComposer({
  selected,
  sessions,
  busy,
  onSend,
}: {
  selected: WorkSessionSummary;
  sessions: WorkSessionSummary[];
  busy: boolean;
  onSend: (kind: MessageKind, content: string, recipientId: string) => Promise<void>;
}) {
  const recipients = useMemo(
    () => availableHandoffRecipients(sessions, selected.id),
    [sessions, selected.id],
  );
  const [content, setContent] = useState("");
  const [recipientId, setRecipientId] = useState(recipients[0]?.id ?? "");
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!recipients.some((session) => session.id === recipientId)) {
      setRecipientId(recipients[0]?.id ?? "");
    }
  }, [recipientId, recipients]);

  async function submit(kind: MessageKind) {
    const clean = content.trim();
    if (!clean) return;
    const target = kind === "message" ? selected.id : recipientId;
    if (!target) return;
    await onSend(kind, clean, target);
    setContent("");
    setNotice(kind === "handoff" ? "Handoff 已提交；送达状态会在收件箱中更新。" : "消息已提交；送达状态会在对话中更新。");
  }

  return (
    <div className="border-t border-border bg-white px-4 py-3 sm:px-6">
      <label htmlFor="session-message" className="text-xs font-semibold text-foreground">
        发送给 {selected.role}
      </label>
      <textarea
        id="session-message"
        value={content}
        onChange={(event) => { setContent(event.target.value); setNotice(null); }}
        rows={2}
        maxLength={8000}
        placeholder="输入消息，或将上下文移交给其他 Session…"
        className="input-base mt-2 min-h-0 w-full resize-none py-2 leading-5"
      />
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          Handoff 接收方
          <select
            value={recipientId}
            onChange={(event) => setRecipientId(event.target.value)}
            disabled={recipients.length === 0}
            className="min-h-9 rounded-lg border border-border bg-white px-3 text-xs font-semibold text-foreground"
          >
            {recipients.length === 0 ? <option value="">需要另一个 Session</option> : null}
            {recipients.map((session) => <option key={session.id} value={session.id}>{session.role}</option>)}
          </select>
        </label>
        <div className="sm:ml-auto flex gap-2">
          <button
            type="button"
            onClick={() => void submit("message")}
            disabled={busy || !content.trim()}
            className="btn btn-secondary min-h-9 flex-1 px-3 text-xs sm:flex-none"
          >
            <Send className="h-4 w-4" />发送消息
          </button>
          <button
            type="button"
            onClick={() => void submit("handoff")}
            disabled={busy || !content.trim() || !recipientId}
            className="btn btn-primary min-h-9 flex-1 px-3 text-xs sm:flex-none"
          >
            创建 Handoff<ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
      {notice ? <p role="status" className="mt-2 text-[11px] font-medium text-success">{notice}</p> : null}
    </div>
  );
}
