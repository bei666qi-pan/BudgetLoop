"use client";

import { ArrowRight, Check, WandSparkles } from "lucide-react";
import { AiGatewayStatus } from "@/components/containers/AiGatewayStatus";
import type { AIGatewayStatus, TeamPresetRecommendation, TeamPresetRecommendationResponse } from "@/lib/types";

interface GoalRecommenderProps {
  goal: string;
  industry: string;
  pace: "steady" | "fast";
  risk: "steady" | "balanced" | "creative";
  busy: boolean;
  recommendations: TeamPresetRecommendation[];
  gatewayStatus: AIGatewayStatus | null;
  gatewayStatusError: string | null;
  recommendationRuntime: TeamPresetRecommendationResponse | null;
  selectedId: string | null;
  onGoalChange: (value: string) => void;
  onIndustryChange: (value: string) => void;
  onPaceChange: (value: "steady" | "fast") => void;
  onRiskChange: (value: "steady" | "balanced" | "creative") => void;
  onRecommend: () => void;
  onSelect: (recommendation: TeamPresetRecommendation) => void;
}

const PACE_OPTIONS = [
  { value: "steady" as const, label: "稳健推进" },
  { value: "fast" as const, label: "快速出结果" },
];

const RISK_OPTIONS = [
  { value: "steady" as const, label: "低风险" },
  { value: "balanced" as const, label: "平衡" },
  { value: "creative" as const, label: "鼓励创意" },
];

export function GoalRecommender({
  goal,
  industry,
  pace,
  risk,
  busy,
  recommendations,
  gatewayStatus,
  gatewayStatusError,
  recommendationRuntime,
  selectedId,
  onGoalChange,
  onIndustryChange,
  onPaceChange,
  onRiskChange,
  onRecommend,
  onSelect,
}: GoalRecommenderProps) {
  return (
    <section className="surface overflow-hidden">
      <div className="border-b border-border bg-gradient-to-r from-background to-white px-5 py-5 sm:px-7 sm:py-6">
        <AiGatewayStatus status={gatewayStatus} statusError={gatewayStatusError} recommendation={recommendationRuntime} />
        <h2 className="mt-4 text-xl font-semibold tracking-[-0.025em] sm:text-2xl">你想让团队完成什么？</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">用自然语言描述目标。系统会组合合适角色、预算与协作阶段，你仍可在创建前调整。</p>
      </div>

      <div className="p-5 sm:p-7">
        <label className="block">
          <span className="sr-only">项目目标</span>
          <textarea
            autoFocus
            value={goal}
            onChange={(event) => onGoalChange(event.target.value)}
            rows={4}
            maxLength={10_000}
            placeholder="例如：在 4 周内做出一个可在手机上试玩的解谜游戏 Demo…"
            className="input-base min-h-32 w-full resize-y px-4 py-3 text-base leading-relaxed"
          />
        </label>
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(180px,1fr)_auto] lg:items-end">
          <label className="block">
            <span className="field-label">行业或场景 <span className="font-normal text-muted-foreground">（可选）</span></span>
            <input value={industry} onChange={(event) => onIndustryChange(event.target.value)} maxLength={100} placeholder="游戏、电商、软件、内容…" className="input-base mt-2 w-full" />
          </label>
          <button type="button" onClick={onRecommend} disabled={busy || goal.trim().length < 3} className="btn btn-primary min-h-11 lg:min-w-36">
            <WandSparkles className="h-4 w-4" />{busy ? "正在匹配…" : "智能推荐"}
          </button>
        </div>

        <details className="mt-4 rounded-lg border border-border bg-muted/25 px-4 py-3">
          <summary className="cursor-pointer select-none text-sm font-semibold text-foreground">可选偏好</summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <fieldset><legend className="text-xs font-semibold text-muted-foreground">节奏</legend><div className="mt-2 flex flex-wrap gap-2">{PACE_OPTIONS.map((option) => <button key={option.value} type="button" aria-pressed={pace === option.value} onClick={() => onPaceChange(option.value)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ring-1 ring-inset transition ${pace === option.value ? "bg-accent/10 text-accent ring-accent/25" : "bg-white text-muted-foreground ring-border hover:text-foreground"}`}>{option.label}</button>)}</div></fieldset>
            <fieldset><legend className="text-xs font-semibold text-muted-foreground">风险偏好</legend><div className="mt-2 flex flex-wrap gap-2">{RISK_OPTIONS.map((option) => <button key={option.value} type="button" aria-pressed={risk === option.value} onClick={() => onRiskChange(option.value)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ring-1 ring-inset transition ${risk === option.value ? "bg-accent/10 text-accent ring-accent/25" : "bg-white text-muted-foreground ring-border hover:text-foreground"}`}>{option.label}</button>)}</div></fieldset>
          </div>
        </details>

        {recommendations.length > 0 ? (
          <div className="mt-6" aria-live="polite">
            <div className="flex items-center justify-between gap-3"><h3 className="text-sm font-semibold">为你推荐</h3><span className="text-xs text-muted-foreground">{recommendationRuntime?.source === "ai" ? "AI 排序 · 本地目录校验" : "本地公开信号匹配"}，可随时更换</span></div>
            <div className="mt-3 divide-y divide-border rounded-xl border border-border bg-white">
              {recommendations.map((recommendation, index) => {
                const selected = recommendation.preset.id === selectedId;
                return (
                  <button key={recommendation.preset.id} type="button" onClick={() => onSelect(recommendation)} aria-pressed={selected} className={`group flex w-full items-start gap-4 p-4 text-left first:rounded-t-xl last:rounded-b-xl sm:p-5 ${selected ? "bg-accent/[0.045]" : "hover:bg-muted/35"}`}>
                    <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${selected ? "bg-accent text-white" : "bg-muted text-accent"}`}>{selected ? <Check className="h-4 w-4" /> : index + 1}</span>
                    <span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><span className="font-semibold">{recommendation.preset.name}</span>{index === 0 ? <span className="badge badge-info">最匹配 · {recommendation.confidence}%</span> : <span className="text-xs font-semibold text-muted-foreground">{recommendation.confidence}%</span>}</span><span className="mt-1.5 block text-sm leading-relaxed text-muted-foreground">{recommendation.reason}</span><span className="mt-2 flex flex-wrap gap-1.5">{recommendation.matched_signals.map((signal) => <span key={signal} className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">{signal}</span>)}</span></span>
                    <ArrowRight className="mt-2 h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-accent" />
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
