"use client";

import { BarChart3, BriefcaseBusiness, Check, Code2, Gamepad2, Headphones, Lightbulb, Megaphone, Search, UsersRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { CATEGORY_LABELS } from "@/lib/team-presets";
import type { TeamPreset } from "@/lib/types";

interface PresetBrowserProps {
  presets: TeamPreset[];
  categories: string[];
  category: string;
  selectedId: string | null;
  onCategoryChange: (category: string) => void;
  onSelect: (preset: TeamPreset) => void;
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  general: UsersRound,
  software: Code2,
  game: Gamepad2,
  business: BriefcaseBusiness,
  content: Megaphone,
  research: Search,
  data: BarChart3,
  support: Headphones,
};

export function PresetBrowser({ presets, categories, category, selectedId, onCategoryChange, onSelect }: PresetBrowserProps) {
  const visible = category === "all" ? presets : presets.filter((preset) => preset.category === category);
  return (
    <section className="surface overflow-hidden">
      <div className="border-b border-border px-5 py-5 sm:px-7"><div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent"><Lightbulb className="h-4 w-4" /></span><div><h2 className="text-xl font-semibold tracking-[-0.025em]">浏览开箱即用团队</h2><p className="mt-1 text-sm text-muted-foreground">按场景选择，无需理解 Agent 框架或配置文件。</p></div></div></div>
      <div className="overflow-x-auto border-b border-border px-4 sm:px-6"><div role="tablist" aria-label="团队分类" className="flex min-w-max gap-1 py-2">{["all", ...categories].map((item) => <button key={item} type="button" role="tab" aria-selected={category === item} onClick={() => onCategoryChange(item)} className={`min-h-9 rounded-lg px-3 text-xs font-semibold ${category === item ? "bg-accent text-white shadow-control" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{CATEGORY_LABELS[item] ?? item}</button>)}</div></div>
      <div className="divide-y divide-border">
        {visible.map((preset) => {
          const Icon = CATEGORY_ICONS[preset.category] ?? UsersRound;
          const selected = preset.id === selectedId;
          return <button key={preset.id} type="button" onClick={() => onSelect(preset)} aria-pressed={selected} className={`flex w-full items-start gap-4 p-5 text-left sm:px-7 ${selected ? "bg-accent/[0.045]" : "hover:bg-muted/35"}`}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${selected ? "bg-accent text-white" : "bg-muted text-accent"}`}><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><span className="font-semibold">{preset.name}</span><span className="text-xs text-muted-foreground">{preset.roles.length} 个角色</span></span><span className="mt-1.5 block text-sm leading-relaxed text-muted-foreground">{preset.summary}</span><span className="mt-2 block text-xs font-medium text-accent">适合：{preset.best_for}</span></span>{selected ? <Check className="mt-2 h-4 w-4 shrink-0 text-accent" /> : null}</button>;
        })}
      </div>
    </section>
  );
}
