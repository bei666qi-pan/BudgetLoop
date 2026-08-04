"""BudgetLoop API 客户端。

提供同步和异步两种风格的 HTTP 客户端，封装所有 BudgetLoop Control Plane API。
MCP Server 和其他 AI Agent 工具可直接使用此客户端与 BudgetLoop 交互。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.client.models import (
    BudgetSpec,
    CreateRunRequest,
    CreateTaskRequest,
    DecideApprovalRequest,
)


class BudgetLoopError(Exception):
    """BudgetLoop API 错误。"""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"BudgetLoop API error {status_code}: {detail}")


class BudgetLoopClient:
    """BudgetLoop API 同步客户端。

    使用示例:
        client = BudgetLoopClient(base_url="http://localhost:8000", api_token="...")
        tasks = client.list_tasks()
        result = client.create_task(CreateTaskRequest(name="fix bug", workdir="/app"))
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_token: str = "budgetloop-dev-token",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BudgetLoopClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ---- helpers ----

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 204:
            return {}
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise BudgetLoopError(resp.status_code, detail)
        return resp.json() if resp.text else {}

    def _get(self, path: str, **kwargs: Any) -> dict:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> dict:
        return self._request("POST", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> dict:
        return self._request("DELETE", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> dict:
        return self._request("PATCH", path, **kwargs)

    def _put(self, path: str, **kwargs: Any) -> dict:
        return self._request("PUT", path, **kwargs)

    # ---- health ----

    def health(self) -> dict:
        """健康检查（无需鉴权）。"""
        # 直接请求不带 auth header
        resp = httpx.get(f"{self.base_url}/api/health")
        return resp.json()

    # ---- tasks ----

    def create_task(self, body: CreateTaskRequest) -> dict:
        """创建任务并立即入队首个 Run。"""
        return self._post("/api/tasks", json=body.model_dump())

    def list_tasks(self) -> dict:
        """列出所有任务及其最新 Run 摘要。"""
        return self._get("/api/tasks")

    def delete_task(self, task_id: str) -> dict:
        """删除一个已终止的独立任务。"""
        return self._delete(f"/api/tasks/{task_id}")

    def create_task_run(self, task_id: str, body: CreateRunRequest | None = None) -> dict:
        """为已有任务创建新 Run。"""
        return self._post(
            f"/api/tasks/{task_id}/runs",
            json=body.model_dump(exclude_none=True) if body else {},
        )

    # ---- runs ----

    def get_run(self, run_id: str) -> dict:
        """获取 Run 聚合详情（run + task + budget）。"""
        return self._get(f"/api/runs/{run_id}")

    def pause_run(self, run_id: str) -> dict:
        """暂停运行。"""
        return self._post(f"/api/runs/{run_id}/pause")

    def cancel_run(self, run_id: str) -> dict:
        """取消运行。"""
        return self._post(f"/api/runs/{run_id}/cancel")

    # ---- observations ----

    def get_llm_calls(self, run_id: str) -> dict:
        """获取 LLM 调用记录。"""
        return self._get(f"/api/runs/{run_id}/llm-calls")

    def get_tool_calls(self, run_id: str) -> dict:
        """获取工具调用记录。"""
        return self._get(f"/api/runs/{run_id}/tool-calls")

    def get_budget(self, run_id: str) -> dict:
        """获取预算详情（含阶段预算与重分配记录）。"""
        return self._get(f"/api/runs/{run_id}/budget")

    def get_events(self, run_id: str, after_seq: int = 0, limit: int = 500) -> dict:
        """获取执行事件（支持游标分页）。"""
        return self._get(
            f"/api/runs/{run_id}/events",
            params={"after_seq": after_seq, "limit": limit},
        )

    def get_report(self, run_id: str) -> dict:
        """获取最终报告。"""
        return self._get(f"/api/runs/{run_id}/report")

    def export_report(self, run_id: str, fmt: str = "json") -> str:
        """导出报告（json/md），返回原始文本。"""
        resp = self._client.get(
            f"/api/runs/{run_id}/report/export",
            params={"format": fmt},
            headers={"Authorization": f"Bearer {self.api_token}"},
        )
        if resp.status_code >= 400:
            raise BudgetLoopError(resp.status_code, resp.text)
        return resp.text

    # ---- approvals ----

    def decide_approval(self, approval_id: str, body: DecideApprovalRequest) -> dict:
        """审批决策。"""
        return self._post(
            f"/api/approvals/{approval_id}/decide",
            json=body.model_dump(exclude_none=True),
        )

    # ---- ai gateway ----

    def get_ai_gateway_status(self) -> dict:
        """获取 AI 网关健康状态。"""
        return self._get("/api/ai-gateway/status")

    def get_ai_gateway_settings(self) -> dict:
        """获取 AI 网关设置。"""
        return self._get("/api/ai-gateway/settings")

    # ---- execution engines ----

    def get_execution_engines(self) -> dict:
        """列出所有注册的执行引擎。"""
        return self._get("/api/execution-engines")

    # ---- work containers ----

    def list_work_containers(
        self,
        lifecycle: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """列出工作容器。"""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if lifecycle:
            params["lifecycle"] = lifecycle
        return self._get("/api/work-containers", params=params)

    def create_work_container(
        self,
        name: str,
        project_goal: str,
        base_workdir: str,
        shared_context: str = "",
    ) -> dict:
        """创建独立工作容器。"""
        return self._post(
            "/api/work-containers",
            json={
                "name": name,
                "project_goal": project_goal,
                "base_workdir": base_workdir,
                "shared_context": shared_context,
            },
        )

    def get_work_container(self, container_id: str) -> dict:
        """获取工作容器详情。"""
        return self._get(f"/api/work-containers/{container_id}")

    # ---- streams ----

    def get_run_stream(self, run_id: str) -> httpx.Response:
        """获取 SSE 实时事件流（返回原始 Response 供迭代）。"""
        return self._client.send(
            self._client.build_request(
                "GET",
                f"/api/runs/{run_id}/stream",
                headers={"Authorization": f"Bearer {self.api_token}"},
            ),
            stream=True,
        )


class AsyncBudgetLoopClient:
    """BudgetLoop API 异步客户端。

    使用示例:
        async with AsyncBudgetLoopClient() as client:
            tasks = await client.list_tasks()
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_token: str = "budgetloop-dev-token",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncBudgetLoopClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code == 204:
            return {}
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise BudgetLoopError(resp.status_code, detail)
        return resp.json() if resp.text else {}

    async def _get(self, path: str, **kwargs: Any) -> dict:
        return await self._request("GET", path, **kwargs)

    async def _post(self, path: str, **kwargs: Any) -> dict:
        return await self._request("POST", path, **kwargs)

    async def health(self) -> dict:
        resp = await self._client.get(f"{self.base_url}/api/health")
        return resp.json()

    async def create_task(self, body: CreateTaskRequest) -> dict:
        return await self._post("/api/tasks", json=body.model_dump())

    async def list_tasks(self) -> dict:
        return await self._get("/api/tasks")

    async def get_run(self, run_id: str) -> dict:
        return await self._get(f"/api/runs/{run_id}")

    async def pause_run(self, run_id: str) -> dict:
        return await self._post(f"/api/runs/{run_id}/pause")

    async def cancel_run(self, run_id: str) -> dict:
        return await self._post(f"/api/runs/{run_id}/cancel")

    async def get_llm_calls(self, run_id: str) -> dict:
        return await self._get(f"/api/runs/{run_id}/llm-calls")

    async def get_budget(self, run_id: str) -> dict:
        return await self._get(f"/api/runs/{run_id}/budget")

    async def get_events(self, run_id: str, after_seq: int = 0, limit: int = 500) -> dict:
        return await self._get(
            f"/api/runs/{run_id}/events",
            params={"after_seq": after_seq, "limit": limit},
        )

    async def get_report(self, run_id: str) -> dict:
        return await self._get(f"/api/runs/{run_id}/report")

    async def decide_approval(self, approval_id: str, body: DecideApprovalRequest) -> dict:
        return await self._post(
            f"/api/approvals/{approval_id}/decide",
            json=body.model_dump(exclude_none=True),
        )

    async def get_ai_gateway_status(self) -> dict:
        return await self._get("/api/ai-gateway/status")

    async def list_work_containers(self, limit: int = 50, offset: int = 0) -> dict:
        return await self._get("/api/work-containers", params={"limit": limit, "offset": offset})

    async def get_execution_engines(self) -> dict:
        return await self._get("/api/execution-engines")
