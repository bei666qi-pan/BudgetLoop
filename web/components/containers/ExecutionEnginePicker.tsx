"use client";

import { Check, Code2, ExternalLink, Server, TerminalSquare } from "lucide-react";
import { compactStars } from "@/lib/team-presets";
import type { ExecutionEngineInfo } from "@/lib/types";

interface ExecutionEnginePickerProps {
  engines: ExecutionEngineInfo[];
  selectedId: string;
  onSelect: (engineId: string) => void;
}

export function ExecutionEnginePicker({ engines, selectedId, onSelect }: ExecutionEnginePickerProps) {
  return (
    <section className="surface overflow-hidden">
      <div className="border-b border-border px-5 py-5 sm:px-7"><div className="flex items-start gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent"><Server className="h-4 w-4" /></span><div><h2 className="section-title">选择执行引擎</h2><p className="mt-1 text-sm leading-relaxed text-muted-foreground">BudgetLoop 管理任务、预算、审批与 Handoff；执行引擎可以替换，不会成为业务事实来源。</p></div></div></div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-7">
        {engines.map((engine) => {
          const selected = selectedId === engine.id;
          const Icon = engine.transport === "server" ? Server : engine.id === "codex" ? Code2 : TerminalSquare;
          const readiness = engine.runtime_available
            ? engine.transport === "server" ? "服务已就绪" : engine.managed_ai_ready ? "已安装 · AI 继承就绪" : "已安装 · 独立凭据就绪"
            : engine.package_installed ? "已安装 · 配置待完成" : engine.source_downloaded ? "源码已内置 · 命令未安装" : "源码未下载";
          return <button key={engine.id} type="button" onClick={() => onSelect(engine.id)} aria-pressed={selected} className={`relative rounded-xl border p-4 text-left transition ${selected ? "border-accent/40 bg-accent/[0.045] ring-4 ring-accent/5" : "border-border hover:border-border-strong"}`}><span className="flex items-start justify-between gap-3"><span className={`flex h-9 w-9 items-center justify-center rounded-xl ${selected ? "bg-accent text-white" : "bg-muted text-accent"}`}><Icon className="h-4 w-4" /></span>{selected ? <Check className="h-4 w-4 text-accent" /> : null}</span><span className="mt-3 flex flex-wrap items-center gap-2"><strong className="text-sm">{engine.name}</strong>{engine.default ? <span className="badge badge-info">默认</span> : null}</span><span className="mt-1.5 block text-xs text-muted-foreground">{engine.repository} · ★ {compactStars(engine.reviewed_stars)} · {engine.license}</span><span className={`mt-3 inline-flex rounded-full px-2 py-1 text-[11px] font-semibold ${engine.runtime_available ? "bg-success/10 text-success" : engine.package_installed || engine.source_downloaded ? "bg-warning/10 text-warning" : "bg-critical/10 text-critical"}`}>{readiness}</span>{engine.runtime_available ? null : <span className="mt-2 block text-[11px] leading-relaxed text-muted-foreground">{engine.availability_reason}</span>}</button>;
        })}
      </div>
      <div className="border-t border-border bg-muted/20 px-5 py-3 text-xs text-muted-foreground sm:px-7"><span className="inline-flex items-center gap-1.5"><ExternalLink className="h-3.5 w-3.5" />所有引擎固定到已审计源码 revision；不可用时不会静默回退。</span></div>
    </section>
  );
}
