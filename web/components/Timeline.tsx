"use client";

// Loop 时间线：把 execution_events 渲染成可展开的条目流。
// 每条：分类图标 + 类型标签 + 关键字段摘要；点击展开 JSON pretty 详情。
import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { ExecutionEvent } from "@/lib/types";
import { CATEGORY_STYLE, approvalIdOf, eventMeta } from "@/lib/events";
import { formatTime } from "@/lib/format";
import { EmptyState } from "@/components/ui";

/** 从 payload 提取少量标量字段做友好摘要（长文本截断）。 */
function summaryFields(payload: Record<string, unknown>): [string, string][] {
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(payload)) {
    if (out.length >= 5) break;
    if (v === null || v === undefined) continue;
    if (typeof v === "object") continue;
    let s = String(v);
    if (s.length > 80) s = `${s.slice(0, 80)}…`;
    out.push([k, s]);
  }
  return out;
}

function TimelineItem({
  event,
  pendingApprovalId,
  onOpenApproval,
}: {
  event: ExecutionEvent;
  pendingApprovalId: string | null;
  onOpenApproval: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const meta = eventMeta(event.type);
  const style = CATEGORY_STYLE[meta.category];
  const fields = summaryFields(event.payload);
  const apId =
    event.type === "approval_requested" ? approvalIdOf(event.payload) : null;
  const IconComp = meta.icon;

  return (
    <li className="relative pl-8">
      {/* 时间轴节点与竖线 */}
      <span
        className={`absolute left-0 top-1.5 flex h-5 w-5 items-center justify-center rounded-full text-background ${style.dot}`}
        aria-hidden
      >
        <IconComp className="h-3 w-3" />
      </span>
      <div className="rounded-md border border-border/50 bg-surface">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/30"
        >
          <span
            className={`mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset ${style.badge}`}
          >
            {meta.label}
          </span>
          <span className="min-w-0 flex-1">
            {fields.length > 0 ? (
              <span className="block space-y-0.5">
                {fields.map(([k, v]) => (
                  <span
                    key={k}
                    className="block truncate text-xs text-muted-foreground"
                  >
                    <span className="text-muted-foreground">{k}: </span>
                    {v}
                  </span>
                ))}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">（无附加字段）</span>
            )}
          </span>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {formatTime(event.created_at)}
          </span>
          {open ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
          )}
        </button>

        {apId && pendingApprovalId === apId && (
          <div className="border-t border-warning/20 bg-warning/10 px-3 py-2">
            <button
              onClick={() => onOpenApproval(apId)}
              className="rounded-md bg-warning px-3 py-1 text-xs font-medium text-background hover:bg-warning/80"
            >
              处理审批请求
            </button>
          </div>
        )}

        {open && (
          <pre className="max-h-72 overflow-auto border-t border-border/50 bg-muted/30 px-3 py-2 font-mono text-[11px] leading-relaxed text-foreground">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        )}
      </div>
    </li>
  );
}

export default function Timeline({
  events,
  pendingApprovalId,
  onOpenApproval,
}: {
  events: ExecutionEvent[];
  pendingApprovalId: string | null;
  onOpenApproval: (id: string) => void;
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="暂无事件"
        hint="任务启动后，计划、执行、工具调用等事件会实时出现在这里。"
      />
    );
  }
  return (
    <ol className="relative space-y-2 before:absolute before:bottom-2 before:left-[9px] before:top-2 before:w-px before:bg-border">
      {events.map((e) => (
        <TimelineItem
          key={e.seq}
          event={e}
          pendingApprovalId={pendingApprovalId}
          onOpenApproval={onOpenApproval}
        />
      ))}
    </ol>
  );
}
