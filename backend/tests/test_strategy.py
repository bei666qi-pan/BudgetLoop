"""策略切换测试：连续低分/重复/回归/CRITICAL 触发。"""
from app.core.enums import PressureMode
from app.policy.strategy import (
    STRATEGY_CHANGE_HYPOTHESIS,
    STRATEGY_DEFAULT,
    STRATEGY_MINIMAL_FIX,
    STRATEGY_ROLLBACK,
    decide_strategy,
)


class TestDecideStrategy:
    def test_no_switch_when_good_scores(self):
        dec = decide_strategy(
            recent_scores=[0.8, 0.7, 0.9],
            repeated_action_count=0,
            pressure_mode=PressureMode.NORMAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=0,
        )
        assert dec.should_switch is False

    def test_switch_on_consecutive_low_scores(self):
        dec = decide_strategy(
            recent_scores=[0.2, 0.2, 0.2],
            repeated_action_count=3,
            pressure_mode=PressureMode.NORMAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=0,
        )
        assert dec.should_switch is True
        assert dec.new_strategy == STRATEGY_CHANGE_HYPOTHESIS

    def test_switch_on_regression(self):
        dec = decide_strategy(
            recent_scores=[0.2, 0.1],
            repeated_action_count=0,
            pressure_mode=PressureMode.NORMAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=2,
        )
        assert dec.should_switch is True
        assert dec.new_strategy == STRATEGY_ROLLBACK

    def test_no_switch_single_bad(self):
        dec = decide_strategy(
            recent_scores=[0.1],
            repeated_action_count=1,
            pressure_mode=PressureMode.NORMAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=0,
        )
        assert dec.should_switch is False

    def test_switch_on_critical_pressure(self):
        dec = decide_strategy(
            recent_scores=[0.6, 0.7],
            repeated_action_count=0,
            pressure_mode=PressureMode.CRITICAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=0,
        )
        assert dec.should_switch is True
        assert dec.new_strategy == STRATEGY_MINIMAL_FIX

    def test_change_hypothesis_when_stale(self):
        dec = decide_strategy(
            recent_scores=[0.29, 0.29, 0.29],
            repeated_action_count=4,
            pressure_mode=PressureMode.NORMAL,
            current_strategy=STRATEGY_DEFAULT,
            regression_count=0,
        )
        assert dec.should_switch is True
        assert dec.new_strategy == STRATEGY_CHANGE_HYPOTHESIS

    def test_keep_minimal_fix_in_critical(self):
        dec = decide_strategy(
            recent_scores=[0.8],
            repeated_action_count=0,
            pressure_mode=PressureMode.CRITICAL,
            current_strategy=STRATEGY_MINIMAL_FIX,
            regression_count=0,
        )
        assert dec.should_switch is False
