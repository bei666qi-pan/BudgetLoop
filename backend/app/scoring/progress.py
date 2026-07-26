"""确定性进展评分：compute_score 为纯函数（同输入同输出），禁止任何 LLM 参与。

评分语义：以 0.5 为基线分，改善类信号加分、停滞/回归类信号减分，
最终裁剪到 [0, 1]。权重公开在 DEFAULT_WEIGHTS，可传参覆盖。
"""
from __future__ import annotations

import re

from app.scoring.signals import ProgressSignals

# 公开权重表（模块常量，调用方可传 weights 覆盖单项）
DEFAULT_WEIGHTS: dict[str, float] = {
    "base": 0.5,
    # 失败测试减少：+0.3/个，总加分封顶 0.6
    "failed_tests_decrease": 0.3,
    "failed_tests_cap": 0.6,
    # 通过测试增加：+0.2/个，封顶 0.4
    "passed_tests_increase": 0.2,
    "passed_tests_cap": 0.4,
    # 编译错误减少：+0.1/个，封顶 0.3
    "compile_errors_decrease": 0.1,
    "compile_errors_cap": 0.3,
    # 有代码改动（diff_lines > 0）：+0.1
    "diff_present": 0.1,
    # 新工具观测证据：+0.05/个，封顶 0.15
    "new_evidence": 0.05,
    "new_evidence_cap": 0.15,
    # 计划步骤完成：+0.05/个，封顶 0.1
    "plan_step": 0.05,
    "plan_step_cap": 0.1,
    # 重复动作：-0.25
    "repeated_action": -0.25,
    # 回归：-0.3
    "regression": -0.3,
    # 无 diff 且无新证据（空转）：-0.1
    "idle": -0.1,
}


def _cap(value: float, cap: float) -> float:
    return max(-cap, min(cap, value))


def compute_score(signals: ProgressSignals, weights: dict[str, float] | None = None) -> float:
    """确定性评分。纯函数：同输入同输出，结果裁剪到 [0, 1]。"""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    score = w["base"]

    score += _cap(max(0, signals.failed_tests_delta) * w["failed_tests_decrease"], w["failed_tests_cap"])
    score += _cap(max(0, signals.passed_tests_delta) * w["passed_tests_increase"], w["passed_tests_cap"])
    score += _cap(max(0, signals.compile_errors_delta) * w["compile_errors_decrease"], w["compile_errors_cap"])

    if signals.diff_lines > 0:
        score += w["diff_present"]

    score += _cap(signals.new_evidence * w["new_evidence"], w["new_evidence_cap"])
    score += _cap(signals.plan_steps_completed * w["plan_step"], w["plan_step_cap"])

    if signals.repeated_action:
        score += w["repeated_action"]
    if signals.regression:
        score += w["regression"]
    if signals.diff_lines == 0 and signals.new_evidence == 0:
        score += w["idle"]

    return min(1.0, max(0.0, score))


# ---------------------------------------------------------------------------
# 测试输出解析（python unittest 与 pytest 两种格式）
# ---------------------------------------------------------------------------

_UNITTEST_RAN = re.compile(r"Ran\s+(\d+)\s+tests?")
_UNITTEST_OK = re.compile(r"^OK\b", re.MULTILINE)
_UNITTEST_FAILED = re.compile(r"^FAILED\s*\(([^)]*)\)", re.MULTILINE)
_UNITTEST_ITEM = re.compile(r"(failures|errors|skipped)\s*=\s*(\d+)")
_PYTEST_ITEM = re.compile(r"(\d+)\s+(passed|failed|skipped|error|errors)\b")


def parse_unittest_output(text: str) -> tuple[int, int, int]:
    """解析测试输出 -> (passed, failed, skipped)。

    兼容：
    - python unittest: "Ran N tests in ..." + "OK" / "OK (skipped=x)" /
      "FAILED (failures=x, errors=y, skipped=z)"
    - pytest: "n passed, n failed, n skipped, n errors in ..." 汇总行
    """
    # pytest 汇总行（含 "passed" 计数时优先按 pytest 解析）
    if "passed" in text:
        passed = failed = skipped = 0
        found = False
        for count, kind in _PYTEST_ITEM.findall(text):
            found = True
            n = int(count)
            if kind == "passed":
                passed += n
            elif kind == "failed":
                failed += n
            elif kind == "skipped":
                skipped += n
            else:  # error / errors
                failed += n
        if found:
            return passed, failed, skipped

    # python unittest
    m = _UNITTEST_RAN.search(text)
    if not m:
        return 0, 0, 0
    ran = int(m.group(1))
    failures = errors = skipped = 0
    fm = _UNITTEST_FAILED.search(text)
    if fm:
        for kind, count in _UNITTEST_ITEM.findall(fm.group(1)):
            if kind == "failures":
                failures = int(count)
            elif kind == "errors":
                errors = int(count)
            else:
                skipped = int(count)
    elif _UNITTEST_OK.search(text):
        ok_m = re.search(r"^OK\s*\(([^)]*)\)", text, re.MULTILINE)
        if ok_m:
            for kind, count in _UNITTEST_ITEM.findall(ok_m.group(1)):
                if kind == "skipped":
                    skipped = int(count)
    failed = failures + errors
    passed = max(0, ran - failed - skipped)
    return passed, failed, skipped
