"use client";

// BudgetLoop Design System — 交付版浅蓝主题（见 design-system/budgetloop/MASTER.md）
// 基础原语：进度条、空态、键值行、标签页
import { ReactNode } from "react";

/* ── 进度条 ── */

export function ProgressBar({
  ratio,
  color = "bg-accent",
  track = "bg-muted",
  height = "h-2",
}: {
  ratio: number;
  color?: string;
  track?: string;
  height?: string;
}) {
  const pct = Math.max(0, Math.min(1, ratio)) * 100;
  return (
    <div className={`w-full overflow-hidden rounded-full ${track} ${height}`}>
      <div
        className={`${height} rounded-full ${color} transition-all duration-500`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/* ── 空态 ── */

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      {icon && <div className="text-muted-foreground">{icon}</div>}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {hint && <p className="text-xs text-muted-foreground max-w-sm">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/* ── 键值行 ── */

export function KeyValue({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-0.5">
      <dt className="shrink-0 text-xs text-muted-foreground">{k}</dt>
      <dd className="text-right text-xs font-medium text-foreground break-all">
        {v}
      </dd>
    </div>
  );
}

/* ── 标签页 ── */

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  ariaLabel,
}: {
  tabs: { key: T; label: string; count?: number }[];
  active: T;
  onChange: (key: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="flex overflow-x-auto border-b border-border px-2" role="tablist" aria-label={ariaLabel}>
      {tabs.map((item) => (
        <button
          key={item.key}
          role="tab"
          aria-selected={active === item.key}
          onClick={() => onChange(item.key)}
          className={`relative min-h-12 shrink-0 px-4 text-sm font-semibold ${
            active === item.key
              ? "text-accent"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {item.label}
          {typeof item.count === "number" ? (
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs">{item.count}</span>
          ) : null}
          {active === item.key ? (
            <span className="absolute inset-x-4 bottom-0 h-0.5 bg-accent" />
          ) : null}
        </button>
      ))}
    </div>
  );
}
