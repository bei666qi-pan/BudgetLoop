// token / 费用 / 时长等展示格式化。

export function formatTokens(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

/** 费用格式化；null 表示后端未配置模型价格。 */
export function formatCost(
  n: number | null | undefined,
  nullText = "价格未配置",
): string {
  if (n === null || n === undefined) return nullText;
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

/** 毫秒时长 → 紧凑文本，如 1m23s / 45s / 1h2m */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  const totalSec = Math.max(0, Math.round(ms / 1000));
  return formatDurationSec(totalSec);
}

export function formatDurationSec(sec: number | null | undefined): string {
  if (sec === null || sec === undefined) return "—";
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h${m}m`;
  if (m > 0) return `${m}m${r}s`;
  return `${r}s`;
}

/** ISO 时间 → 本地 HH:MM:SS（24h）。无效输入原样返回。 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

/** 百分比（0-100，保留整数），分母为 0 时返回 null。 */
export function percent(used: number, max: number): number | null {
  if (!max || max <= 0) return null;
  return Math.min(100, Math.round((used / max) * 100));
}

/** ISO 时间戳转相对时间文本（中文），无效输入返回 "—"。 */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const now = Date.now();
  const diffMs = now - date.getTime();
  if (diffMs < 0) return "刚刚";
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 10) return "刚刚";
  if (seconds < 60) return `${seconds}秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}天前`;
  return formatDateTime(iso);
}
