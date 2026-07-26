import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TokenObservatory from "@/components/TokenObservatory";
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
    provider: "openai",
    started_at: "2026-07-25T01:00:00Z",
    ended_at: "2026-07-25T01:00:01Z",
    duration_ms: 1200,
    ttft_ms: 250,
    prompt_tokens: 100,
    completion_tokens: 50,
    total_tokens: 150,
    reasoning_tokens: 20,
    cache_read_tokens: 30,
    cache_write_tokens: 10,
    token_source: "exact",
    estimated_cost: 0.02,
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

const fullCall = makeCall();

const sparseCall = makeCall({
  id: "c2",
  call_id: "call-2",
  call_kind: "condenser",
  model: "gpt-4o-mini",
  provider: null,
  started_at: "2026-07-25T01:00:01Z",
  ended_at: "2026-07-25T01:00:02Z",
  duration_ms: 800,
  ttft_ms: null,
  prompt_tokens: 200,
  completion_tokens: 80,
  total_tokens: 280,
  reasoning_tokens: null,
  cache_read_tokens: null,
  cache_write_tokens: null,
  token_source: undefined,
  estimated_cost: null,
  request_status: "failed",
  retry_count: 3,
});

describe("TokenObservatory", () => {
  it("展示聚合指标、趋势图、拆分与逐次计量", () => {
    render(<TokenObservatory calls={[fullCall, sparseCall]} />);

    // 聚合指标（zh-CN 标签 + 派生值）
    expect(screen.getByText("总 Token")).toBeInTheDocument();
    expect(screen.getByText("430")).toBeInTheDocument(); // 150 + 280
    expect(screen.getByText("费用")).toBeInTheDocument();
    expect(screen.getByText("$0.02")).toBeInTheDocument(); // 仅一次调用报价
    expect(screen.getByText("成功率")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("缓存命中率")).toBeInTheDocument();
    expect(screen.getByText("23%")).toBeInTheDocument(); // 30 / (100 + 30)，只算两字段都上报的调用
    expect(screen.getByText("平均首 Token")).toBeInTheDocument();
    expect(screen.getAllByText("250ms")).toHaveLength(2); // 聚合指标 + 表格行

    // 累计 Token 趋势图（两个数据点 → 渲染 SVG）
    expect(screen.getByLabelText("累计 Token")).toBeInTheDocument();

    // 按模型 / 按调用类型拆分
    expect(screen.getByText("按模型")).toBeInTheDocument();
    expect(screen.getByText("按调用类型")).toBeInTheDocument();
    expect(screen.getAllByText("gpt-4o").length).toBeGreaterThanOrEqual(2); // 拆分 + 表格
    expect(screen.getAllByText("上下文压缩").length).toBeGreaterThanOrEqual(1);

    // 逐次调用计量：已上报字段原样展示
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("exact")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // sparseCall.retry_count
  });

  it("可选字段未上报时标记「未上报」而不是 0", () => {
    render(<TokenObservatory calls={[fullCall, sparseCall]} />);
    // sparseCall 的 provider / ttft / 推理 / 缓存读 / 缓存写 / token 来源共 6 处
    expect(screen.getAllByText("未上报")).toHaveLength(6);
  });

  it("所有调用价格未配置：费用标记不可用，费用趋势空态", () => {
    render(
      <TokenObservatory
        calls={[
          makeCall({ id: "a", estimated_cost: null }),
          makeCall({ id: "b", estimated_cost: null, ended_at: "2026-07-25T01:00:02Z" }),
        ]}
      />,
    );
    expect(screen.getAllByText("价格未配置").length).toBeGreaterThanOrEqual(1); // 聚合指标
    expect(screen.getByText("价格未配置，暂无费用趋势")).toBeInTheDocument(); // 趋势图空态
    expect(screen.queryByLabelText("累计费用")).not.toBeInTheDocument();
  });

  it("无调用时展示空态", () => {
    render(<TokenObservatory calls={[]} />);
    expect(screen.getByText("暂无观测数据")).toBeInTheDocument();
  });
});
