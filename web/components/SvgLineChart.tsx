"use client";

// 纯 SVG 折线图（燃尽趋势用）：无第三方依赖。
// x 为时间戳（ms），y 为累计用量；可选 maxY 参考线（预算上限）。
import { useId } from "react";
import { CHART_COLORS } from "@/lib/chart-colors";

export interface ChartPoint {
  x: number; // epoch ms
  y: number;
}

export default function SvgLineChart({
  points,
  maxY,
  height = 160,
  stroke = CHART_COLORS.accent,
  yLabel,
  formatY = (v: number) => String(v),
}: {
  points: ChartPoint[];
  maxY?: number | null;
  height?: number;
  stroke?: string;
  yLabel?: string;
  formatY?: (v: number) => string;
}) {
  const gradientId = useId();
  const W = 640;
  const H = height;
  const padL = 48;
  const padR = 12;
  const padT = 14;
  const padB = 24;

  if (points.length < 2) {
    return (
      <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
        数据点不足，趋势图将在运行产生更多事件后显示
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMax = Math.max(maxY ?? 0, ...ys) * 1.05 || 1;

  const sx = (x: number) =>
    padL + ((x - xMin) / Math.max(1, xMax - xMin)) * (W - padL - padR);
  const sy = (y: number) => padT + (1 - y / yMax) * (H - padT - padB);

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`)
    .join(" ");
  const area = `${path} L${sx(xMax).toFixed(1)},${sy(0).toFixed(1)} L${sx(xMin).toFixed(1)},${sy(0).toFixed(1)} Z`;

  const gridYs = [0, 0.25, 0.5, 0.75, 1].map((r) => r * yMax);
  const fmtTime = (t: number) =>
    new Date(t).toLocaleTimeString("zh-CN", { hour12: false });

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label={yLabel ?? "趋势图"}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {gridYs.map((v) => (
        <g key={v}>
          <line
            x1={padL}
            x2={W - padR}
            y1={sy(v)}
            y2={sy(v)}
            stroke={CHART_COLORS.grid}
            strokeWidth="1"
          />
          <text
            x={padL - 6}
            y={sy(v) + 3}
            textAnchor="end"
            fontSize="9"
            fill={CHART_COLORS.label}
          >
            {formatY(Math.round(v))}
          </text>
        </g>
      ))}

      <text x={padL} y={H - 8} fontSize="9" fill={CHART_COLORS.label}>
        {fmtTime(xMin)}
      </text>
      <text x={W - padR} y={H - 8} textAnchor="end" fontSize="9" fill={CHART_COLORS.label}>
        {fmtTime(xMax)}
      </text>

      {maxY ? (
        <line
          x1={padL}
          x2={W - padR}
          y1={sy(maxY)}
          y2={sy(maxY)}
          stroke={CHART_COLORS.critical}
          strokeWidth="1"
          strokeDasharray="4 3"
        />
      ) : null}
      {maxY ? (
        <text x={W - padR} y={sy(maxY) - 4} textAnchor="end" fontSize="9" fill={CHART_COLORS.critical}>
          上限 {formatY(maxY)}
        </text>
      ) : null}

      <path d={area} fill={`url(#${gradientId})`} />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.8" />
      <circle cx={sx(xMax)} cy={sy(ys[ys.length - 1])} r="3" fill={stroke} />
    </svg>
  );
}
