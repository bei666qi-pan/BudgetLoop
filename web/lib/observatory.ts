// Token 观测台：从 LlmCall[] 纯派生聚合指标、分布与时间序列。
// 原则：可选字段缺失时保持不可用（null），绝不填 0 或编造数据。

import type { LlmCall } from "@/lib/types";
import type { ChartPoint } from "@/components/SvgLineChart";

export const SERIES_CAP = 500;

export interface TokenTotals {
  total: number;
  prompt: number;
  completion: number;
  reasoning: number;
  cacheRead: number;
  cacheWrite: number;
}

export interface BreakdownEntry {
  key: string;
  calls: number;
  tokens: number;
}

export interface ObservatorySummary {
  callCount: number;
  tokens: TokenTotals;
  /** 所有调用都未配置价格时为 null（不可用），否则为已报价调用的费用合计。 */
  cost: number | null;
  /** 0-1；无调用时为 null。 */
  successRate: number | null;
  /** cache_read / (prompt + cache_read)，仅统计两个字段都上报的调用；0-1，无可用数据为 null。 */
  cacheHitRate: number | null;
  /** 仅统计上报了 duration_ms 的调用；无可用数据为 null。 */
  avgDurationMs: number | null;
  /** 仅统计上报了 ttft_ms 的调用；无可用数据为 null。 */
  avgTtftMs: number | null;
  /** 按 token 降序。 */
  byModel: BreakdownEntry[];
  byKind: BreakdownEntry[];
  /** 累计 token 序列，x = ended_at ?? started_at，按时间升序，最多保留最新 500 点。 */
  tokenSeries: ChartPoint[];
  /** 累计费用序列；所有调用价格未配置时为空数组。 */
  costSeries: ChartPoint[];
}

/** 单次调用消耗的 token 总数：优先 total_tokens，缺失时回退 prompt + completion。 */
function callTokens(c: LlmCall): number {
  if (c.total_tokens !== null && c.total_tokens !== undefined) return c.total_tokens;
  return (c.prompt_tokens ?? 0) + (c.completion_tokens ?? 0);
}

function sumField(calls: LlmCall[], pick: (c: LlmCall) => number | null | undefined): number {
  return calls.reduce((acc, c) => acc + (pick(c) ?? 0), 0);
}

function averageOf(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function breakdown(calls: LlmCall[], keyOf: (c: LlmCall) => string): BreakdownEntry[] {
  const map = new Map<string, BreakdownEntry>();
  for (const c of calls) {
    const key = keyOf(c);
    const entry = map.get(key) ?? { key, calls: 0, tokens: 0 };
    entry.calls += 1;
    entry.tokens += callTokens(c);
    map.set(key, entry);
  }
  return Array.from(map.values()).sort((a, b) => b.tokens - a.tokens);
}

/** 序列用时间戳：优先结束时间，缺失时用开始时间；无法解析返回 null。 */
function seriesTimestamp(c: LlmCall): number | null {
  const raw = c.ended_at ?? c.started_at;
  if (!raw) return null;
  const t = new Date(raw).getTime();
  return Number.isNaN(t) ? null : t;
}

export function deriveObservatory(calls: LlmCall[]): ObservatorySummary {
  const tokens: TokenTotals = {
    total: sumField(calls, callTokens),
    prompt: sumField(calls, (c) => c.prompt_tokens),
    completion: sumField(calls, (c) => c.completion_tokens),
    reasoning: sumField(calls, (c) => c.reasoning_tokens),
    cacheRead: sumField(calls, (c) => c.cache_read_tokens),
    cacheWrite: sumField(calls, (c) => c.cache_write_tokens),
  };

  const reportedCosts = calls
    .map((c) => c.estimated_cost)
    .filter((v): v is number => v !== null && v !== undefined);
  const cost = reportedCosts.length === 0 ? null : reportedCosts.reduce((a, b) => a + b, 0);

  const successRate =
    calls.length === 0
      ? null
      : calls.filter((c) => c.request_status === "success").length / calls.length;

  // 缓存命中率：只统计 prompt_tokens 与 cache_read_tokens 都上报的调用。
  const cacheCalls = calls.filter(
    (c) => c.prompt_tokens !== null && c.prompt_tokens !== undefined
      && c.cache_read_tokens !== null && c.cache_read_tokens !== undefined,
  );
  const cacheDenominator = cacheCalls.reduce(
    (acc, c) => acc + (c.prompt_tokens as number) + (c.cache_read_tokens as number),
    0,
  );
  const cacheHitRate =
    cacheDenominator > 0
      ? cacheCalls.reduce((acc, c) => acc + (c.cache_read_tokens as number), 0) / cacheDenominator
      : null;

  const avgDurationMs = averageOf(
    calls.map((c) => c.duration_ms).filter((v): v is number => v !== null && v !== undefined),
  );
  const avgTtftMs = averageOf(
    calls.map((c) => c.ttft_ms).filter((v): v is number => v !== null && v !== undefined),
  );

  // 时间序列：按时间升序累计，再截取最新 500 点（截断点保留此前累计值）。
  const timed = calls
    .map((c) => ({ call: c, x: seriesTimestamp(c) }))
    .filter((p): p is { call: LlmCall; x: number } => p.x !== null)
    .sort((a, b) => a.x - b.x);

  let tokenAcc = 0;
  let costAcc = 0;
  const tokenSeries: ChartPoint[] = [];
  const costSeries: ChartPoint[] = [];
  for (const { call, x } of timed) {
    tokenAcc += callTokens(call);
    tokenSeries.push({ x, y: tokenAcc });
    if (call.estimated_cost !== null && call.estimated_cost !== undefined) {
      costAcc += call.estimated_cost;
      costSeries.push({ x, y: costAcc });
    }
  }

  return {
    callCount: calls.length,
    tokens,
    cost,
    successRate,
    cacheHitRate,
    avgDurationMs,
    avgTtftMs,
    byModel: breakdown(calls, (c) => c.model ?? "未知模型"),
    byKind: breakdown(calls, (c) => c.call_kind),
    tokenSeries: tokenSeries.slice(-SERIES_CAP),
    costSeries: costSeries.slice(-SERIES_CAP),
  };
}
