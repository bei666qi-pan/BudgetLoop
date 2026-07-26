"use client";

import { Check, GitBranch, Plus, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import type { CreateWorkSessionRequest } from "@/lib/types";

const DEFAULT_BUDGET = {
  max_total_tokens: 50_000,
  max_wall_time_seconds: 1_200,
  max_active_runtime_seconds: 600,
  max_llm_calls: 20,
  max_cost: 5,
  max_parallel_llm_calls: 2,
};

export function CreateSessionDialog({
  open,
  defaultWorktree,
  busy,
  error,
  onClose,
  onCreate,
}: {
  open: boolean;
  defaultWorktree: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onCreate: (body: CreateWorkSessionRequest) => Promise<void>;
}) {
  const [role, setRole] = useState("");
  const [goal, setGoal] = useState("");
  const [privateContext, setPrivateContext] = useState("");
  const [worktree, setWorktree] = useState(defaultWorktree);

  if (!open) return null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!role.trim() || !goal.trim()) return;
    await onCreate({
      role: role.trim(),
      goal: goal.trim(),
      private_context: privateContext.trim(),
      template: "small_feature",
      require_approval: true,
      strategy: "dynamic",
      budget: DEFAULT_BUDGET,
      worktree_enabled: worktree,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/20 p-0 backdrop-blur-sm sm:items-center sm:p-6" role="presentation">
      <form onSubmit={submit} onKeyDown={(event) => { if (event.key === "Escape" && !busy) onClose(); }} className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-t-2xl border border-border bg-white shadow-elevated sm:rounded-2xl" role="dialog" aria-modal="true" aria-labelledby="new-session-title">
        <header className="flex items-start justify-between border-b border-border px-5 py-5 sm:px-7">
          <div>
            <h2 id="new-session-title" className="text-xl font-semibold tracking-tight">新建 Session</h2>
            <p className="mt-1 text-sm text-muted-foreground">为这个团队添加一个独立目标、上下文与预算的专业工作单元。</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭" className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="h-5 w-5" /></button>
        </header>
        <div className="space-y-5 px-5 py-6 sm:px-7">
          <label className="block"><span className="field-label">角色</span><input autoFocus value={role} onChange={(event) => setRole(event.target.value)} maxLength={120} placeholder="例如：后端实现" className="input-base mt-2 w-full" /></label>
          <label className="block"><span className="field-label">独立目标</span><textarea value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={10000} rows={3} placeholder="这个 Session 对项目目标负责什么？" className="input-base mt-2 w-full resize-none" /></label>
          <label className="block"><span className="field-label">私有上下文</span><textarea value={privateContext} onChange={(event) => setPrivateContext(event.target.value)} maxLength={30000} rows={4} placeholder="仅此 Session 可见的约束、已有判断或文件线索（可选）" className="input-base mt-2 w-full resize-none" /><span className="field-hint">不会自动复制到其他 Session；跨 Session 信息只能通过明确消息或 Handoff 发送。</span></label>
          <button type="button" role="switch" aria-checked={worktree} onClick={() => setWorktree((value) => !value)} className={`flex w-full items-start gap-4 rounded-xl border p-4 text-left transition-colors ${worktree ? "border-accent/35 bg-accent/5" : "border-border bg-white hover:border-border-strong"}`}>
            <span className={`mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg ${worktree ? "bg-accent text-white" : "bg-muted text-muted-foreground"}`}>{worktree ? <Check className="h-4 w-4" /> : <GitBranch className="h-4 w-4" />}</span>
            <span><span className="font-semibold">独立 Git Worktree</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">在现有 Docker 工作区内创建服务端命名的分支与 worktree。创建失败时运行会明确失败，不会静默换目录。</span></span>
          </button>
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><ShieldCheck className="h-4 w-4 text-success" />默认启用高风险操作审批与独立硬预算。</div>
          {error ? <div role="alert" className="rounded-lg border border-critical/20 bg-critical/5 px-4 py-3 text-sm text-critical">{error}</div> : null}
        </div>
        <footer className="flex items-center justify-end gap-3 border-t border-border px-5 py-4 sm:px-7">
          <button type="button" onClick={onClose} className="btn btn-secondary">取消</button>
          <button type="submit" disabled={busy || !role.trim() || !goal.trim()} className="btn btn-primary"><Plus className="h-4 w-4" />{busy ? "正在创建…" : "创建并启动"}</button>
        </footer>
      </form>
    </div>
  );
}
