import { ExternalLink, GitFork, ShieldCheck } from "lucide-react";
import { compactStars } from "@/lib/team-presets";
import type { TeamPresetSource } from "@/lib/types";

export function PresetSources({ sources }: { sources: TeamPresetSource[] }) {
  return (
    <section className="rounded-xl border border-border bg-background p-4 sm:p-5">
      <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" /><div><h3 className="text-sm font-semibold">高 Star 开源方案来源</h3><p className="mt-1 text-xs leading-relaxed text-muted-foreground">LangGraph 直接承担图运行；其他项目用于兼容 schema 与协作模式。无需另装框架或填写 Provider Key。</p></div></div>
      <div className="mt-4 flex flex-wrap gap-2">{sources.map((source) => <a key={source.repository} href={source.url} target="_blank" rel="noreferrer" className="group inline-flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-xs shadow-control hover:border-accent/30"><GitFork className="h-3.5 w-3.5 text-accent" /><span className="font-semibold">{source.repository.split("/").at(-1)}</span><span className="text-muted-foreground">★ {compactStars(source.reviewed_stars)}</span><span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${source.integration === "runtime" ? "bg-accent/10 text-accent" : "bg-muted text-muted-foreground"}`}>{source.integration === "runtime" ? "直接运行" : "模式来源"}</span><ExternalLink className="h-3 w-3 text-muted-foreground group-hover:text-accent" /></a>)}</div>
    </section>
  );
}
