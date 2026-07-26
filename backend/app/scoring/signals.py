"""确定性进展信号：评分的事实输入（防伪智能：信号即事实）。

本模块只做数据结构定义与信号提取的纯工具函数，禁止任何 LLM 参与。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProgressSignals:
    """一个 BudgetLoop iteration 的确定性信号快照。

    delta 约定：正值 = 改善（与上一轮对比）。
    """

    failed_tests_delta: int = 0     # prev_failed - cur_failed，正值 = 失败减少
    passed_tests_delta: int = 0     # cur_passed - prev_passed，正值 = 通过增加
    compile_errors_delta: int = 0   # prev_errors - cur_errors，正值 = 编译错误减少
    diff_files: int = 0             # 本轮 git diff 触及的文件数
    diff_lines: int = 0             # 本轮 git diff 增删行数（+/- 合计）
    new_evidence: int = 0           # 本轮新工具观测（ObservationEvent）数量
    repeated_action: bool = False   # 本轮动作指纹命中历史指纹集合
    regression: bool = False        # 通过测试减少或失败增加，且 diff 无变化
    plan_steps_completed: int = 0   # 本轮完成的计划步骤数

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ProgressSignals":
        return ProgressSignals(
            failed_tests_delta=int(data.get("failed_tests_delta", 0)),
            passed_tests_delta=int(data.get("passed_tests_delta", 0)),
            compile_errors_delta=int(data.get("compile_errors_delta", 0)),
            diff_files=int(data.get("diff_files", 0)),
            diff_lines=int(data.get("diff_lines", 0)),
            new_evidence=int(data.get("new_evidence", 0)),
            repeated_action=bool(data.get("repeated_action", False)),
            regression=bool(data.get("regression", False)),
            plan_steps_completed=int(data.get("plan_steps_completed", 0)),
        )


def normalize_action(tool: str, args: dict | str | None) -> str:
    """归一化 tool+args：小写、参数键排序、压缩空白，用于动作指纹。"""
    tool_norm = " ".join(str(tool).lower().split())
    if isinstance(args, dict):
        args_norm = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    else:
        args_norm = " ".join(str(args or "").lower().split())
    return f"{tool_norm}|{args_norm}"


def action_fingerprint(tool: str, args: dict | str | None) -> str:
    """动作指纹 = 归一化 tool+args 的 sha256。"""
    return hashlib.sha256(normalize_action(tool, args).encode("utf-8")).hexdigest()


def detect_regression(
    prev_passed: int,
    prev_failed: int,
    cur_passed: int,
    cur_failed: int,
    diff_lines: int,
) -> bool:
    """回归判定：通过测试减少或失败增加，且 diff 无变化。"""
    return (cur_passed < prev_passed or cur_failed > prev_failed) and diff_lines == 0
