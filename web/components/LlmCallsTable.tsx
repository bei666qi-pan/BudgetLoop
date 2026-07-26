"use client";

// LLM 调用列表：表格 + call_kind 筛选 + 行展开详情。
import { useMemo, useState } from "react";
import { LlmCall } from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatTime,
  formatTokens,
} from "@/lib/format";
import { statusClass, STATUS_LABELS } from "@/lib/presentation";
import { EmptyState, KeyValue } from "@/components/ui";

const KIND_LABEL: Record<string, string> = {
  agent: "Agent 推理",
  condenser: "上下文压缩",
  other: "其他",
};

function RequestStatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${statusClass(status)}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export default function LlmCallsTable({ calls }: { calls: LlmCall[] }) {
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const kinds = useMemo(
    () => Array.from(new Set(calls.map((c) => c.call_kind))),
    [calls],
  );
  const filtered = useMemo(
    () =>
      kindFilter === "all"
        ? calls
        : calls.filter((c) => c.call_kind === kindFilter),
    [calls, kindFilter],
  );

  if (calls.length === 0) {
    return (
      <EmptyState
        title="暂无 LLM 调用记录"
        hint="Agent 开始推理后，每次调用的 token、耗时与费用都会记录在这里。"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">按类型筛选：</span>
        {["all", ...kinds].map((k) => (
          <button
            key={k}
            onClick={() => setKindFilter(k)}
            className={`rounded-full px-2.5 py-1 font-medium ring-1 ring-inset ${
              kindFilter === k
                ? "bg-foreground text-background ring-foreground"
                : "bg-surface text-muted-foreground ring-border hover:bg-muted"
            }`}
          >
            {k === "all" ? "全部" : (KIND_LABEL[k] ?? k)}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>阶段</th>
              <th>类型</th>
              <th>模型</th>
              <th className="text-right">输入 tok</th>
              <th className="text-right">输出 tok</th>
              <th className="text-right">总 tok</th>
              <th className="text-right">耗时</th>
              <th className="text-right">费用</th>
              <th className="text-right">进展评分</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody className="bg-surface">
            {filtered.map((c, i) => {
              const open = openId === c.id;
              return [
                <tr
                  key={c.id}
                  onClick={() => setOpenId(open ? null : c.id)}
                  className="cursor-pointer"
                >
                  <td className="tabular-nums text-muted-foreground">
                    {i + 1}
                  </td>
                  <td className="text-muted-foreground">{c.phase ?? "—"}</td>
                  <td className="text-muted-foreground">
                    {KIND_LABEL[c.call_kind] ?? c.call_kind}
                  </td>
                  <td className="max-w-40 truncate font-mono text-foreground">
                    {c.model ?? "—"}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {formatTokens(c.prompt_tokens)}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {formatTokens(c.completion_tokens)}
                  </td>
                  <td className="text-right tabular-nums font-medium text-foreground">
                    {formatTokens(c.total_tokens)}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {formatDurationMs(c.duration_ms)}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {formatCost(c.estimated_cost)}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {c.progress_score !== null && c.progress_score !== undefined
                      ? c.progress_score.toFixed(2)
                      : "—"}
                  </td>
                  <td>
                    <RequestStatusBadge status={c.request_status} />
                  </td>
                </tr>,
                open ? (
                  <tr key={`${c.id}-detail`} className="bg-muted hover:bg-muted">
                    <td colSpan={11}>
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <div>
                          <dl>
                            <KeyValue k="call_id" v={c.call_id} />
                            <KeyValue k="迭代" v={c.iteration} />
                            <KeyValue
                              k="开始时间"
                              v={formatTime(c.started_at)}
                            />
                            <KeyValue
                              k="finish_reason"
                              v={c.finish_reason ?? "—"}
                            />
                            <KeyValue k="重试次数" v={c.retry_count} />
                            <KeyValue
                              k="token 来源"
                              v={c.token_source ?? "—"}
                            />
                            {c.effective !== null &&
                              c.effective !== undefined && (
                                <KeyValue
                                  k="是否有效进展"
                                  v={c.effective ? "是" : "否"}
                                />
                              )}
                          </dl>
                          {c.inefficiency_reason && (
                            <p className="mt-2 rounded-md border border-warning/30 bg-warning/10 px-2 py-1.5 text-[11px] text-warning">
                              低效原因：{c.inefficiency_reason}
                            </p>
                          )}
                        </div>
                        <div className="space-y-2">
                          {c.input_summary && (
                            <div>
                              <p className="mb-0.5 text-[11px] font-medium text-muted-foreground">
                                输入摘要
                              </p>
                              <p className="whitespace-pre-wrap rounded-md bg-surface p-2 text-[11px] leading-relaxed text-foreground ring-1 ring-border">
                                {c.input_summary}
                              </p>
                            </div>
                          )}
                          {c.output_summary && (
                            <div>
                              <p className="mb-0.5 text-[11px] font-medium text-muted-foreground">
                                输出摘要
                              </p>
                              <p className="whitespace-pre-wrap rounded-md bg-surface p-2 text-[11px] leading-relaxed text-foreground ring-1 ring-border">
                                {c.output_summary}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">
        共 {filtered.length} 次调用 · 费用列显示「价格未配置」时表示该模型缺少价格表，仅按 token 统计。
      </p>
    </div>
  );
}
