"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Check, KeyRound, LoaderCircle, Network, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { AIGatewaySettings, AIGatewayStatus } from "@/lib/types";

type NativeGatewaySaveResult = {
  id: string;
  ok: boolean;
  settings?: AIGatewaySettings;
  message?: string;
};

type NativeGatewayBridge = {
  postMessage: (payload: {
    id: string;
    settings: Omit<AIGatewaySettings, "secret_configured" | "secret_store">;
    api_key: string | null;
  }) => void;
};

type NativeBridgeWindow = Window & {
  webkit?: { messageHandlers?: { budgetloopSaveGatewaySettings?: NativeGatewayBridge } };
};

const EMPTY: AIGatewaySettings = {
  kind: "compatible",
  base_url: "",
  console_url: "",
  recommendation_model: "",
  default_model: "",
  deployment_label: "",
  network_label: "",
  reasoning_effort: "",
  thinking_enabled: false,
  thinking_budget_tokens: 0,
  managed_app_inheritance_enabled: true,
  secret_configured: false,
  secret_store: "macos_keychain",
};

const STATUS_REASON: Record<string, string> = {
  timeout: "连接安全网关超时，请确认网络接入已连接后重试。",
  gateway_unreachable: "无法到达安全网关，请确认网络接入已连接。",
  authentication_failed: "网关认证未通过，可在上方更换 API Key。",
  rate_limited: "网关当前限流，稍后可再次检查。",
  upstream_unavailable: "上游模型服务暂不可用。",
  missing_gateway_key: "尚未配置 API Key。",
  missing_recommendation_model: "尚未配置团队推荐模型。",
};

function nativeGatewayBridge(): NativeGatewayBridge | undefined {
  return (window as NativeBridgeWindow).webkit?.messageHandlers?.budgetloopSaveGatewaySettings;
}

function saveThroughNativeBridge(
  bridge: NativeGatewayBridge,
  settings: Omit<AIGatewaySettings, "secret_configured" | "secret_store">,
  apiKey: string,
): Promise<AIGatewaySettings> {
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const onResult = (event: Event) => {
      const result = (event as CustomEvent<NativeGatewaySaveResult>).detail;
      if (!result || result.id !== id) return;
      window.removeEventListener("budgetloopGatewaySettingsSaved", onResult);
      if (result.ok && result.settings) {
        resolve(result.settings);
      } else {
        reject(new Error(result.message || "本机安全存储未能保存设置"));
      }
    };
    window.addEventListener("budgetloopGatewaySettingsSaved", onResult);
    bridge.postMessage({ id, settings, api_key: apiKey || null });
  });
}

