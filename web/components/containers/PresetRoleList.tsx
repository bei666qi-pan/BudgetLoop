"use client";

import { Bot, ChevronDown, Sparkles } from "lucide-react";
import type { TeamPreset, TeamRoleDraft } from "@/lib/types";

interface RoleEngineOption {
  id: string;
  name: string;
  runtime_available: boolean;
}

interface PresetRoleListProps {
  preset: TeamPreset;
  roles: TeamRoleDraft[];
  engines: RoleEngineOption[];
  budgetMode?: "bounded" | "max";
  onChange: (roles: TeamRoleDraft[]) => void;
}

export function PresetRoleList({ preset, roles, engines, budgetMode = "bounded", onChange }: PresetRoleListProps) {
  function update(key: string, patch: Partial<TeamRoleDraft>) {
    onChange(roles.map((role) => role.key === key ? { ...role, ...patch } : role));
  }

  return (
    <section className="surface overflow-hidden">
      <div className="border-b border-border px-5 py-5 sm:px-7"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="section-title">团队角色</h2><p className="mt-1 text-sm text-muted-foreground">已按「{preset.coordination_pattern}」预组装，可在安全范围内修改。</p></div><span className="text-xs font-semibold text-muted-foreground">已启用 {roles.filter((role) => role.enabled).length} / {roles.length}</span></div></div>
      <div className="divide-y divide-border">
        {roles.map((role, index) => (
          <details key={role.key} className="group" open={index === 0}>
            <summary className="flex cursor-pointer list-none items-start gap-3 px-5 py-4 hover:bg-muted/25 sm:px-7 [&::-webkit-details-marker]:hidden">
              <label onClick={(event) => event.stopPropagation()} className="relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center"><input type="checkbox" checked={role.enabled} onChange={(event) => update(role.key, { enabled: event.target.checked })} aria-label={`启用${role.role}`} className="peer h-5 w-5 appearance-none rounded-md border border-border-strong bg-white checked:border-accent checked:bg-accent" /><svg aria-hidden="true" viewBox="0 0 16 16" className="pointer-events-none absolute h-3.5 w-3.5 stroke-white opacity-0 peer-checked:opacity-100"><path d="m3 8 3 3 7-7" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></label>
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${role.enabled ? "bg-accent/10 text-accent" : "bg-muted text-muted-foreground"}`}><Bot className="h-4 w-4" /></span>
              <span className={`min-w-0 flex-1 ${role.enabled ? "" : "opacity-55"}`}><span className="flex flex-wrap items-center gap-2"><span className="font-semibold">{role.role}</span>{role.optional ? <span className="badge badge-muted">可选</span> : null}</span><span className="mt-1 block text-sm leading-relaxed text-muted-foreground">{role.goal}</span><span className="mt-2 flex flex-wrap gap-1.5">{preset.roles.find((item) => item.key === role.key)?.skills.map((skill) => <span key={skill} className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"><Sparkles className="h-2.5 w-2.5" />{skill}</span>)}</span></span>
              <ChevronDown className="mt-2 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
            </summary>
            <div className="border-t border-border/70 bg-muted/20 px-5 py-5 sm:px-7">
              <div className="grid gap-4 sm:grid-cols-3"><label><span className="field-label">角色名称</span><input value={role.role} disabled={!role.enabled} maxLength={120} onChange={(event) => update(role.key, { role: event.target.value })} className="input-base mt-2 w-full" /></label><label><span className="field-label">执行引擎</span><select value={role.execution_engine} disabled={!role.enabled} onChange={(event) => update(role.key, { execution_engine: event.target.value })} className="input-base mt-2 w-full">{engines.map((engine) => <option key={engine.id} value={engine.id}>{engine.name}{engine.runtime_available ? "" : "（待启用）"}</option>)}</select></label><label><span className="field-label">{budgetMode === "max" ? "起始 Token 估算（Max 不限额）" : "启动 Token 上限"}</span><input type="number" min={1} max={200000} value={role.budget.max_total_tokens} disabled={!role.enabled} onChange={(event) => update(role.key, { budget: { ...role.budget, max_total_tokens: Number(event.target.value) } })} className="input-base mt-2 w-full tabular-nums" /></label></div>
              <label className="mt-4 block"><span className="field-label">独立目标</span><textarea value={role.goal} disabled={!role.enabled} maxLength={10000} rows={3} onChange={(event) => update(role.key, { goal: event.target.value })} className="input-base mt-2 w-full resize-y" /></label>
              <p className="mt-3 text-xs leading-relaxed text-muted-foreground">此角色拥有独立对话、私有上下文、运行状态和预算。Skills 是工作方法提示，不会授予额外权限。</p>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
