"use client";

import { AlertCircle, Clock3 } from "lucide-react";
import { BudgetLoopActivityMark } from "@/components/brand/BudgetLoopActivityMark";
import { elapsedStartupTime, sessionStartupPresentation } from "@/lib/session-startup-presentation";
import type { WorkSessionSummary } from "@/lib/types";

export function SessionStartupFeedback({ session }: { session: WorkSessionSummary }) {
  const presentation = sessionStartupPresentation(session);
  if (!presentation.state) return null;
  const elapsed = elapsedStartupTime(session.run_started_at ?? null);
  if (presentation.state === "failed") {
    return <section role="alert" className="border-b border-critical/20 bg-critical/5 px-5 py-4 sm:px-6"><div className="flex items-start gap-3"><AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-critical" aria-hidden="true" /><div className="min-w-0"><h3 className="text-sm font-semibold text-critical">{presentation.label}</h3><p className="mt-1 text-xs leading-5 text-critical/90">{presentation.error}</p><p className="mt-2 text-xs leading-5 text-muted-foreground">{presentation.detail}</p></div></div></section>;
  }
  return <section aria-label="Session 启动进度" className="border-b border-accent/15 bg-accent/[0.035] px-5 py-4 sm:px-6"><div className="flex items-center gap-3"><span className="text-accent"><BudgetLoopActivityMark compact label={presentation.label} /></span><div className="min-w-0"><p className="text-sm font-semibold text-foreground">{presentation.label}</p><p className="mt-0.5 text-xs leading-5 text-muted-foreground">{presentation.detail}</p></div>{elapsed ? <span className="ml-auto flex shrink-0 items-center gap-1 text-[11px] font-medium text-muted-foreground"><Clock3 className="h-3.5 w-3.5" aria-hidden="true" />{elapsed}</span> : null}</div></section>;
}
