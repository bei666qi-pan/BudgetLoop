"""BudgetLoop API 共享数据模型。

与后端 Pydantic 模型保持独立，确保 MCP 客户端零依赖后端内部模块。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BudgetSpec(BaseModel):
    """任务预算约束。"""

    max_total_tokens: int = Field(default=100_000, ge=1)
    max_wall_time_seconds: int = Field(default=1200, ge=1)
    max_active_runtime_seconds: int = Field(default=600, ge=1)
    max_llm_calls: int = Field(default=20, ge=1)
    max_cost: float = Field(default=5.0, gt=0)
    max_parallel_llm_calls: int = Field(default=2, ge=1)


class CreateTaskRequest(BaseModel):
    """创建任务请求。"""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    workdir: str = Field(min_length=1, max_length=500)
    acceptance_criteria: str | None = None
    template: str = "fix_bug"
    require_approval: bool = True
    strategy: str = "dynamic"
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    project_dir: str | None = Field(default=None, max_length=500)
    folder_access: str = "isolated"


class CreateRunRequest(BaseModel):
    """重新运行任务的可选覆盖项。"""

    strategy: str | None = None
    budget: BudgetSpec | None = None
    model_config: dict | None = Field(default=None, alias="model_cfg")


class DecideApprovalRequest(BaseModel):
    """审批决策请求。"""

    action: Literal["approve", "reject", "modify"]
    note: str | None = None
