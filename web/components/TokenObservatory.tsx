"use client";

// Token 观测台：聚合指标、累计趋势、按模型/类型拆分、逐次调用计量。
// 纯展示组件，数据全部来自运行页已有轮询状态；未上报字段标记为「未上报」，不填 0。
import { useMemo } from "react";
import type { LlmCall } from "@/lib/types";
import { deriveObservatory, type BreakdownEntry } from "@/lib/observatory";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/format";
import { EmptyState, ProgressBar } from "@/components/ui";
import SvgLineChart from "@/components/SvgLineChart";

const KIND_LABEL: Record<string, string> = {
  agent: "Agent 推理",
  condenser: "上下文压缩",
  other: "其他",
};

const NOT_REPORTED = "未上报";

/** 可选计量字段：null/undefined → 未上报，绝不填 0。 */
function reported<T extends number | string>(v: T | null | undefined, format?: (v: T) => string): string {
  if (v === null || v === undefined) return NOT_REPORTED;
  return format ? format(v) : String(v);
}

/** 亚秒级时长保留 ms 精度（首 Token 延迟常小于 1s），其余复用 formatDurationMs。 */
function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return formatDurationMs(ms);
}

function formatRatio(ratio: number | null): string {
  return ratio === null ? "—" : `${Math.round(ratio * 100)}%`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 truncate font-mono text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function BreakdownList({ title, entries, labelOf }: { title: string; entries: BreakdownEntry[]; labelOf: (key: string) => string }) {
  const max = Math.max(0, ...entries.map((e) => e.tokens));
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-3 space-y-3">
        {entries.map((e) => (
          <div key={e.key}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
              <span className="truncate font-medium">{labelOf(e.key)}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {formatTokens(e.tokens)} tok · {e.calls} 次
              </span>
            </div>
            <ProgressBar ratio={max > 0 ? e.tokens / max : 0} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TokenObservatory({ calls }: { calls: LlmCall[] }) {
  const summary = useMemo(() => deriveObservatory(calls), [calls]);

  if (calls.length === 0) {
    return (
      <EmptyState
        title="暂无观测数据"
        hint="运行产生 LLM 调用后，这里会汇总 token 计量、费用趋势与缓存命中情况。"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
        <Metric label="总 Token" value={formatTokens(summary.tokens.total)} />
        <Metric label="输入" value={formatTokens(summary.tokens.prompt)} />
        <Metric label="输出" value={formatTokens(summary.tokens.completion)} />
        <Metric label="推理" value={formatTokens(summary.tokens.reasoning)} />
        <Metric label="缓存" value={formatTokens(summary.tokens.cacheRead + summary.tokens.cacheWrite)} />
        <Metric label="费用" value={formatCost(summary.cost)} />
        <Metric label="平均耗时" value={formatMs(summary.avgDurationMs)} />
        <Metric label="平均首 Token" value={formatMs(summary.avgTtftMs)} />
        <Metric label="成功率" value={formatRatio(summary.successRate)} />
        <Metric label="缓存命中率" value={formatRatio(summary.cacheHitRate)} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold">累计 Token</h3>
          <SvgLineChart points={summary.tokenSeries} yLabel="累计 Token" formatY={formatTokens} />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold">累计费用</h3>
          {summary.cost === null ? (
            <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
              价格未配置，暂无费用趋势
            </div>
          ) : (
            <SvgLineChart points={summary.costSeries} yLabel="累计费用" formatY={formatCost} />
          )}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <BreakdownList title="按模型" entries={summary.byModel} labelOf={(k) => k} />
        <BreakdownList title="按调用类型" entries={summary.byKind} labelOf={(k) => KIND_LABEL[k] ?? k} />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">逐次调用计量</h3>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>模型</th>
                <th>类型</th>
                <th>Provider</th>
                <th className="text-right">首 Token</th>
                <th className="text-right">推理 tok</th>
                <th className="text-right">缓存读 tok</th>
                <th className="text-right">缓存写 tok</th>
                <th>token 来源</th>
                <th className="text-right">重试</th>
              </tr>
            </thead>
            <tbody className="bg-surface">
              {calls.map((c, i) => (
                <tr key={c.id}>
                  <td className="tabular-nums text-muted-foreground">{i + 1}</td>
                  <td className="max-w-40 truncate font-mono text-foreground">{c.model ?? "—"}</td>
                  <td className="text-muted-foreground">{KIND_LABEL[c.call_kind] ?? c.call_kind}</td>
                  <td className="text-muted-foreground">{reported(c.provider)}</td>
                  <td className="text-right tabular-nums text-muted-foreground">
                    {c.ttft_ms === null || c.ttft_ms === undefined ? NOT_REPORTED : formatMs(c.ttft_ms)}
                  </td>
                  <td className="text-right tabular-nums text-muted-foreground">{reported(c.reasoning_tokens, formatTokens)}</td>
                  <td className="text-right tabular-nums text-muted-foreground">{reported(c.cache_read_tokens, formatTokens)}</td>
                  <td className="text-right tabular-nums text-muted-foreground">{reported(c.cache_write_tokens, formatTokens)}</td>
                  <td className="text-muted-foreground">{reported(c.token_source)}</td>
                  <td className="text-right tabular-nums text-muted-foreground">{c.retry_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
