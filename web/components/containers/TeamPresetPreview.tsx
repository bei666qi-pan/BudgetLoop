"use client";

import { ArrowRight, Clock3, Coins, LoaderCircle, Play, Sparkles, UsersRound } from "lucide-react";
import { aggregateTeamBudget } from "@/lib/team-presets";
import type { TeamPreset, TeamRoleDraft } from "@/lib/types";

interface TeamPresetPreviewProps {
  preset: TeamPreset;
  roles: TeamRoleDraft[];
  teamMode: "guided" | "autonomous";
  budgetMode: "bounded" | "max";
  valid: boolean;
  startValid: boolean;
  busyAction: "start" | "later" | null;
  error: string | null;
  onSubmit: (startImmediately: boolean) => void;
}

export function TeamPresetPreview({ preset, roles, teamMode, budgetMode, valid, startValid, busyAction, error, onSubmit }: TeamPresetPreviewProps) {
  const enabled = roles.filter((role) => role.enabled);
  const total = aggregateTeamBudget(roles);
  return (
    <aside className="fixed inset-x-3 bottom-3 z-40 rounded-2xl border border-border bg-white/95 p-3 shadow-elevated backdrop-blur-xl xl:sticky xl:inset-auto xl:top-24 xl:z-auto xl:self-start xl:p-5">
      <div className="hidden xl:block"><span className="text-xs font-semibold text-accent">团队预览</span><h2 className="mt-2 text-lg font-semibold tracking-tight">{preset.name}</h2><p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{preset.summary}</p><div className="my-5 h-px bg-border" /><div className="space-y-3">{enabled.map((role) => <div key={role.key} className="flex items-center gap-3"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted text-xs font-bold text-accent">{role.role.slice(0, 1)}</span><span className="min-w-0 flex-1 truncate text-sm font-medium">{role.role}</span><span className="text-xs tabular-nums text-muted-foreground">{Math.round(role.budget.max_total_tokens / 1000)}k</span></div>)}</div><div className="my-5 h-px bg-border" /></div>
      <div className="grid grid-cols-3 gap-2 rounded-xl bg-muted/55 p-3 text-center xl:grid-cols-1 xl:gap-3 xl:bg-transparent xl:p-0 xl:text-left">
        <div className="xl:flex xl:items-center xl:justify-between"><span className="flex items-center justify-center gap-1 text-[11px] text-muted-foreground xl:justify-start xl:text-xs"><UsersRound className="h-3.5 w-3.5" />角色</span><strong className="mt-1 block text-sm tabular-nums xl:mt-0">{enabled.length}</strong></div>
        <div className="xl:flex xl:items-center xl:justify-between"><span className="flex items-center justify-center gap-1 text-[11px] text-muted-foreground xl:justify-start xl:text-xs"><Coins className="h-3.5 w-3.5" />Token</span><strong className="mt-1 block text-sm tabular-nums xl:mt-0">{budgetMode === "max" ? "Max" : `${Math.round(total.tokens / 1000)}k`}</strong></div>
        <div className="xl:flex xl:items-center xl:justify-between"><span className="flex items-center justify-center gap-1 text-[11px] text-muted-foreground xl:justify-start xl:text-xs"><Clock3 className="h-3.5 w-3.5" />调用</span><strong className="mt-1 block text-sm tabular-nums xl:mt-0">{total.calls}</strong></div>
      </div>
      {error ? <p role="alert" className="mt-2 rounded-lg bg-critical/5 px-3 py-2 text-xs text-critical xl:mt-4">{error}</p> : null}
      <div className="mt-3 grid grid-cols-[1fr_auto] gap-2 xl:mt-5 xl:grid-cols-1">
        <button type="button" disabled={!valid || !startValid || busyAction !== null} onClick={() => onSubmit(true)} className="btn btn-primary min-h-11"><span>{busyAction === "start" ? "正在创建…" : "一键创建并启动"}</span>{busyAction === "start" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <><Play className="hidden h-4 w-4 sm:block" /><ArrowRight className="h-4 w-4" /></>}</button>
        <button type="button" disabled={!valid || busyAction !== null} onClick={() => onSubmit(false)} className="btn btn-secondary min-h-11 px-3 xl:w-full">{busyAction === "later" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}<span className="hidden sm:inline">仅创建，稍后启动</span><span className="sm:hidden">仅创建</span></button>
      </div>
      <p className="mt-2 hidden text-center text-[11px] leading-relaxed text-muted-foreground xl:block">{teamMode === "autonomous" ? <span className="inline-flex items-center gap-1"><Sparkles className="h-3 w-3" />自主阶段协作与自动 Handoff 已启用。</span> : "创建前不会产生模型调用。"} {budgetMode === "max" ? "Max 不会自动停止；审批与手动停止仍然有效。" : "所有角色保留审批与硬预算。"}</p>
    </aside>
  );
}
