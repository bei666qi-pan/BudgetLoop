"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, ArrowLeft, CheckCircle2, Download, FileCode2, GitBranch, Lightbulb, RefreshCw, XCircle } from "lucide-react";
import { apiFetch, downloadFile } from "@/lib/api";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/format";
import { STATUS_LABELS } from "@/lib/presentation";
import { averageScore, outcomeTone } from "@/lib/report-presentation";
import { ProgressBar } from "@/components/ui";
import type { RunDetail } from "@/lib/types";

interface ReportData {
  status: string;
  acceptance_result: { met: boolean; criteria?: string; last_test?: { passed: number; failed: number } };
  files_changed: string[];
  diff_summary?: string;
  totals: { iterations: number; active_runtime_ms: number; budget: Record<string, number>; scores: number[] };
  strategy_switches: { iteration: number; from: string; to: string; reason: string }[];
  open_issues: string[];
  suggestions: string[];
}

function safeArray<T>(value: T[] | undefined): T[] { return Array.isArray(value) ? value : []; }

function ResourceRow({ label, value, total, ratio }: { label: string; value: string; total?: string; ratio?: number }) {
  return <div className="grid items-center gap-3 border-b border-border py-3 last:border-0 sm:grid-cols-[140px_1fr_auto]"><span className="text-xs font-semibold text-muted-foreground">{label}</span>{typeof ratio === "number" ? <ProgressBar ratio={ratio} height="h-1.5" /> : <div />}<span className="font-mono font-semibold tabular-nums">{value}{total ? <span className="font-normal text-muted-foreground"> / {total}</span> : null}</span></div>;
}

