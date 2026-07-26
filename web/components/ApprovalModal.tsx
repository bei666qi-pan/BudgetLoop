"use client";

// 审批弹窗：展示 Agent 想做什么 / 为什么 / 风险 / 预计消耗，
// 三个操作：允许 / 拒绝 / 修改后允许（带备注）。
import { useState } from "react";
import { Hand, X } from "lucide-react";
import { ApprovalAction, ApprovalPayload } from "@/lib/types";
import { formatDurationSec, formatTokens } from "@/lib/format";

export default function ApprovalModal({
  approvalId,
  payload,
  onDecide,
  onClose,
}: {
  approvalId: string;
  payload: ApprovalPayload;
  onDecide: (action: ApprovalAction, note: string) => Promise<void>;
  onClose: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<ApprovalAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(action: ApprovalAction) {
    if (action === "modify" && !note.trim()) {
      setError("「修改后允许」需要填写修改说明，告诉 Agent 你想调整什么。");
      return;
    }
    setBusy(action);
    setError(null);
    try {
      await onDecide(action, note.trim());
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  }

  const text = (v: unknown) => (typeof v === "string" && v ? v : null);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="审批请求"
    >
      <div className="w-full max-w-lg card overflow-hidden">
        <header className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Hand className="w-4 h-4 text-warning" />
            Agent 请求人工确认
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors duration-fast"
            aria-label="稍后处理"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="space-y-3 px-5 py-4 text-sm">
          <div>
            <p className="mb-0.5 text-xs font-medium text-muted-foreground">
              想执行的操作
            </p>
            <p className="rounded-md bg-muted/30 px-3 py-2 text-foreground">
              {text(payload.description) ?? "（未提供描述）"}
            </p>
            {text(payload.action_type) && (
              <p className="mt-1 text-xs text-muted-foreground">
                类型：{text(payload.action_type)}
              </p>
            )}
          </div>

          {text(payload.reason) && (
            <div>
              <p className="mb-0.5 text-xs font-medium text-muted-foreground">原因</p>
              <p className="text-foreground">{text(payload.reason)}</p>
            </div>
          )}

          {text(payload.risk) && (
            <div className="rounded-md border border-warning/20 bg-warning/10 px-3 py-2 text-xs text-warning">
              风险等级：{text(payload.risk)}
            </div>
          )}

          <div className="flex gap-4 text-xs text-muted-foreground">
            {typeof payload.est_tokens === "number" && (
              <span>
                预计额外 Token：
                <span className="font-medium text-foreground">
                  {formatTokens(payload.est_tokens)}
                </span>
              </span>
            )}
            {typeof payload.est_seconds === "number" && (
              <span>
                预计额外时间：
                <span className="font-medium text-foreground">
                  {formatDurationSec(payload.est_seconds)}
                </span>
              </span>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              备注（拒绝原因 / 修改说明，「修改后允许」必填）
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="input-base w-full text-sm resize-none"
              placeholder="例如：不要删除 fixtures 目录，改为先备份"
            />
          </div>

          {error && (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-critical">
              {error}
            </p>
          )}
        </div>

        <footer className="flex flex-col gap-2 border-t border-border px-5 py-3.5 sm:flex-row sm:justify-end">
          <button
            onClick={() => decide("reject")}
            disabled={busy !== null}
            className="btn btn-destructive text-xs"
          >
            {busy === "reject" ? "提交中…" : "拒绝"}
          </button>
          <button
            onClick={() => decide("modify")}
            disabled={busy !== null}
            className="btn btn-secondary text-xs"
          >
            {busy === "modify" ? "提交中…" : "修改后允许"}
          </button>
          <button
            onClick={() => decide("approve")}
            disabled={busy !== null}
            className="btn btn-primary text-xs"
          >
            {busy === "approve" ? "提交中…" : "允许执行"}
          </button>
        </footer>
        <p className="px-5 pb-3 text-[11px] text-muted-foreground">
          拒绝后 Agent 会根据你的备注重新规划；审批 ID：{approvalId}
        </p>
      </div>
    </div>
  );
}