export default function AISettingsPage() {
  const [form, setForm] = useState<AIGatewaySettings>(EMPTY);
  const [status, setStatus] = useState<AIGatewayStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [saved, health] = await Promise.all([
        apiFetch<AIGatewaySettings>("/api/ai-gateway/settings"),
        apiFetch<AIGatewayStatus>("/api/ai-gateway/status"),
      ]);
      setForm(saved);
      setStatus(health);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法读取 AI 设置");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        kind: form.kind,
        base_url: form.base_url,
        console_url: form.console_url,
        recommendation_model: form.recommendation_model,
        default_model: form.default_model,
        deployment_label: form.deployment_label,
        network_label: form.network_label,
        reasoning_effort: form.reasoning_effort,
        thinking_enabled: form.thinking_enabled,
        thinking_budget_tokens: form.thinking_enabled ? form.thinking_budget_tokens : 0,
        managed_app_inheritance_enabled: form.managed_app_inheritance_enabled,
      };
      const bridge = nativeGatewayBridge();
      const saved = bridge
        ? await saveThroughNativeBridge(bridge, payload, apiKey)
        : await apiFetch<AIGatewaySettings>("/api/ai-gateway/settings", {
            method: "PUT",
            body: JSON.stringify({ ...payload, api_key: apiKey || null }),
          });
      setForm(saved);
      setApiKey("");
      if (bridge) {
        setMessage("已安全保存并应用到这台 Mac；密钥不会回显，之后也无需再次填写。");
        const health = await apiFetch<AIGatewayStatus>("/api/ai-gateway/status");
        setStatus(health);
      } else {
        setMessage("设置已安全保存；密钥不会回显。正在重新检查连接。 ");
        const health = await apiFetch<AIGatewayStatus>("/api/ai-gateway/status");
        setStatus(health);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const update = <K extends keyof AIGatewaySettings>(key: K, value: AIGatewaySettings[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="page-shell">
      <div className="max-w-3xl">
        <h1 className="page-heading">AI 网关与应用继承</h1>
        <p className="page-subtitle">连接你有权使用的 OpenAI 兼容网关。地址、模型和网络标签只属于当前安装，不会成为 BudgetLoop 产品默认值。</p>
      </div>

      {loading ? <section className="surface mt-8 p-8"><LoaderCircle className="h-5 w-5 animate-spin text-accent" /><p className="mt-3 text-sm text-muted-foreground">正在读取安全设置…</p></section> : (
        <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="surface overflow-hidden">
            <div className="border-b border-border px-5 py-5 sm:px-7"><h2 className="section-title">连接配置</h2><p className="mt-1 text-sm text-muted-foreground">所有字段都可在网页修改，没有供应商硬编码。</p></div>
            <div className="grid gap-5 p-5 sm:grid-cols-2 sm:p-7">
              <label className="block"><span className="field-label">网关类型</span><select className="input-base mt-2 w-full" value={form.kind} onChange={(event) => update("kind", event.target.value as AIGatewaySettings["kind"])}><option value="compatible">OpenAI 兼容</option><option value="new-api">New API</option><option value="litellm">LiteLLM</option></select></label>
              <label className="block"><span className="field-label">部署名称</span><input className="input-base mt-2 w-full" value={form.deployment_label} onChange={(event) => update("deployment_label", event.target.value)} placeholder="例如：企业内部模型" /></label>
              <label className="block sm:col-span-2"><span className="field-label">API Base URL</span><input type="url" className="input-base mt-2 w-full font-mono text-sm" value={form.base_url} onChange={(event) => update("base_url", event.target.value)} placeholder="https://gateway.example/v1" /></label>
              <label className="block"><span className="field-label">默认模型</span><input className="input-base mt-2 w-full font-mono text-sm" value={form.default_model} onChange={(event) => update("default_model", event.target.value)} /></label>
              <label className="block"><span className="field-label">团队推荐模型</span><input className="input-base mt-2 w-full font-mono text-sm" value={form.recommendation_model} onChange={(event) => update("recommendation_model", event.target.value)} /></label>
              <label className="block"><span className="field-label">网络接入名称</span><input className="input-base mt-2 w-full" value={form.network_label} onChange={(event) => update("network_label", event.target.value)} placeholder="例如：企业安全接入" /></label>
              <label className="block"><span className="field-label">管理控制台（可选）</span><input type="url" className="input-base mt-2 w-full" value={form.console_url} onChange={(event) => update("console_url", event.target.value)} /></label>
              <label className="block sm:col-span-2"><span className="field-label">API Key</span><input aria-label="API Key" type="password" autoComplete="new-password" className="input-base mt-2 w-full font-mono text-sm" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={form.secret_configured ? "已安全保存；留空表示不更换" : "输入后写入系统安全存储"} /><span className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground"><KeyRound className="h-3.5 w-3.5" />{form.secret_configured ? "密钥已配置，页面不会读取或回显" : "尚未配置密钥"}</span></label>
            </div>

            <div className="border-t border-border bg-muted/20 p-5 sm:p-7">
              <h2 className="section-title">推理与思考</h2>
              <div className="mt-5 grid gap-5 sm:grid-cols-2">
                <label className="block"><span className="field-label">推理努力档位</span><select className="input-base mt-2 w-full" value={form.reasoning_effort} onChange={(event) => update("reasoning_effort", event.target.value as AIGatewaySettings["reasoning_effort"])}><option value="">网关默认</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="max">最大</option></select></label>
                <label className="block"><span className="field-label">思考 Token 上限</span><input type="number" min={0} max={65536} disabled={!form.thinking_enabled} className="input-base mt-2 w-full" value={form.thinking_budget_tokens} onChange={(event) => update("thinking_budget_tokens", Number(event.target.value))} /></label>
              </div>
              <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-white p-4"><input type="checkbox" className="mt-1 h-4 w-4 accent-accent" checked={form.thinking_enabled} onChange={(event) => update("thinking_enabled", event.target.checked)} /><span><strong className="block text-sm">启用模型思考模式</strong><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">只传递配置字段；隐藏思考内容不会进入公开对话或日志。</span></span></label>
            </div>

            <div className="border-t border-border p-5 sm:p-7">
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-accent/20 bg-accent/5 p-4"><input type="checkbox" className="mt-1 h-4 w-4 accent-accent" checked={form.managed_app_inheritance_enabled} onChange={(event) => update("managed_app_inheritance_enabled", event.target.checked)} /><span><strong className="block text-sm text-foreground">AI 应用自动继承 BudgetLoop AI 能力</strong><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">默认开启。生成的服务端应用获得短期受限凭据，不需要项目 `.env` API Key；浏览器代码仍通过应用自己的服务端调用。</span></span></label>
              {error ? <p role="alert" className="mt-4 flex items-start gap-2 text-sm text-critical"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p> : null}
              {message ? <p role="status" className="mt-4 flex items-start gap-2 text-sm text-success"><Check className="mt-0.5 h-4 w-4 shrink-0" />{message}</p> : null}
              <button type="button" onClick={() => void save()} disabled={saving || !form.base_url || !form.default_model || !form.recommendation_model} className="btn btn-primary mt-5 min-h-11">{saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{saving ? "安全保存中…" : "安全保存并检查连接"}</button>
            </div>
          </section>

          <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
            <section className="surface p-5"><div className="flex items-center gap-2"><Network className="h-4 w-4 text-accent" /><h2 className="section-title">当前状态</h2></div><dl className="mt-5 space-y-4 text-sm"><div><dt className="text-xs text-muted-foreground">连接</dt><dd className={`mt-1 font-semibold ${status?.healthy ? "text-success" : "text-warning"}`}>{status?.healthy ? "已就绪" : "尚未连通"}</dd>{!status?.healthy && status?.reason_code ? <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{status.network_label ? `${status.network_label}：` : ""}{STATUS_REASON[status.reason_code] ?? "请检查网关配置后重试。"}</p> : null}</div><div><dt className="text-xs text-muted-foreground">部署 / 网络</dt><dd className="mt-1">{status?.deployment_label || "未命名"} · {status?.network_label || "普通网络"}</dd></div><div><dt className="text-xs text-muted-foreground">模型</dt><dd className="mt-1 break-all font-mono text-xs">{status?.default_model || "未配置"}</dd></div><div><dt className="text-xs text-muted-foreground">思考策略</dt><dd className="mt-1">{status?.reasoning_effort ? `努力 ${status.reasoning_effort}` : "网关默认"}{status?.thinking_enabled ? ` · 已启用（${status.thinking_budget_tokens}）` : " · 未启用"}</dd></div></dl></section>
            <section className="rounded-xl border border-success/20 bg-success/5 p-5"><h2 className="flex items-center gap-2 text-sm font-semibold text-success"><ShieldCheck className="h-4 w-4" />密钥边界</h2><p className="mt-2 text-xs leading-relaxed text-muted-foreground">上游密钥保留在 BudgetLoop/系统安全存储中，不写入生成项目。应用继承开关关闭后，新工作区不会获得代理凭据。</p></section>
          </aside>
        </div>
      )}
    </div>
  );
}
