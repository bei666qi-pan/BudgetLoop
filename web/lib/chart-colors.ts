// 图表颜色的单一来源：与 tailwind.config.ts 的调色板保持一致。
// SVG 的 stroke/fill 属性需要 hex 值，无法直接使用 Tailwind 工具类，
// 因此所有图表颜色从这里引用，改色时与 tailwind.config.ts 同步修改。

export const CHART_COLORS = {
  /** 主数据序列（= accent） */
  accent: "#1769F6",
  /** 次数据序列（= success） */
  success: "#0CAD72",
  /** 预警（= warning） */
  warning: "#F28A00",
  /** 参考线 / 超限（= critical） */
  critical: "#EF4B5B",
  /** 网格线（= border） */
  grid: "#D8E4F5",
  /** 坐标文字（= muted-foreground） */
  label: "#60759A",
} as const;