export default function RunReportPage() {
  const runId = useParams<{ id: string }>().id;
  const [report, setReport] = useState<ReportData | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"json" | "md" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const [reportResult, runResult] = await Promise.allSettled([apiFetch<ReportData>(`/api/runs/${runId}/report`), apiFetch<RunDetail>(`/api/runs/${runId}`)]);
    if (reportResult.status === "fulfilled") setReport(reportResult.value);
    else { setReport(null); setError(reportResult.reason instanceof Error ? reportResult.reason.message : "报告尚未生成。"); }
    if (runResult.status === "fulfilled") setRun(runResult.value);
    setLoading(false);
  }, [runId]);

  useEffect(() => { void load(); }, [load]);

  const exportReport = async (format: "json" | "md") => {
    setExporting(format); setExportError(null);
    try { await downloadFile(`/api/runs/${runId}/report/export?format=${format}`, `budgetloop-${runId}.${format === "md" ? "md" : "json"}`); }
    catch (err) { setExportError(err instanceof Error ? err.message : "导出失败，请重试。"); }
    finally { setExporting(null); }
  };

  const scores = safeArray(report?.totals?.scores);
  const average = useMemo(() => averageScore(scores), [scores]);

  if (loading) return <div className="page-shell space-y-6" aria-busy="true"><div className="skeleton h-12 w-1/2" /><div className="grid gap-4 lg:grid-cols-2"><div className="skeleton h-72" /><div className="skeleton h-72" /></div><div className="skeleton h-72" /></div>;

  if (!report) return <div className="page-shell"><section className="surface mx-auto mt-20 max-w-xl p-8 text-center"><AlertCircle className="mx-auto h-9 w-9 text-warning" /><h1 className="mt-4 text-xl font-semibold">执行结果尚未生成</h1><p className="mt-2 text-sm leading-relaxed text-muted-foreground">运行可能仍在进行，或报告服务暂不可用。{error ? ` ${error}` : ""}</p><div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row"><button onClick={() => void load()} className="btn btn-primary"><RefreshCw className="h-4 w-4" />重新检查</button><Link href={`/runs/${runId}`} className="btn btn-secondary"><ArrowLeft className="h-4 w-4" />返回运行指挥台</Link></div></section></div>;

  const budget = report.totals?.budget ?? {};
  const passed = report.acceptance_result?.met;
  const partial = ["PARTIAL_COMPLETED", "BUDGET_EXHAUSTED"].includes(report.status);
  const tone = outcomeTone(report.status, passed);
  const outcomeIconClass = tone === "success" ? "bg-success/10 text-success" : tone === "warning" ? "bg-warning/10 text-warning" : "bg-critical/10 text-critical";
  const outcomeBadgeClass = tone === "success" ? "badge-success" : tone === "warning" ? "badge-warning" : "badge-critical";
  const OutcomeIcon = passed ? CheckCircle2 : partial ? AlertTriangle : XCircle;
  const files = safeArray(report.files_changed);
  const issues = safeArray(report.open_issues);
  const suggestions = safeArray(report.suggestions);
  const switches = safeArray(report.strategy_switches);

  return (
    <div className="page-shell animate-in space-y-6">
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><Link href="/" className="hover:text-accent">任务工作台</Link><span>/</span><Link href={`/runs/${runId}`} className="hover:text-accent">运行指挥台</Link><span>/</span><span>执行结果</span></div>
      <header className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end"><div><h1 className="page-heading">执行结果</h1><p className="mt-2 text-lg font-semibold">{run?.task.name ?? "BudgetLoop 任务"}</p><p className="mt-1 font-mono text-xs text-muted-foreground">{runId}</p></div><div className="flex flex-wrap gap-2"><Link href={`/runs/${runId}`} className="btn btn-secondary"><ArrowLeft className="h-4 w-4" />返回运行指挥台</Link><button onClick={() => void exportReport("json")} disabled={exporting !== null} className="btn btn-secondary"><Download className="h-4 w-4" />{exporting === "json" ? "导出中…" : "导出 JSON"}</button><button onClick={() => void exportReport("md")} disabled={exporting !== null} className="btn btn-primary"><Download className="h-4 w-4" />{exporting === "md" ? "导出中…" : "导出 Markdown"}</button></div></header>
      {exportError ? <div role="alert" className="rounded-lg border border-critical/20 bg-critical/5 p-3 text-sm text-critical">导出失败：{exportError}</div> : null}

      <section className="grid gap-4 lg:grid-cols-[1.05fr_.95fr]">
        <div className="surface p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-center gap-3"><span className={`flex h-12 w-12 items-center justify-center rounded-full ${outcomeIconClass}`}><OutcomeIcon className="h-6 w-6" /></span><div><span className={`badge ${outcomeBadgeClass}`}>{STATUS_LABELS[report.status] ?? report.status}</span><h2 className="mt-2 text-xl font-semibold">{passed ? "验收条件已满足" : partial ? "验收条件未完全满足" : "验收条件未满足"}</h2></div></div></div><p className="mt-4 text-sm leading-relaxed text-muted-foreground">{passed ? "任务目标已经达成，以下是可审阅的修改与资源证据。" : partial ? "Agent 已在预算内完成部分关键工作，但仍有验证或收尾事项需要处理。" : "本次运行未达到验收条件，请优先查看仍需处理的问题。"}</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-success/20 bg-success/5 p-4"><p className="flex items-center gap-2 font-semibold text-success"><CheckCircle2 className="h-4 w-4" />已达成的证据</p><p className="mt-2 text-sm">{report.acceptance_result.last_test ? `${report.acceptance_result.last_test.passed} 项测试通过` : files.length ? `${files.length} 个文件已修改` : "已记录本次执行产出"}</p></div><div className={`rounded-lg border p-4 ${issues.length ? "border-warning/20 bg-warning/5" : "border-success/20 bg-success/5"}`}><p className={`flex items-center gap-2 font-semibold ${issues.length ? "text-warning" : "text-success"}`}>{issues.length ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}{issues.length ? "未达成的证据" : "没有遗留问题"}</p><p className="mt-2 text-sm">{issues[0] ?? "报告未记录仍需处理的事项"}</p></div></div><div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 text-sm"><span className="font-semibold">验收条件：</span><span className="text-muted-foreground">{report.acceptance_result.criteria ?? run?.task.acceptance_criteria ?? "未显式设置"}</span></div>
        </div>

        <div className="surface p-5 sm:p-6"><h2 className="section-title">资源使用</h2><div className="mt-3"><ResourceRow label="迭代轮次" value={String(report.totals.iterations ?? 0)} /><ResourceRow label="活跃运行时间" value={formatDurationMs(report.totals.active_runtime_ms ?? 0)} /><ResourceRow label="Tokens 使用" value={formatTokens(budget.used_tokens ?? 0)} total={formatTokens(budget.max_total_tokens ?? 0)} ratio={(budget.used_tokens ?? 0) / Math.max(1, budget.max_total_tokens ?? 1)} /><ResourceRow label="费用" value={formatCost(budget.used_cost ?? 0)} total={formatCost(budget.max_cost ?? 0)} ratio={(budget.used_cost ?? 0) / Math.max(.01, budget.max_cost ?? 1)} /><ResourceRow label="调用次数" value={String(budget.used_calls ?? 0)} total={String(budget.max_llm_calls ?? "—")} ratio={(budget.used_calls ?? 0) / Math.max(1, budget.max_llm_calls ?? 1)} /><ResourceRow label="平均进展贡献" value={average === null ? "—" : average.toFixed(2)} ratio={average ?? 0} /></div></div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[.75fr_1.25fr_.85fr]">
        <div className="surface p-5"><h2 className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4 text-success" />完成了什么</h2><ul className="mt-4 space-y-2 text-sm text-muted-foreground">{files.length ? files.slice(0, 4).map((file) => <li key={file} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-success" /><span>已修改 <code className="font-mono text-foreground">{file}</code></span></li>) : <li>本次报告没有记录文件变更。</li>}</ul></div>
        <div className="surface p-5"><h2 className="flex items-center gap-2 font-semibold"><FileCode2 className="h-4 w-4 text-accent" />修改的文件</h2>{files.length ? <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[480px] text-sm"><thead><tr className="border-b border-border text-left text-xs text-muted-foreground"><th className="pb-2">文件路径</th><th className="pb-2">说明</th></tr></thead><tbody>{files.map((file) => <tr key={file} className="border-b border-border/70 last:border-0"><td className="py-3 pr-4 font-mono text-xs text-accent">{file}</td><td className="py-3 text-muted-foreground">由本次运行修改</td></tr>)}</tbody></table></div> : <p className="mt-4 text-sm text-muted-foreground">没有文件被修改。</p>}{report.diff_summary ? <details className="mt-4"><summary className="cursor-pointer text-sm font-semibold text-accent">查看 Git Diff 摘要</summary><pre className="code-block mt-3 max-h-72">{report.diff_summary}</pre></details> : null}</div>
        <div className="surface p-5"><h2 className="flex items-center gap-2 font-semibold"><GitBranch className="h-4 w-4 text-accent" />策略调整</h2>{switches.length ? <div className="mt-4 space-y-3">{switches.map((item, index) => <div key={`${item.iteration}-${index}`} className="rounded-lg border border-border bg-muted/30 p-3 text-sm"><p className="font-mono font-semibold text-accent">第 {item.iteration} 轮：{item.from} → {item.to}</p><p className="mt-2 text-xs leading-relaxed text-muted-foreground">{item.reason}</p></div>)}</div> : <p className="mt-4 text-sm text-muted-foreground">本次运行没有策略切换。</p>}</div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2"><div className="surface p-5"><h2 className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4 text-warning" />仍需处理</h2>{issues.length ? <ul className="mt-4 space-y-3 text-sm">{issues.map((issue) => <li key={issue} className="flex gap-3 rounded-lg border border-warning/15 bg-warning/5 p-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warning" /><span>{issue}</span></li>)}</ul> : <p className="mt-4 text-sm text-muted-foreground">没有遗留问题。</p>}</div><div className="surface p-5"><h2 className="flex items-center gap-2 font-semibold"><Lightbulb className="h-4 w-4 text-accent" />后续建议</h2>{suggestions.length ? <ul className="mt-4 space-y-3 text-sm">{suggestions.map((suggestion) => <li key={suggestion} className="flex gap-3 rounded-lg border border-accent/15 bg-accent/5 p-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" /><span>{suggestion}</span></li>)}</ul> : <p className="mt-4 text-sm text-muted-foreground">无需额外操作。</p>}</div></section>
    </div>
  );
}
