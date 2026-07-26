"""双时间预算压力模式：wall clock 与 active runtime 两条口径取更紧张者。

纯函数，无任何 IO / LLM。阈值：
- 剩余比例 > 0.5  -> NORMAL
- 0.2 < 剩余比例 <= 0.5 -> CONSERVATIVE
- 剩余比例 <= 0.2 -> CRITICAL
token 剩余比例 < 0.2 时至少 CONSERVATIVE。
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import PressureMode

NORMAL_THRESHOLD = 0.5
CRITICAL_THRESHOLD = 0.2


def _remaining_ratio(remaining: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, remaining / total))


def _mode_from_ratio(ratio: float) -> PressureMode:
    if ratio > NORMAL_THRESHOLD:
        return PressureMode.NORMAL
    if ratio > CRITICAL_THRESHOLD:
        return PressureMode.CONSERVATIVE
    return PressureMode.CRITICAL


def _tighter(a: PressureMode, b: PressureMode) -> PressureMode:
    order = {PressureMode.NORMAL: 0, PressureMode.CONSERVATIVE: 1, PressureMode.CRITICAL: 2}
    return a if order[a] >= order[b] else b


def compute_pressure_mode(
    *,
    deadline_at: datetime | None,
    max_wall_time_seconds: int,
    active_runtime_ms: int,
    max_active_runtime_seconds: int,
    remaining_tokens: int,
    max_total_tokens: int,
    now: datetime | None = None,
) -> PressureMode:
    """计算压力模式。

    - wall 口径：deadline_at - now 占 max_wall_time_seconds 的比例；
      deadline_at 为 None 时视为不紧张（比例 1.0）。
    - active 口径：max_active_runtime_seconds - active_runtime_ms 的剩余比例。
      active_runtime_ms 由 orchestrator 用单调时钟累加，
      WAITING_APPROVAL / PAUSED 期间不累加，因此审批等待不会让 active 口径变紧张。
    - 两口径取更紧张者；token 剩余比例 < 0.2 时至少 CONSERVATIVE。
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if deadline_at is None:
        wall_ratio = 1.0
    else:
        remaining_wall = (deadline_at - now).total_seconds()
        wall_ratio = _remaining_ratio(remaining_wall, max_wall_time_seconds)

    remaining_active_ms = max_active_runtime_seconds * 1000 - active_runtime_ms
    active_ratio = _remaining_ratio(remaining_active_ms, max_active_runtime_seconds * 1000)

    mode = _tighter(_mode_from_ratio(wall_ratio), _mode_from_ratio(active_ratio))

    token_ratio = _remaining_ratio(remaining_tokens, max_total_tokens)
    if token_ratio < CRITICAL_THRESHOLD and mode == PressureMode.NORMAL:
        mode = PressureMode.CONSERVATIVE

    return mode
