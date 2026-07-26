"use client";

// 预算视图：总预算分段进度条（used + reserved）、各阶段预算表、
// 动态重分配记录、Token / 时间燃尽趋势（纯 SVG，数据源 budget_updated 事件）。
import { useMemo } from "react";
import { BudgetDetail, ExecutionEvent } from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatTime,
  formatTokens,
  percent,
} from "@/lib/format";
import { EmptyState, ProgressBar } from "@/components/ui";
import SvgLineChart, { ChartPoint } from "@/components/SvgLineChart";
import { CHART_COLORS } from "@/lib/chart-colors";

const PHASE_STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  active: "进行中",
  done: "已完成",
  capped: "已截断",
};

/** 从 budget_updated 事件 payload 中尽量宽容地提取累计用量数值。 */
function num(payload: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = payload[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  const nested = payload.budget;
  if (nested && typeof nested === "object") {
    for (const k of keys) {
      const v = (nested as Record<string, unknown>)[k];
      if (typeof v === "number" && Number.isFinite(v)) return v;
    }
  }
  return null;
}

export default function BudgetView({
  detail,
  events,
}: {
  detail: BudgetDetail | null;
  events: ExecutionEvent[];
}) {
  // 燃尽趋势：x = 事件时间，y = 累计用量。
  const { tokenSeries, timeSeries } = useMemo(() => {
    const tokens: ChartPoint[] = [];
    const times: ChartPoint[] = [];
    for (const e of events) {
      if (e.type !== "budget_updated") continue;
      const t = new Date(e.created_at).getTime();
      if (Number.isNaN(t)) continue;
      const usedTokens = num(e.payload, ["used_tokens", "total_tokens", "tokens"]);
      if (usedTokens !== null) tokens.push({ x: t, y: usedTokens });
      const usedMs = num(e.payload, [
        "active_runtime_ms",
        "used_ms",
        "elapsed_ms",
      ]);
      if (usedMs !== null) times.push({ x: t, y: usedMs / 1000 });
    }
    return { tokenSeries: tokens, timeSeries: times };
  }, [events]);

  if (!detail) {
    return (
      <EmptyState
        title="暂无预算数据"
        hint="该运行可能选择了「无预算」策略，或预算信息尚未生成。"
      />
    );
  }

  const { budget, phases, reallocations } = detail;
  const usedPct = percent(budget.used_tokens, budget.max_total_tokens);
  const reservedPct = percent(budget.reserved_tokens, budget.max_total_tokens);
  const projected = budget.projected_tokens ?? null;
  const willOverrun =
    projected !== null && projected > budget.max_total_tokens;

  return (
    <div className="space-y-5">
      {/* 超支预警 */}
      {projected !== null && (
        <div
          className={`rounded-md border px-3 py-2 text-xs ${
            willOverrun
              ? "border-critical/20 bg-critical/5 text-critical"
              : "border-accent/30 bg-accent/10 text-accent"
          }`}
        >
          {willOverrun
            ? `按当前消耗速率，预计总共消耗 ${formatTokens(projected)} tokens，将超出上限 ${formatTokens(budget.max_total_tokens)}，可能触发预算熔断。`
            : `按当前消耗速率，预计总共消耗 ${formatTokens(projected)} tokens，在上限 ${formatTokens(budget.max_total_tokens)} 之内。`}
        </div>
      )}

      {/* 总预算进度（used + reserved 分段） */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-foreground">总预算</h3>
        <div className="relative">
          <ProgressBar
            ratio={budget.max_total_tokens > 0 ? budget.used_tokens / budget.max_total_tokens : 0}
            color={willOverrun ? "bg-critical" : "bg-accent"}
            height="h-3"
          />
          {(reservedPct ?? 0) > 0 && (
            <div
              className="absolute top-0 h-3 rounded-r-full bg-accent/70"
              style={{
                left: `${usedPct ?? 0}%`,
                width: `${Math.min(reservedPct ?? 0, 100 - (usedPct ?? 0))}%`,
              }}
              title={`预留 ${formatTokens(budget.reserved_tokens)}`}
            />
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span>
            已用 <span className="font-semibold text-foreground">{formatTokens(budget.used_tokens)}</span>
          </span>
          <span>
            预留 <span className="font-semibold text-accent">{formatTokens(budget.reserved_tokens)}</span>
          </span>
          <span>
            上限 <span className="font-semibold text-foreground">{formatTokens(budget.max_total_tokens)}</span>
          </span>
          <span>
            费用 {formatCost(budget.used_cost)} / {formatCost(budget.max_cost, `$${budget.max_cost}`)}
          </span>
          <span>
            调用 {budget.used_calls} / {budget.max_llm_calls} 次
          </span>
        </div>
      </section>

      {/* 阶段预算表 */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-foreground">各阶段预算</h3>
        {phases.length === 0 ? (
          <p className="text-xs text-muted-foreground">尚无阶段预算分配。</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="data-table">
              <thead>
                <tr>
                  <th>阶段</th>
                  <th className="text-right">预算 tokens</th>
                  <th className="text-right">已用 tokens</th>
                  <th className="text-right">已用时间</th>
                  <th className="text-right">调用</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody className="bg-surface">
                {phases.map((p) => (
                  <tr key={p.id ?? p.phase}>
                    <td className="font-medium text-foreground">
                      {p.phase}
                    </td>
                    <td className="text-right tabular-nums text-muted-foreground">
                      {formatTokens(p.budget_tokens)}
                    </td>
                    <td className="text-right tabular-nums text-muted-foreground">
                      {formatTokens(p.used_tokens)}
                    </td>
                    <td className="text-right tabular-nums text-muted-foreground">
                      {formatDurationMs(p.used_ms)}
                    </td>
                    <td className="text-right tabular-nums text-muted-foreground">
                      {p.used_calls ?? "—"}
                    </td>
                    <td className="text-muted-foreground">
                      {PHASE_STATUS_LABEL[p.status] ?? p.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 燃尽趋势 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-foreground">
            Token 燃尽趋势
          </h3>
          <SvgLineChart
            points={tokenSeries}
            maxY={budget.max_total_tokens}
            yLabel="累计 token 用量"
            formatY={formatTokens}
          />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-foreground">
            时间燃尽趋势（active 秒）
          </h3>
          <SvgLineChart
            points={timeSeries}
            maxY={budget.max_active_runtime_seconds}
            stroke={CHART_COLORS.success}
            yLabel="累计执行时间（秒）"
            formatY={(v) => `${Math.round(v)}s`}
          />
        </div>
      </section>

      {/* 重分配记录 */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-foreground">
          动态重分配记录
        </h3>
        {reallocations.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            暂无重分配。动态策略下，当某阶段进展不及预期时，预算会被调剂到更有希望的阶段。
          </p>
        ) : (
          <ul className="space-y-1.5">
            {reallocations.map((r, i) => (
              <li
                key={r.id ?? i}
                className="rounded-md border border-border bg-surface px-3 py-2 text-xs text-muted-foreground"
              >
                <span className="font-medium text-foreground">
                  {r.from_phase ?? "?"} → {r.to_phase ?? "?"}
                </span>
                {typeof r.tokens === "number" && (
                  <span className="ml-2 tabular-nums">
                    {formatTokens(r.tokens)} tokens
                  </span>
                )}
                {r.reason && <span className="ml-2 text-muted-foreground">{r.reason}</span>}
                {r.created_at && (
                  <span className="ml-2 text-muted-foreground">
                    {formatTime(r.created_at)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
