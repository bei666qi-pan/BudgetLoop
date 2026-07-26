# BudgetLoop API 契约（control-plane 与 web 的共同依据）

所有端点前缀 `/api`，除 `/api/health` 外均需请求头 `Authorization: Bearer <API_TOKEN>`。
`run_id` / `task_id` / `container_id` / `session_id` 均为 UUID 字符串。时间均为 ISO8601（UTC）。

## 任务与运行

- `POST /api/tasks` — 创建任务并启动首个 run。
  - Header: `Idempotency-Key: <string>`（可选，重复提交返回同一任务）
  - Body:
    ```json
    {
      "name": "修复库存并发扣减",
      "description": "...",
      "workdir": "/workspace/project",
      "acceptance_criteria": "可为空，agent 自动生成",
      "template": "fix_bug|locate_issue|add_tests|small_feature|fix_build",
      "require_approval": true,
      "folder_access": "isolated|full_access",
      "project_dir": "/Users/you/project（仅 full_access 必填）",
      "strategy": "none|fixed|dynamic",
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
  - 返回 `{ "task_id": "...", "run_id": "..." }`
- `POST /api/tasks/{task_id}/runs` — 同一任务再跑一次（换 strategy/budget/model_config）。Body 字段同上的可选子集 + `model_config`。
- `GET /api/tasks` — 任务列表，每项含最新 run 摘要（status、iteration、used_tokens、used_cost）。
- `GET /api/runs/{run_id}` — 聚合详情：
  ```json
  {
    "run": {"id","task_id","attempt_no","strategy","status","current_phase","pressure_mode","iteration","started_at","finished_at","deadline_at","active_runtime_ms","error","work_container_id","work_session_id","work_session_role"},
    "task": {"id","name","description","workdir","acceptance_criteria","template","require_approval"},
    "budget": { max_*, used_*, reserved_*, remaining_tokens, remaining_calls, remaining_cost, projected_tokens }
  }
  ```
- `POST /api/runs/{run_id}/pause`、`POST /api/runs/{run_id}/cancel` — 幂等。

旧任务和运行的三个 `work_*` 归属字段均为 `null`；其执行与序列化语义不变。

## 对话式任务草稿

- `POST /api/task-drafts` — 把首页的一段自然语言描述转换为可审阅的 Agent Team 配置草稿。此接口无数据库、队列、文件挂载或预算副作用。
  - Body:
    ```json
    {
      "message": "检查订单服务的并发测试，修复问题并给出验证结果",
      "previous_draft": null
    }
    ```
  - `message` 为 3–10000 个字符。跟进修改可传上一版公开、可编辑草稿；其 schema 固定为版本 `1`，只包含 `title`、`goal`、`acceptance_criteria`、`shared_context`、`preset_id` 和 `preset_version`。
  - 返回 `TaskSetupDraft`，主要字段为：
    ```json
    {
      "schema_version": 1,
      "state": "ready",
      "clarifications": [],
      "intent": {"title":"...","goal":"...","acceptance_criteria":"...","shared_context":""},
      "team": {"preset":{"id":"software-delivery","version":1},"confidence":76,"reason":"...","matched_signals":["..."],"activation_plan":{}},
      "execution": {"default_engine":"openhands","ready":true,"require_approval":true,"start_immediately":true,"base_workdir":"/workspace/project","default_workspace_policy":"worktree"},
      "provenance": {"source":"ai|local_fallback","runtime":"ai-gateway|langgraph","model":null,"fallback_reason":null,"duration_ms":12,"explanation":"..."}
    }
    ```
  - 模型只能整理四个公开意图文本并选择服务端提供的可信 preset ID/version。角色、任务、激活图、预算、执行引擎、审批和权限均由服务端目录解析；未知 key、未知 preset、超限或畸形输出会被拒绝并改用确定性的本地 LangGraph 推荐。
  - `provenance.source=local_fallback` 是可用的降级结果，不是创建失败。响应不包含提示词全文、隐藏推理、凭据或文件夹授权。
  - 文件夹模式、路径和高风险确认不属于草稿，也不能由提示词授权；它们只在最终创建请求中由操作员明确提交。

## Agent Team 工作容器

工作容器是可选的项目协调层。每个 Session 仍然原子创建一个标准 `Task`、`TaskRun`、预算账本与六个阶段，并且只将该 Run 投递到 worker。容器共享上下文不会授予跨 workspace 文件访问权限。

### 可替换执行引擎

- `GET /api/execution-engines` — 返回 OpenHands、Codex、Gemini CLI、OpenCode 的 canonical repo、固定 revision、审查 Star、许可证边界、能力，以及 `source_downloaded`、`package_installed`、`managed_ai_ready`、`runtime_available` 四级就绪事实。响应明确 `BudgetLoop` 是控制平面、`PostgreSQL` 是持久事实来源且 `silent_fallback=false`。
- `source_downloaded=true` 只表示固定源码已在 `vendor/agent-engines`；CLI 的 `package_installed=true` 表示官方命令存在；`managed_ai_ready=true` 表示短期 BudgetLoop AI 继承可用；只有 `runtime_available=true` 才允许立即启动。任一条件不满足都会给出脱敏、可操作原因，不会退回 OpenHands。
- 运行 `scripts/fetch-agent-engines.sh` 可按 manifest 重建四个 detached shallow checkout。OpenHands 只下载 MIT core，明确排除另有条款的 `enterprise/`。

- `GET /api/work-containers?lifecycle=active&limit=50&offset=0` — 返回 `{ "containers": [...] }`。每项包含 `counts.sessions/running/waiting/attention` 和轻量 Session 摘要。
- `POST /api/work-containers` — 创建容器，不会隐式启动 Session。
  ```json
  {
    "name": "BudgetLoop 多会话协作",
    "project_goal": "实现隔离、可审计的多 Session 协作",
    "shared_context": "PostgreSQL 是唯一业务事实来源。",
    "base_workdir": "/workspace/project",
    "default_workspace_policy": "isolated|worktree"
  }
  ```
  `base_workdir` 必须是规范化绝对路径。
- `GET /api/work-containers/{container_id}` — 容器事实、共享上下文、派生计数与所属 Session 摘要。
- `PATCH /api/work-containers/{container_id}` — 可更新 `name`、`project_goal`、`shared_context`、`lifecycle_state`（`active|paused|completed|archived`）和默认 workspace 策略。
- `POST /api/work-containers/{container_id}/sessions` — 原子创建并启动 Session。
  - Header: `Idempotency-Key: <string>`（建议必传；重复提交返回现有 Session 且不重复投递）
  - Body:
    ```json
    {
      "role": "后端实现",
      "goal": "实现持久化与接口边界",
      "private_context": "仅此 Session 可见的已有判断",
      "acceptance_criteria": "可选",
      "template": "small_feature",
      "require_approval": true,
      "strategy": "dynamic",
      "budget": {"max_total_tokens":50000,"max_wall_time_seconds":1200,"max_active_runtime_seconds":600,"max_llm_calls":20,"max_cost":5,"max_parallel_llm_calls":2},
      "worktree_enabled": true
    }
    ```
  `worktree_branch` 与 `worktree_path` 不接受客户端输入，只由服务端 Session UUID 生成。
- `GET /api/work-containers/{container_id}/sessions/{session_id}` — Session 私有详情、预算和按时间排序的公开 transcript。跨容器或错误归属统一返回 404。
- `POST /api/work-containers/{container_id}/sessions/{session_id}/pause` — 幂等暂停该 Session 的当前 Run。
- `POST /api/work-containers/{container_id}/sessions/{recipient_session_id}/messages` — 创建显式消息或 Handoff。
  - Header: `Idempotency-Key: <string>`（可选）
  - Body: `{ "sender_session_id": "可空，同容器且不能等于接收者", "kind": "message|handoff", "content": "...", "metadata": {} }`
  - 返回的 `delivery_state` 初始为 `queued`。worker 只在下一轮 OpenHands `send_message` 成功后标记为 `delivered`；失败保持排队。

Session transcript 只包含操作员消息、显式 Handoff 与现有 `agent_message` 公开事件。它不会声称或暴露模型隐藏推理，也不会自动复制其他 Session 的私有上下文。

### Agent Team 模板与一键创建

- `GET /api/work-container-presets?category=game` — 返回 9 套内置团队、分类、角色预算、来源和 SOP。`runtime.graph` 明确为 `LangGraph`；CrewAI/MetaGPT 等来源会区分 `runtime` 与 `pattern`，且均不要求用户配置。
- `POST /api/work-container-presets/recommend` — 在本地 LangGraph 中按公开信号推荐最多 3 套团队，不调用远程模型。
  - Body: `{ "goal": "做一个手机解谜游戏试玩版", "industry": "游戏", "pace": "steady|fast", "risk": "steady|balanced|creative" }`
  - 返回项包含完整 `preset`、`confidence`（55–95）、`matched_signals`、可读 `reason` 和 `fallback`，不包含隐藏推理。
- `POST /api/work-containers/from-preset` — 在一个数据库事务内创建容器、2–8 个 Session、对应 Task/Run/预算/阶段，提交后按 SOP 激活波次投递。
  - Header: `Idempotency-Key: <8–100 chars>`（必传；重试返回原团队且不重复投递）
  - Body:
    ```json
    {
      "preset_id": "game-development",
      "preset_version": 1,
      "name": "星港谜案",
      "project_goal": "交付移动端解谜游戏试玩版",
      "shared_context": "首版只做一章",
      "base_workdir": "/workspace/game",
      "default_workspace_policy": "isolated|worktree",
      "default_execution_engine": "openhands|codex|gemini-cli|opencode",
      "folder_access": "isolated|full_access",
      "project_dir": "/Users/you/project",
      "full_access_acknowledged": false,
      "recommendation_source": "ai|local_fallback|manual",
      "role_overrides": [
        {"key":"designer","enabled":true,"role":"主策划","goal":"...","execution_engine":"codex","budget":{"max_total_tokens":24000}}
      ],
      "start_immediately": true
    }
    ```
  - 角色预算覆盖受服务端上限约束。Skills 只写入对应 Session 私有工作提示，不授予工具、权限或隐式跨 Session 上下文。
  - 旧客户端省略新增权限字段时仍默认为 `folder_access=isolated`，不需要 `project_dir`，且 `full_access_acknowledged` 必须为 `false`。
  - `full_access` 要求规范化且非敏感系统根的绝对 `project_dir`、`full_access_acknowledged=true` 和 `default_workspace_policy=worktree`；任何缺失或矛盾组合在事务开始前返回 422，不会静默降级。
  - 完全访问团队的每个 Session 都以服务端 Session UUID 生成独立 Git branch/worktree。客户端不能指定 branch/path；挂载或 Git 准备失败时 Run 可见失败，绝不回退到共享仓库根或隔离副本。
  - `recommendation_source` 只记录公开推荐来源；权限确认仍是独立的操作员授权。应用快照不会保存提示词全文、隐藏推理或供应商凭据。
  - `start_immediately=true` 要求每个所选引擎的 worker runtime 可用；“仅创建”允许先固化源码已下载但运行待启用的引擎，之后启动时会再次 preflight。
  - 返回 `{ "container": {...}, "created": true, "dispatch": { "accepted": [], "skipped": [], "warnings": [] } }`。详情中的 `preset_snapshot` 固化实际角色、来源、激活波次、Handoff、评审门禁和投递记录；历史团队不会随目录升级而漂移。
- `POST /api/work-containers/{container_id}/start` — 为“仅创建”团队投递尚未投递且仍为 `PENDING` 的所属 Runs。重复调用会在 `skipped` 中返回 `already_dispatched`，失败项留在 `warnings` 供重试。

手工 `POST /api/work-containers` 与单 Session 路径保持不变；其 `preset_id`、`preset_version`、`preset_snapshot` 均为 `null`。

## 观测数据

- `GET /api/runs/{run_id}/llm-calls` — 逐次调用列表（字段同 llm_calls 表）。
- `GET /api/runs/{run_id}/tool-calls` — 工具调用列表。
- `GET /api/runs/{run_id}/budget` — `{ "budget": {...}, "phases": [...], "reallocations": [...] }`。
- `GET /api/runs/{run_id}/events?after_seq=0` — `{ "events": [{"seq","type","payload","created_at"}...] }`。
- `GET /api/runs/{run_id}/report` — 最终报告 JSON（不存在则 404）。
- `GET /api/runs/{run_id}/report/export?format=json|md` — 导出。

显式协作送达会产生 `collaboration_delivered` 事件。事件只包含消息 ID、种类、发送/接收 Session 归属，不包含消息正文；正文仅出现在所属 Session transcript 与收件箱记录中。

## 审批

- `POST /api/approvals/{approval_id}/decide` — Body `{ "action": "approve|reject|modify", "note": "..." }`，幂等（已决策则返回当前状态）。

## 实时流

- `GET /api/runs/{run_id}/stream` — SSE。每条：`id: <seq>`，`data: {"seq","type","payload","created_at"}`。支持 `Last-Event-ID` 断线重连回放；run 终态后发送 `type=run_finished` 并关闭。

## 健康

- `GET /api/health` — `{ "status": "ok" }`（无需鉴权）。
