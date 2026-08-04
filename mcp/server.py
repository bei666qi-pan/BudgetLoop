"""BudgetLoop MCP Server。

启动方式:
  budgetloop-mcp                          # stdio 模式（默认）
  budgetloop-mcp --transport sse --port 3100  # HTTP/SSE 模式

环境变量:
  BUDGETLOOP_API_URL   — BudgetLoop Control Plane 地址（默认 http://localhost:8000）
  BUDGETLOOP_API_TOKEN — API 鉴权 Token（默认 budgetloop-dev-token）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---- 配置 ----

API_URL = os.environ.get("BUDGETLOOP_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("BUDGETLOOP_API_TOKEN", "budgetloop-dev-token")

mcp = FastMCP(
    "BudgetLoop",
    description="预算感知 Coding Agent 控制面板 — 创建任务、监控执行、审批决策",
)

_client = httpx.Client(
    base_url=API_URL,
    headers={"Authorization": f"Bearer {API_TOKEN}"},
    timeout=30.0,
)


def _api(method: str, path: str, **kwargs: Any) -> dict:
    """调用 BudgetLoop API，统一错误处理。"""
    resp = _client.request(method, path, **kwargs)
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"BudgetLoop API error {resp.status_code}: {detail}")
    return resp.json() if resp.text else {}


def _fmt(obj: Any) -> str:
    """格式化 JSON 输出。"""
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---- 工具 ----

@mcp.tool()
def health_check() -> str:
    """检查 BudgetLoop 服务是否正常运行。"""
    resp = httpx.get(f"{API_URL}/api/health")
    return _fmt(resp.json())


@mcp.tool()
def create_task(
    name: str,
    workdir: str,
    description: str = "",
    acceptance_criteria: str | None = None,
    template: str = "fix_bug",
    max_total_tokens: int = 100_000,
    max_wall_time_seconds: int = 1200,
    max_llm_calls: int = 20,
    max_cost: float = 5.0,
) -> str:
    """创建编码任务并入队首个 Run。

    Args:
        name: 任务名称（1-200 字符）
        workdir: 工作目录（绝对路径）
        description: 任务描述
        acceptance_criteria: 验收条件
        template: 任务模板（fix_bug/add_feature/refactor/small_feature/code_review）
        max_total_tokens: 最大 Token 数
        max_wall_time_seconds: 最大挂钟时间（秒）
        max_llm_calls: 最大 LLM 调用次数
        max_cost: 最大费用（美元）
    """
    body = {
        "name": name,
        "workdir": workdir,
        "description": description,
        "acceptance_criteria": acceptance_criteria,
        "template": template,
        "budget": {
            "max_total_tokens": max_total_tokens,
            "max_wall_time_seconds": max_wall_time_seconds,
            "max_active_runtime_seconds": 600,
            "max_llm_calls": max_llm_calls,
            "max_cost": max_cost,
            "max_parallel_llm_calls": 2,
        },
    }
    return _fmt(_api("POST", "/api/tasks", json=body))


@mcp.tool()
def list_tasks() -> str:
    """列出所有任务及其最新 Run 摘要。"""
    return _fmt(_api("GET", "/api/tasks"))


@mcp.tool()
def get_run(run_id: str) -> str:
    """获取 Run 聚合详情（run + task + budget）。

    Args:
        run_id: 运行 ID（UUID）
    """
    return _fmt(_api("GET", f"/api/runs/{run_id}"))


@mcp.tool()
def pause_run(run_id: str) -> str:
    """暂停运行。

    Args:
        run_id: 运行 ID（UUID）
    """
    return _fmt(_api("POST", f"/api/runs/{run_id}/pause"))


@mcp.tool()
def cancel_run(run_id: str) -> str:
    """取消运行。

    Args:
        run_id: 运行 ID（UUID）
    """
    return _fmt(_api("POST", f"/api/runs/{run_id}/cancel"))


@mcp.tool()
def get_run_events(run_id: str, after_seq: int = 0, limit: int = 100) -> str:
    """获取执行事件流（游标分页，用于轮询最新进展）。

    Args:
        run_id: 运行 ID（UUID）
        after_seq: 从该序号之后开始（首次传 0）
        limit: 返回条数上限
    """
    return _fmt(_api("GET", f"/api/runs/{run_id}/events", params={"after_seq": after_seq, "limit": limit}))


@mcp.tool()
def get_run_report(run_id: str) -> str:
    """获取 Run 的最终执行报告。

    Args:
        run_id: 运行 ID（UUID）
    """
    return _fmt(_api("GET", f"/api/runs/{run_id}/report"))


@mcp.tool()
def get_budget(run_id: str) -> str:
    """获取 Run 的预算详情（含各阶段消耗与重分配记录）。

    Args:
        run_id: 运行 ID（UUID）
    """
    return _fmt(_api("GET", f"/api/runs/{run_id}/budget"))


@mcp.tool()
def decide_approval(approval_id: str, action: str, note: str | None = None) -> str:
    """审批决策：批准、拒绝或修改 Agent 的高风险操作。

    Args:
        approval_id: 审批 ID（UUID）
        action: 决策动作（approve / reject / modify）
        note: 可选备注
    """
    body: dict[str, Any] = {"action": action}
    if note:
        body["note"] = note
    return _fmt(_api("POST", f"/api/approvals/{approval_id}/decide", json=body))


@mcp.tool()
def get_ai_gateway_status() -> str:
    """检查 AI 网关连接状态。"""
    return _fmt(_api("GET", "/api/ai-gateway/status"))


@mcp.tool()
def list_work_containers(limit: int = 20, offset: int = 0) -> str:
    """列出 Agent Team 工作容器。

    Args:
        limit: 返回条数
        offset: 偏移量
    """
    return _fmt(_api("GET", "/api/work-containers", params={"limit": limit, "offset": offset}))


@mcp.tool()
def get_work_container(container_id: str) -> str:
    """获取工作容器详情（含 Sessions 状态）。

    Args:
        container_id: 容器 ID（UUID）
    """
    return _fmt(_api("GET", f"/api/work-containers/{container_id}"))


@mcp.tool()
def list_execution_engines() -> str:
    """列出所有可用的执行引擎（OpenHands、Codex、Gemini CLI 等）。"""
    return _fmt(_api("GET", "/api/execution-engines"))


# ---- 资源（只读数据模板） ----

@mcp.resource("budgetloop://tasks")
def resource_tasks() -> str:
    """任务列表资源。"""
    return _fmt(_api("GET", "/api/tasks"))


@mcp.resource("budgetloop://tasks/{task_id}")
def resource_task(task_id: str) -> str:
    """单个任务资源。"""
    tasks = _api("GET", "/api/tasks").get("tasks", [])
    for t in tasks:
        if t.get("id") == task_id:
            return _fmt(t)
    return _fmt({"error": "task not found"})


@mcp.resource("budgetloop://runs/{run_id}")
def resource_run(run_id: str) -> str:
    """运行详情资源。"""
    return _fmt(_api("GET", f"/api/runs/{run_id}"))


@mcp.resource("budgetloop://runs/{run_id}/report")
def resource_report(run_id: str) -> str:
    """运行报告资源。"""
    return _fmt(_api("GET", f"/api/runs/{run_id}/report"))


@mcp.resource("budgetloop://containers")
def resource_containers() -> str:
    """工作容器列表资源。"""
    return _fmt(_api("GET", "/api/work-containers"))


# ---- Prompts（快捷指令模板） ----

@mcp.prompt()
def fix_bug(description: str, workdir: str = "/app") -> str:
    """创建修复 Bug 的标准任务提示。

    Args:
        description: Bug 描述
        workdir: 工作目录
    """
    return textwrap.dedent(f"""\
        请使用 BudgetLoop 创建一个修复 Bug 的任务：

        任务名称: 修复: {description[:80]}
        工作目录: {workdir}
        描述: {description}
        模板: fix_bug
        预算: 100k tokens, 20 次 LLM 调用, $5.00

        用 create_task 工具创建任务，然后用 get_run_events 监控进度。""")


@mcp.prompt()
def add_feature(description: str, workdir: str = "/app") -> str:
    """创建添加功能的标准任务提示。

    Args:
        description: 功能描述
        workdir: 工作目录
    """
    return textwrap.dedent(f"""\
        请使用 BudgetLoop 创建一个添加功能的任务：

        任务名称: 新增: {description[:80]}
        工作目录: {workdir}
        描述: {description}
        模板: small_feature
        预算: 200k tokens, 30 次 LLM 调用, $10.00

        用 create_task 工具创建任务，然后用 get_run_events 监控进度。""")


@mcp.prompt()
def review_run(run_id: str) -> str:
    """审查运行结果并给出建议。

    Args:
        run_id: 要审查的运行 ID
    """
    return textwrap.dedent(f"""\
        请审查 BudgetLoop 运行 {run_id} 的结果：

        1. 用 get_run 获取运行状态
        2. 用 get_run_report 获取最终报告
        3. 用 get_budget 检查预算消耗
        4. 总结关键发现并给出改进建议""")


# ---- 入口 ----

def main() -> None:
    parser = argparse.ArgumentParser(description="BudgetLoop MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="传输协议（默认 stdio）",
    )
    parser.add_argument("--port", type=int, default=3100, help="SSE 模式端口（默认 3100）")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式绑定地址")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
