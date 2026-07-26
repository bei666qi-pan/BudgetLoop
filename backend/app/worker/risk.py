"""危险动作识别：扫描 agent 的 bash 命令 / 文件操作，命中规则则需要人工审批。

纯函数，规则表在模块常量 BASH_RULES / FILE_RULES。
返回 RiskHit(action_type, description, risk)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.enums import ApprovalActionType

# 单轮改动文件数阈值，超过则需要审批
MAX_FILES_THRESHOLD = 10


@dataclass(frozen=True)
class RiskHit:
    action_type: ApprovalActionType
    description: str
    risk: str  # low | medium | high


@dataclass(frozen=True)
class _BashRule:
    action_type: ApprovalActionType
    pattern: re.Pattern[str]
    description: str
    risk: str


# 危险 bash 命令规则表
BASH_RULES: tuple[_BashRule, ...] = (
    _BashRule(
        ApprovalActionType.DANGEROUS_COMMAND,
        re.compile(r"\brm\s+(?:-[a-zA-Z]*[rf][a-zA-Z]*\s+)+\S"),
        "recursive/forced delete (rm -rf)",
        "high",
    ),
    _BashRule(
        ApprovalActionType.DANGEROUS_COMMAND,
        re.compile(r"\bsudo\b"),
        "privilege escalation (sudo)",
        "medium",
    ),
    _BashRule(
        ApprovalActionType.DANGEROUS_COMMAND,
        re.compile(r"\bgit\s+push\b"),
        "git push to remote",
        "high",
    ),
    _BashRule(
        ApprovalActionType.DANGEROUS_COMMAND,
        re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
        "destructive SQL (DROP TABLE)",
        "high",
    ),
    _BashRule(
        ApprovalActionType.DEPENDENCY_CHANGE,
        re.compile(r"\bpip3?\s+(?:un)?install\b"),
        "dependency change (pip install/uninstall)",
        "medium",
    ),
    _BashRule(
        ApprovalActionType.NETWORK_ACCESS,
        re.compile(r"\b(?:curl|wget)\s+\S"),
        "network access (curl/wget)",
        "medium",
    ),
    _BashRule(
        ApprovalActionType.DELETE_FILE,
        re.compile(r"\brm\s+(?!-)\S"),
        "file deletion (rm)",
        "medium",
    ),
)

# 写工作目录外路径：重定向 / tee / cp / mv 的目标为 workdir 之外的绝对路径
_OUT_OF_WORKDIR_TARGET = re.compile(r"(?:>>?|tee\b|cp\b|mv\b)[^;|&]*?(/[^\s;|&>]+)")

# 文件编辑工具名（OpenHands 默认工具）
_FILE_TOOL_NAMES = frozenset({"str_replace_editor", "file_editor", "edit_file", "write_file"})
_DELETE_TOOL_NAMES = frozenset({"delete_file", "remove_file"})


def _is_out_of_workdir(path: str, workdir: str) -> bool:
    workdir = workdir.rstrip("/") or "/"
    return not (path == workdir or path.startswith(workdir + "/"))


def assess_bash_command(command: str, workdir: str = "/workspace") -> list[RiskHit]:
    """扫描单条 bash 命令，返回命中的风险列表（可能为空）。"""
    hits: list[RiskHit] = []
    for rule in BASH_RULES:
        m = rule.pattern.search(command)
        if m:
            hits.append(RiskHit(rule.action_type, f"{rule.description}: {m.group(0).strip()!r}", rule.risk))
    for m in _OUT_OF_WORKDIR_TARGET.finditer(command):
        target = m.group(1)
        if _is_out_of_workdir(target, workdir):
            hits.append(RiskHit(
                ApprovalActionType.OUT_OF_WORKDIR,
                f"write outside workdir {workdir!r}: {target!r}",
                "high",
            ))
            break
    return hits


def assess_action(
    tool_name: str,
    args_summary: dict | str | None = None,
    *,
    changed_files_count: int = 0,
    workdir: str = "/workspace",
) -> list[RiskHit]:
    """评估一个 agent 动作（工具调用）的风险。

    - bash/execute_bash 类工具：扫描命令文本；
    - 文件删除类工具：delete_file；
    - 文件编辑类工具写 workdir 外路径：out_of_workdir；
    - 单轮改动文件数 > MAX_FILES_THRESHOLD：too_many_files。
    """
    hits: list[RiskHit] = []
    tool = (tool_name or "").lower()

    command = _extract_command(args_summary)
    if command is not None and ("bash" in tool or "shell" in tool or "terminal" in tool or command):
        hits.extend(assess_bash_command(command, workdir))

    if tool in _DELETE_TOOL_NAMES:
        hits.append(RiskHit(ApprovalActionType.DELETE_FILE, f"delete via tool {tool_name!r}", "medium"))

    if tool in _FILE_TOOL_NAMES:
        path = _extract_path(args_summary)
        if path and path.startswith("/") and _is_out_of_workdir(path, workdir):
            hits.append(RiskHit(
                ApprovalActionType.OUT_OF_WORKDIR,
                f"file tool {tool_name!r} writes outside workdir: {path!r}",
                "high",
            ))

    if changed_files_count > MAX_FILES_THRESHOLD:
        hits.append(RiskHit(
            ApprovalActionType.TOO_MANY_FILES,
            f"{changed_files_count} files changed in one iteration (> {MAX_FILES_THRESHOLD})",
            "medium",
        ))
    return hits


def _extract_command(args_summary: dict | str | None) -> str | None:
    if isinstance(args_summary, dict):
        for key in ("command", "cmd", "code"):
            if isinstance(args_summary.get(key), str):
                return args_summary[key]
        return None
    if isinstance(args_summary, str):
        return args_summary
    return None


def _extract_path(args_summary: dict | str | None) -> str | None:
    if isinstance(args_summary, dict):
        for key in ("path", "file_path", "filename", "target"):
            if isinstance(args_summary.get(key), str):
                return args_summary[key]
    return None
