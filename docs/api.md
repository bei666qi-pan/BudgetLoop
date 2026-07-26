# BudgetLoop API 文档

API 基础路径：`http://localhost:8000/api`

鉴权：所有接口（除 `/api/health`）需请求头 `Authorization: Bearer <API_TOKEN>`

--- 参见 [docs/api-contract.md](./api-contract.md) 的接口定义，本文档补充完整响应示例与错误码。

---

## 通用约定

- 时间格式：ISO 8601 (UTC)
- UUID：36 字符
- 分页：`after_seq` 游标（单调递增 BIGSERIAL）
- 幂等：`Idempotency-Key` 头

## 端点一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（免鉴权） |
| POST | `/api/task-drafts` | 无副作用地生成/修订首页建议配置 |
| POST | `/api/tasks` | 创建任务并启动首个 run |
| POST | `/api/work-containers/from-preset` | 幂等确认并创建建议的 Agent Team |
| POST | `/api/tasks/:id/runs` | 同一任务再跑一次 |
| GET | `/api/tasks` | 任务列表（含最新 run 摘要） |
| GET | `/api/runs/:id` | run 聚合详情（run + task + budget） |
| POST | `/api/runs/:id/pause` | 暂停运行 |
| POST | `/api/runs/:id/cancel` | 取消运行 |
| GET | `/api/runs/:id/llm-calls` | 逐次 LLM 调用列表 |
| GET | `/api/runs/:id/tool-calls` | 工具调用列表 |
| GET | `/api/runs/:id/budget` | 预算快照 + 阶段预算 + 重分配 |
| GET | `/api/runs/:id/events?after_seq=N` | 执行事件（SSE 回放/轮询） |
| GET | `/api/runs/:id/report` | 最终报告 |
| GET | `/api/runs/:id/report/export?format=json\|md` | 导出报告 |
| POST | `/api/approvals/:id/decide` | 审批决策 |

## 创建任务

`POST /api/tasks`

请求体：
```json
{
  "name": "修复库存并发扣减",
  "description": "订单服务 POST /orders 并发下超扣库存...",
  "workdir": "/workspace/project",
  "acceptance_criteria": null,
  "template": "fix_bug",
  "require_approval": true,
  "folder_access": "isolated",
  "project_dir": null,
  "strategy": "dynamic",
  "budget": {
    "max_total_tokens": 100000,
    "max_wall_time_seconds": 1200,
    "max_active_runtime_seconds": 600,
    "max_llm_calls": 20,
    "max_cost": 5.0,
    "max_parallel_llm_calls": 2
  }
}
```

`folder_access` 默认 `isolated`，不会挂载或修改宿主文件夹。单任务选择
`full_access` 时必须提供规范化的非敏感绝对 `project_dir`；服务器会把确认后的策略写入
Run 配置并由唯一的 WorkspaceManager 转译为 Docker mount。

响应 `201`：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

## 生成首页建议配置

`POST /api/task-drafts`

```json
{
  "message": "分析销售数据下滑原因，并交付可执行的改进建议",
  "previous_draft": null
}
```

接口返回版本化 `TaskSetupDraft`：公开意图、可信内置团队、目录解析的角色/任务/预算、
执行引擎事实、最多两条澄清问题以及 `ai` 或 `local_fallback` 来源。AI 不可生成自由角色、
提高预算、关闭审批或选择文件夹权限；输出无效或网关不可用时会自动使用本地 LangGraph
推荐。草稿不会创建 Task/Run/Session、不会投递 worker，也不会访问文件。

跟进修改时，`previous_draft` 只传上一版公开可编辑字段。文件夹授权始终留在客户端的独立
权限控件中，不能因用户在自然语言里提到路径或“完全访问”而自动生效。

## 确认建议 Agent Team

`POST /api/work-containers/from-preset` 必须携带 `Idempotency-Key`。除既有 preset、角色、
预算和启动字段外，可提交：

```json
{
  "folder_access": "full_access",
  "project_dir": "/Users/you/project",
  "full_access_acknowledged": true,
  "default_workspace_policy": "worktree",
  "recommendation_source": "ai"
}
```

- 省略新增字段保持向后兼容，默认隔离。
- 完全访问必须同时满足路径、明确确认和 worktree 策略；任一缺失都会在创建任何记录前返回
  422。
- 每个 Session 使用服务端生成的独立 worktree；挂载/Git 失败时 fail closed。
- `recommendation_source` 是公开来源说明，不等同于操作员授权；快照不保存隐藏推理、提示词
  全文或凭据。

## 运行聚合详情

`GET /api/runs/:id`

```json
{
  "run": {
    "id": "...",
    "task_id": "...",
    "attempt_no": 1,
    "strategy": "dynamic",
    "status": "EXECUTING",
    "current_phase": "modify",
    "pressure_mode": "NORMAL",
    "iteration": 3,
    "started_at": "2026-07-23T10:00:00Z",
    "deadline_at": "2026-07-23T10:20:00Z",
    "active_runtime_ms": 45000
  },
  "task": {
    "id": "...",
    "name": "修复库存并发扣减",
    "description": "...",
    "template": "fix_bug",
    "require_approval": true
  },
  "budget": {
    "max_total_tokens": 100000,
    "used_tokens": 12000,
    "reserved_tokens": 4000,
    "remaining_tokens": 84000,
    "used_cost": 0.03,
    "remaining_cost": 4.97
  }
}
```

## 执行事件

`GET /api/runs/:id/events?after_seq=42`

```json
{
  "events": [
    {
      "seq": 43,
      "type": "state_changed",
      "payload": {"from": "EXECUTING", "to": "OBSERVING"},
      "created_at": "2026-07-23T10:01:00Z"
    },
    {
      "seq": 44,
      "type": "llm_call",
      "payload": {"iteration": 3, "call_kind": "agent", "total_tokens": 4200, "cost": 0.0042},
      "created_at": "2026-07-23T10:01:02Z"
    }
  ]
}
```

## 审批决策

`POST /api/approvals/:id/decide`

```json
{
  "action": "approve",
  "note": "这个操作在预期之内，允许执行"
}
```

幂等：重复提交同一审批 ID，若已决策则返回当前状态（不报错）。

## 错误响应

```json
{
  "detail": "budget check failed: max_llm_calls reached"
}
```

HTTP 状态码：400 非法参数、404 资源不存在、409 状态冲突、500 内部错误。

## 完整接口定义

参见 [docs/api-contract.md](./api-contract.md)——它是前后端实现的共同契约，包含全部字段定义。
