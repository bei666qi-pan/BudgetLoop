"""策略切换决策：纯函数，输入确定性信号，输出 StrategyDecision。

所有实际切换由 orchestrator 记录（原因、旧计划、新计划、剩余预算）
并 emit strategy_switched 事件；本模块只负责决策。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import PressureMode

# 决策阈值（公开常量，测试与评测可引用）
LOW_SCORE_THRESHOLD = 0.3          # 低分线
LOW_SCORE_WINDOW = 3               # 连续低分窗口
REPEATED_ACTION_THRESHOLD = 2      # 重复动作累计次数
REGRESSION_SWITCH_THRESHOLD = 2    # 连续回归次数

# 策略名
STRATEGY_CHANGE_HYPOTHESIS = "change_hypothesis"  # 改变假设 / 扩大证据
STRATEGY_MINIMAL_FIX = "minimal_fix"              # 最小修复 + 回滚不稳定改动
STRATEGY_ROLLBACK = "rollback"                    # 回滚最近 checkpoint
STRATEGY_DEFAULT = "default"


@dataclass(frozen=True)
class StrategyDecision:
    should_switch: bool
    new_strategy: str
    reason: str


def decide_strategy(
    recent_scores: list[float],
    repeated_action_count: int,
    pressure_mode: PressureMode | str,
    current_strategy: str,
    regression_count: int = 0,
) -> StrategyDecision:
    """策略切换决策。

    规则（按优先级）：
    1. CRITICAL 压力 -> minimal_fix（最小修复 + 回滚不稳定改动）；
    2. 连续回归（>= REGRESSION_SWITCH_THRESHOLD）-> rollback（回滚最近 checkpoint）；
    3. 连续 LOW_SCORE_WINDOW 轮 score < LOW_SCORE_THRESHOLD 且重复动作累计
       >= REPEATED_ACTION_THRESHOLD -> change_hypothesis（改变假设/扩大证据）。
    目标策略与当前一致时不切换。
    """
    mode = PressureMode(pressure_mode)

    if mode == PressureMode.CRITICAL:
        return _decide(STRATEGY_MINIMAL_FIX, current_strategy,
                       "pressure CRITICAL: switch to minimal_fix (最小修复+回滚不稳定改动)")

    if regression_count >= REGRESSION_SWITCH_THRESHOLD:
        return _decide(STRATEGY_ROLLBACK, current_strategy,
                       f"regression streak {regression_count}: rollback to last checkpoint")

    window = recent_scores[-LOW_SCORE_WINDOW:]
    if (
        len(window) >= LOW_SCORE_WINDOW
        and all(s < LOW_SCORE_THRESHOLD for s in window)
        and repeated_action_count >= REPEATED_ACTION_THRESHOLD
    ):
        return _decide(STRATEGY_CHANGE_HYPOTHESIS, current_strategy,
                       f"{LOW_SCORE_WINDOW} consecutive scores < {LOW_SCORE_THRESHOLD} "
                       f"with {repeated_action_count} repeated actions: change hypothesis / widen evidence")

    return StrategyDecision(False, current_strategy, "no rule triggered")


def _decide(target: str, current: str, reason: str) -> StrategyDecision:
    if target == current:
        return StrategyDecision(False, current, f"already on {target}")
    return StrategyDecision(True, target, reason)
