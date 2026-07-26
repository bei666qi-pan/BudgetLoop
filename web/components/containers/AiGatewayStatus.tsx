import Link from "next/link";
import { Bot, ExternalLink, Route, Settings2, ShieldCheck, Sparkles } from "lucide-react";
import { safeGatewayConsoleUrl } from "@/lib/team-presets";
import type { AIGatewayStatus, TeamPresetRecommendationResponse } from "@/lib/types";

interface AiGatewayStatusProps {
  status: AIGatewayStatus | null;
  statusError: string | null;
  recommendation: TeamPresetRecommendationResponse | null;
}

const REASON_TEXT: Record<string, string> = {
  ai_disabled: "AI 推荐已关闭",
  invalid_gateway_type: "网关类型无效",
  invalid_or_missing_gateway_url: "尚未配置网关地址",
  missing_gateway_key: "尚未配置网关 Token",
  missing_recommendation_model: "尚未配置推荐模型别名",
  timeout: "AI 网关响应超时",
  authentication_failed: "网关认证未通过",
  rate_limited: "网关当前限流",
  upstream_unavailable: "上游模型暂不可用",
  gateway_unreachable: "暂时无法连接 AI 网关",
  gateway_rejected_request: "网关拒绝了本次请求",
  response_too_large: "AI 返回内容超过安全限制",
  invalid_gateway_response: "网关响应格式无效",
  invalid_ai_json: "AI 返回内容不是有效 JSON",
  invalid_ai_schema: "AI 返回结构未通过校验",
  invalid_ai_item_count: "AI 推荐数量未通过校验",
  untrusted_or_duplicate_preset: "AI 引用了未知或重复模板",
  invalid_ai_output: "AI 推荐未通过本地校验",
};

export function AiGatewayStatus({ status, statusError, recommendation }: AiGatewayStatusProps) {
  const consoleUrl = safeGatewayConsoleUrl(status);
  const runtimeFallback = recommendation?.source === "local_fallback";
  const aiResult = recommendation?.source === "ai";
  const aiReady = Boolean(status?.healthy && status.recommendation_enabled);

  let title = "正在检查 AI 网关";
  let detail = "无论网关状态如何，本地推荐都会保持可用。";
  let tone = "text-muted-foreground";
  let Icon = Bot;

  if (aiResult) {
    title = "AI 已完成推荐 · 本地目录已校验";
    detail = "只接受内置可信团队模板，不展示或保存隐藏推理。";
    tone = "text-success";
    Icon = ShieldCheck;
  } else if (runtimeFallback) {
    const reason = recommendation.fallback_reason
      ? REASON_TEXT[recommendation.fallback_reason] ?? "AI 推荐未成功"
      : "AI 推荐未成功";
    title = "已自动切换到本地推荐";
    detail = `${reason}；团队创建功能不受影响。`;
    tone = "text-warning";
    Icon = Route;
  } else if (aiReady) {
    title = `AI 智能推荐已就绪 · ${status?.deployment_label ?? status?.provenance?.name ?? status?.type ?? "网关"}`;
    detail = status?.managed_app_runtime.enabled
      ? "提交目标时仅发送推荐字段；生成的服务端 AI 应用默认继承受限代理能力，不复制上游密钥。"
      : "提交目标时仅发送推荐字段；AI 应用自动继承已关闭，不会注入代理凭据。";
    tone = "text-accent";
    Icon = Sparkles;
  } else if (statusError) {
    title = "当前使用本地推荐";
    detail = "网关状态暂不可用；仍可直接创建完整团队。";
    tone = "text-warning";
    Icon = Route;
  } else if (status) {
    title = "当前使用本地推荐";
    detail = `${status.reason_code ? REASON_TEXT[status.reason_code] ?? "AI 网关尚未就绪" : "AI 网关尚未就绪"}；配置完成后会自动优先使用 AI。`;
    tone = "text-muted-foreground";
    Icon = Route;
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-2.5" role="status" aria-live="polite">
        <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white shadow-control ${tone}`}>
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="min-w-0">
          <strong className={`block text-xs font-semibold ${tone}`}>{title}</strong>
          <span className="mt-0.5 block max-w-2xl text-xs leading-relaxed text-muted-foreground">{detail}</span>
        </span>
      </div>
      <span className="flex flex-wrap items-center gap-1">
        <Link href="/settings/ai" className="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-accent hover:bg-accent/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30">
          AI 设置 <Settings2 className="h-3.5 w-3.5" />
        </Link>
        {consoleUrl ? (
          <a href={consoleUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-accent hover:bg-accent/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30">
            管理 AI 网关 <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}
      </span>
    </div>
  );
}
