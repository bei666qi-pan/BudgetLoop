export function averageScore(scores: number[] | null | undefined): number | null {
  if (!Array.isArray(scores) || scores.length === 0) return null;
  return scores.reduce((sum, score) => sum + score, 0) / scores.length;
}

export type OutcomeTone = "success" | "warning" | "critical";
export function outcomeTone(status: string, acceptanceMet: boolean): OutcomeTone {
  if (acceptanceMet) return "success";
  if (["PARTIAL_COMPLETED", "BUDGET_EXHAUSTED"].includes(status)) return "warning";
  return "critical";
}
