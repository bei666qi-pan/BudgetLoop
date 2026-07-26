"use client";

import Link from "next/link";
import { Check, Clock3, ExternalLink, GitBranch, Inbox, Pause, Pencil, Save, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { budgetRatio, incomingMessages, presentWorktreePath, sessionTone } from "@/lib/container-presentation";
import { ProgressBar } from "@/components/ui";
import type { SessionTranscriptEntry, WorkContainer, WorkSessionDetail } from "@/lib/types";

export function SessionInspector({
  container,
  session,
  transcript,
  busy,
  onPause,
  onSaveContext,
}: {
  container: WorkContainer;
  session: WorkSessionDetail;
  transcript: SessionTranscriptEntry[];
  busy: boolean;
  onPause: () => Promise<void>;
  onSaveContext: (value: string) => Promise<void>;
}) {
  const inbox = incomingMessages(transcript, session.id);
  const [editing, setEditing] = useState(false);
  const [context, setContext] = useState(container.shared_context ?? "");
  useEffect(() => {
    if (!editing) setContext(container.shared_context ?? "");
  }, [container.shared_context, editing]);
  const ratio = budgetRatio(session);
  const worktreePath = presentWorktreePath(session.worktree_path);

  return (
    <aside className="min-h-0 overflow-y-auto border-l border-border bg-white/60" aria-label="团队与运行信息">
      <section className="border-b border-border p-5">
        <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-sm font-semibold"><UsersRound className="h-4 w-4 text-accent" />团队上下文</h2>{editing ? <button onClick={() => { setContext(container.shared_context ?? ""); setEditing(false); }} aria-label="取消编辑" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"><X className="h-4 w-4" /></button> : <button onClick={() => setEditing(true)} aria-label="编辑团队上下文" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"><Pencil className="h-4 w-4" /></button>}</div>
        {editing ? <div className="mt-3"><textarea aria-label="团队共享上下文" value={context} onChange={(event) => setContext(event.target.value)} rows={6} maxLength={30000} className="input-base w-full resize-none text-xs leading-5" /><button onClick={async () => { await onSaveContext(context); setEditing(false); }} disabled={busy} className="btn btn-primary mt-2 min-h-9 w-full text-xs"><Save className="h-3.5 w-3.5" />保存共享上下文</button></div> : <p className="mt-3 whitespace-pre-wrap text-xs leading-5 text-muted-foreground">{container.shared_context || "尚未设置共享上下文。"}</p>}
      </section>

      <section className="border-b border-border p-5">
        <div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><Inbox className="h-4 w-4 text-accent" />收件箱</h2><span className="text-[11px] text-muted-foreground">{inbox.filter((item) => item.delivery_state === "queued").length} 排队中 · {inbox.filter((item) => item.delivery_state === "delivered").length} 已送达</span></div>
        <div className="mt-3 space-y-2">
          {inbox.length === 0 ? <p className="text-xs text-muted-foreground">没有发给这个 Session 的显式消息。</p> : inbox.slice(-5).reverse().map((item) => <div key={item.id} className="flex items-center gap-2 text-xs"><span className={`h-1.5 w-1.5 rounded-full ${item.delivery_state === "delivered" ? "bg-success" : "bg-warning"}`} /><span className="min-w-0 flex-1 truncate font-mono text-[10px] text-foreground">{item.id}</span><span className="shrink-0 text-[10px] text-muted-foreground">{item.sender_role}</span></div>)}
        </div>
      </section>

      <section className="border-b border-border p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><GitBranch className="h-4 w-4 text-accent" />运行与工作区</h2>
        <dl className="mt-4 space-y-3 text-xs">
          <div className="flex items-center justify-between gap-3"><dt className="text-muted-foreground">当前 Run</dt><dd><Link href={`/runs/${session.current_run_id}`} className="flex items-center gap-1 font-mono text-accent hover:underline">{session.current_run_id.slice(0, 8)}<ExternalLink className="h-3 w-3" /></Link></dd></div>
          <div className="flex items-center justify-between gap-3"><dt className="text-muted-foreground">会话状态</dt><dd className="flex items-center gap-1.5 font-semibold"><span className={`h-1.5 w-1.5 rounded-full ${sessionTone(session.status)}`} />{session.status}</dd></div>
          <div className="flex items-center justify-between gap-3"><dt className="text-muted-foreground">Worktree</dt><dd className="flex items-center gap-1.5 font-semibold">{session.worktree_enabled ? session.workspace_status === "READY" ? <><Check className="h-3.5 w-3.5 text-success" />已就绪</> : <><Clock3 className="h-3.5 w-3.5 text-warning" />{session.workspace_status}</> : "未启用"}</dd></div>
          {session.worktree_enabled ? <><div><dt className="text-muted-foreground">分支</dt><dd className="mt-1 break-all font-mono text-[10px] leading-4">{session.worktree_branch ?? "等待工作区创建"}</dd></div><div><dt className="text-muted-foreground">目录</dt><dd className="mt-1 break-all font-mono text-[10px] leading-4">{worktreePath ?? "等待工作区创建"}</dd></div></> : null}
          {session.workspace_error ? <div className="rounded-lg border border-critical/20 bg-critical/5 p-3 text-critical"><dt className="font-semibold">工作区错误</dt><dd className="mt-1 leading-5">{session.workspace_error}</dd></div> : null}
        </dl>
        {session.budget ? <div className="mt-5"><div className="flex items-center justify-between text-[11px] text-muted-foreground"><span>Token 预算使用</span><span className="font-mono">{Math.round(ratio * 100)}%</span></div><div className="mt-2"><ProgressBar ratio={ratio} height="h-1.5" /></div><p className="mt-2 font-mono text-[10px] text-muted-foreground">{session.budget.used_tokens.toLocaleString()} / {session.budget.max_total_tokens.toLocaleString()} tokens</p></div> : null}
      </section>

      <section className="p-5"><h2 className="text-sm font-semibold">会话操作</h2><button type="button" onClick={() => void onPause()} disabled={busy || session.status === "PAUSED"} className="btn btn-secondary mt-3 w-full"><Pause className="h-4 w-4" />{session.status === "PAUSED" ? "Session 已暂停" : "暂停 Session"}</button></section>
    </aside>
  );
}
