import { describe, expect, it } from "vitest";
import { deriveObservatory, SERIES_CAP } from "@/lib/observatory";
import type { LlmCall } from "@/lib/types";

function makeCall(overrides: Partial<LlmCall> = {}): LlmCall {
  return {
    id: "c1",
    run_id: "r1",
    call_id: "call-1",
    iteration: 1,
    phase: "scan",
    call_kind: "agent",
    model: "gpt-4o",
    started_at: "2026-07-25T01:00:00Z",
    ended_at: "2026-07-25T01:00:01Z",
    duration_ms: 1000,
    prompt_tokens: 100,
    completion_tokens: 50,
    total_tokens: 150,
    estimated_cost: 0.01,
    finish_reason: "stop",
    request_status: "success",
    retry_count: 0,
    input_summary: null,
    output_summary: null,
    progress_score: null,
    inefficiency_reason: null,
    ...overrides,
  };
}

describe("deriveObservatory", () => {
  it("空调用列表：聚合为 0 或不可用，序列为空", () => {
    const s = deriveObservatory([]);
    expect(s.callCount).toBe(0);
    expect(s.tokens).toEqual({
      total: 0,
      prompt: 0,
      completion: 0,
      reasoning: 0,
      cacheRead: 0,
      cacheWrite: 0,
    });
    expect(s.cost).toBeNull();
    expect(s.successRate).toBeNull();
    expect(s.cacheHitRate).toBeNull();
    expect(s.avgDurationMs).toBeNull();
    expect(s.avgTtftMs).toBeNull();
    expect(s.byModel).toEqual([]);
    expect(s.byKind).toEqual([]);
    expect(s.tokenSeries).toEqual([]);
    expect(s.costSeries).toEqual([]);
  });

  it("混合 null 字段：只累计已上报的值", () => {
    const s = deriveObservatory([
      makeCall({
        id: "a",
        prompt_tokens: 100,
        completion_tokens: 50,
        total_tokens: 150,
        reasoning_tokens: 20,
        cache_read_tokens: 30,
        cache_write_tokens: null,
        duration_ms: 1000,
        ttft_ms: 200,
        estimated_cost: 0.02,
      }),
      makeCall({
        id: "b",
        prompt_tokens: null,
        completion_tokens: null,
        total_tokens: null,
        reasoning_tokens: null,
        cache_read_tokens: null,
        duration_ms: null,
        ttft_ms: null,
        estimated_cost: null,
        request_status: "failed",
      }),
    ]);
    expect(s.tokens.total).toBe(150); // total_tokens 缺失时回退 prompt+completion（此处均为 null → 0）
    expect(s.tokens.prompt).toBe(100);
    expect(s.tokens.completion).toBe(50);
    expect(s.tokens.reasoning).toBe(20);
    expect(s.tokens.cacheRead).toBe(30);
    expect(s.tokens.cacheWrite).toBe(0);
    expect(s.cost).toBeCloseTo(0.02);
    expect(s.successRate).toBeCloseTo(0.5);
    expect(s.avgDurationMs).toBe(1000); // 只对上报了的调用取平均
    expect(s.avgTtftMs).toBe(200);
  });

  it("全部调用价格未配置：费用保持不可用（null）而非 0", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", estimated_cost: null }),
      makeCall({ id: "b", estimated_cost: null }),
    ]);
    expect(s.cost).toBeNull();
    expect(s.costSeries).toEqual([]);
  });

  it("部分调用价格未配置：费用为已报价部分合计，序列只含已报价调用", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", estimated_cost: 0.01, ended_at: "2026-07-25T01:00:01Z" }),
      makeCall({ id: "b", estimated_cost: null, ended_at: "2026-07-25T01:00:02Z" }),
      makeCall({ id: "c", estimated_cost: 0.02, ended_at: "2026-07-25T01:00:03Z" }),
    ]);
    expect(s.cost).toBeCloseTo(0.03);
    expect(s.costSeries).toHaveLength(2);
    expect(s.costSeries[1].y).toBeCloseTo(0.03);
  });

  it("缓存命中率：分母只含 prompt 与 cache_read 都上报的调用", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", prompt_tokens: 100, cache_read_tokens: 100 }), // 命中 100/200
      makeCall({ id: "b", prompt_tokens: 1000, cache_read_tokens: null }), // 未上报 cache，不计入
      makeCall({ id: "c", prompt_tokens: null, cache_read_tokens: 500 }), // 未上报 prompt，不计入
    ]);
    expect(s.cacheHitRate).toBeCloseTo(0.5);
  });

  it("缓存命中率：分母为 0 时不可用", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", prompt_tokens: 0, cache_read_tokens: 0 }),
    ]);
    expect(s.cacheHitRate).toBeNull();
  });

  it("成功率按 request_status 统计", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", request_status: "success" }),
      makeCall({ id: "b", request_status: "success" }),
      makeCall({ id: "c", request_status: "failed" }),
      makeCall({ id: "d", request_status: "rejected_budget" }),
    ]);
    expect(s.successRate).toBeCloseTo(0.5);
  });

  it("按模型与按类型拆分：token 降序", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", model: "gpt-4o", total_tokens: 100, call_kind: "agent" }),
      makeCall({ id: "b", model: "gpt-4o-mini", total_tokens: 300, call_kind: "condenser" }),
      makeCall({ id: "c", model: null, total_tokens: 50, call_kind: "agent" }),
    ]);
    expect(s.byModel.map((e) => [e.key, e.tokens])).toEqual([
      ["gpt-4o-mini", 300],
      ["gpt-4o", 100],
      ["未知模型", 50],
    ]);
    expect(s.byKind.map((e) => [e.key, e.calls, e.tokens])).toEqual([
      ["condenser", 1, 300],
      ["agent", 2, 150],
    ]);
  });

  it("序列按时间升序，x = ended_at ?? started_at，累计值正确", () => {
    const s = deriveObservatory([
      makeCall({ id: "late", total_tokens: 30, ended_at: "2026-07-25T01:00:03Z", estimated_cost: 0.03 }),
      makeCall({ id: "early", total_tokens: 10, started_at: "2026-07-25T01:00:01Z", ended_at: null, estimated_cost: 0.01 }),
      makeCall({ id: "mid", total_tokens: 20, ended_at: "2026-07-25T01:00:02Z", estimated_cost: 0.02 }),
      makeCall({ id: "no-time", total_tokens: 99, started_at: null, ended_at: null, estimated_cost: null }),
    ]);
    const t1 = new Date("2026-07-25T01:00:01Z").getTime();
    const t2 = new Date("2026-07-25T01:00:02Z").getTime();
    const t3 = new Date("2026-07-25T01:00:03Z").getTime();
    expect(s.tokenSeries).toEqual([
      { x: t1, y: 10 }, // ended_at 缺失 → 用 started_at
      { x: t2, y: 30 },
      { x: t3, y: 60 },
    ]);
    expect(s.costSeries.map((p) => p.x)).toEqual([t1, t2, t3]);
    expect(s.costSeries[2].y).toBeCloseTo(0.06);
  });

  it(`序列超过 ${SERIES_CAP} 点：保留最新 ${SERIES_CAP} 点且累计值不丢失`, () => {
    const calls = Array.from({ length: SERIES_CAP + 100 }, (_, i) =>
      makeCall({
        id: `c${i}`,
        total_tokens: 1,
        estimated_cost: 0.001,
        started_at: new Date(Date.UTC(2026, 6, 25, 1, 0, 0) + i * 1000).toISOString(),
        ended_at: null,
      }),
    );
    const s = deriveObservatory(calls);
    expect(s.tokenSeries).toHaveLength(SERIES_CAP);
    expect(s.costSeries).toHaveLength(SERIES_CAP);
    // 首个保留点的累计值包含被截掉的 100 次调用。
    expect(s.tokenSeries[0].y).toBe(101);
    expect(s.tokenSeries[SERIES_CAP - 1].y).toBe(SERIES_CAP + 100);
    expect(s.costSeries[0].y).toBeCloseTo(0.101);
    expect(s.costSeries[SERIES_CAP - 1].y).toBeCloseTo((SERIES_CAP + 100) * 0.001);
    // 升序保持不变。
    for (let i = 1; i < s.tokenSeries.length; i += 1) {
      expect(s.tokenSeries[i].x).toBeGreaterThanOrEqual(s.tokenSeries[i - 1].x);
    }
  });

  it("total_tokens 缺失时回退 prompt + completion", () => {
    const s = deriveObservatory([
      makeCall({ id: "a", total_tokens: null, prompt_tokens: 70, completion_tokens: 30 }),
    ]);
    expect(s.tokens.total).toBe(100);
    expect(s.tokenSeries[0].y).toBe(100);
  });
});
