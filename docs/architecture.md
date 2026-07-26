# BudgetLoop 架构文档

## 总览

BudgetLoop 采用分层架构，按职责切分为：

- **Web UI**（Next.js）：用户界面，通过 REST + SSE 与控制面通信
- **Control Plane**（FastAPI）：任务管理、事件回放、审批决策、报告导出
- **PostgreSQL**：唯一业务事实来源——任务、预算、事件、评分、报告全部落库
- **Orchestrator Worker**（Dramatiq）：任务级状态机、预算预留/结算、确定性进展评分、压力模式、策略切换、审批闸门、崩溃恢复
- **OpenHands Agent Server**：Agent 推理与工具循环内核（复用，不重造）
- **Execution Engine Registry**：OpenHands、Codex、Gemini CLI、OpenCode 的固定源码、能力与可用性边界
- **LangGraph**：团队模板 SOP 激活与无 AI 时的确定性推荐降级；不接管执行、预算或存储
- **New API Gateway**：默认多协议模型网关；负责 OpenAI/Claude/Gemini 转换、渠道管理、权重/优先级、重试和限流
- **LiteLLM Proxy**：旧部署兼容 profile；保留自定义预算回调
- **Valkey**：工作队列、worker 心跳、短期缓存

## 数据流

```
User 创建任务 (Web UI)
  → POST /api/tasks (Control Plane)
  → 创建 task + task_run + task_budget + 6 task_phases (PostgreSQL)
  → enqueue run_id (Dramatiq/Valkey)
  → Worker 消费
  → Provision Workspace (Docker sibling container)
  → Create conversation (Agent Server)
  → Loop (每次一个 OpenHands step):
      1. 预留预算 (PG CAS UPDATE)
      2. 发送本轮指令，驱动 Agent 单步执行
      3. 订阅事件，收集 Action/Observation/Stats
      4. 按真实 usage 结算预算
      5. 运行测试，解析结果
      6. 计算确定性进展评分
      7. 压力模式重算 / 阶段预算重分配 / 策略切换 / checkpoint
      8. 写入事件 outbox (同事务)
  → 终态 → 最终报告 → SSE 推送 → 销毁 Workspace
```

## 关键模块

### 预算管理器 (`app/budget/manager.py`)

原子预留 SQL（PG 行锁串行化）：
```sql
UPDATE task_budgets
SET reserved_calls = reserved_calls + 1, ...
WHERE run_id = $1
  AND used_calls + reserved_calls < max_llm_calls
  AND used_tokens + reserved_tokens + $2 <= max_total_tokens
  AND used_cost + reserved_cost + $3 <= max_cost
  AND now() < deadline_at
RETURNING reserved_calls;
```
0 行 = 拒绝。并发请求不可能同时穿透同一 run 的剩余额度。

### 状态机 (`app/core/enums.py`)

13 个状态，合法转换表 `ALLOWED_TRANSITIONS` 编码了全部允许的路径。orchestrator 每次转换前校验，非法转换抛 `InvalidTransition`。

### 进展评分 (`app/scoring/`)

纯函数，禁止 LLM 参与。信号：测试失败/通过 Δ、编译错误 Δ、diff 行数、新观测数、动作重复指纹、回归检测。权重公开可调，每条评分存储信号快照。

### 压力模式 (`app/policy/pressure.py`)

双时间口径：wall clock 截止时间 + active runtime 执行时间。WAITING_APPROVAL/PAUSED 期间 active runtime 暂停累计。Token 剩余比例 < 20% 时至少升到 CONSERVATIVE。

### 策略切换 (`app/policy/strategy.py`)

规则：CRITICAL 压力 → `minimal_fix`；连续回归 → `rollback`；连续低分+重复动作 → `change_hypothesis`。

### AI 网关边界 (`app/ai_gateway/`)

默认直接使用固定版本 QuantumNous New API。BudgetLoop 只实现脱敏配置、健康检查和
有界 OpenAI-compatible 调用，不重写协议转换或路由。团队推荐优先调用配置的用途模型
别名，结果必须通过本地目录校验；任何网关或输出异常都回到 LangGraph 确定性推荐。

不引入“用一个 LLM 选择另一个 LLM”的语义路由；New API 原生渠道策略是唯一默认路由层。

### LiteLLM 预算回调 (`litellm/budget_callback.py`，兼容模式)

pre-call hook：从请求 metadata 取 `task_run_id`，对业务库执行原子预留 UPDATE，失败则拒绝调用。post-call hook：按响应 usage 结算。Virtual key `max_budget` 是第三道硬兜底。

### Agent Team 模板 (`app/team_presets/`)

团队目录采用 CrewAI 兼容的 `agents.role/goal/backstory` 与 `tasks.description/expected_output/agent` YAML 字段，并用 MetaGPT 风格 SOP stage 表达阶段、并行角色、Handoff 与评审门禁。LangGraph 是直接安装和执行的状态图运行时；CrewAI、MetaGPT、AutoGen、CAMEL、Semantic Kernel 仅作为经过高 Star 与维护状态核验的模式来源，不安装其完整 executor。OpenHands、PostgreSQL、BudgetLoop 预算和审批仍是权威执行边界。

### 可替换执行引擎 (`app/execution_engines/`)

BudgetLoop 是多 Agent 控制平面，OpenHands、Codex、Gemini CLI 和 OpenCode 是可替换执行引擎。注册表只暴露经过许可证与维护核验的固定 revision，并分别报告“源码已下载”“官方命令已安装”“受管 AI 已就绪”和“运行时可用”。适配层生成上游原生非交互命令并把 JSONL 事件归一化为公共消息/工具事实；thought/reasoning 类内部事件不进入公共 transcript。TaskRun 状态、预算预留、审批、workspace、Handoff 和事件持久化始终由 BudgetLoop/PostgreSQL 决定。

源码通过 `scripts/fetch-agent-engines.sh` 下载到 `vendor/agent-engines/`。四个 checkout 采用 detached shallow revision；OpenHands sparse checkout 排除 `enterprise/`。本地 worker 固定安装官方 Codex/Gemini CLI 包；只有命令、短期能力继承（或独立凭据）、原生协议、sandbox 和生命周期检查全部通过才可选择，禁止静默回退。

Codex 使用隔离的运行时 `config.toml` 连接 BudgetLoop Responses 代理；Gemini CLI 使用进程级 Gemini origin/model/capability。两者只看到 Run/Model scoped 短期凭据。BudgetLoop 在控制面校验 live Run、模型、请求大小与预算后转发给 New API，New API 承担协议转换和渠道路由。

## 目录结构

```
BudgetLoop/
├── backend/
│   ├── app/
│   │   ├── core/       # enums, models, config, db, security
│   │   ├── budget/     # TaskBudgetManager (CAS SQL)
│   │   ├── scoring/    # 确定性进展评分（纯函数）
│   │   ├── policy/     # pressure, strategy（纯函数决策）
│   │   ├── ai_gateway/ # 网关配置、脱敏健康与有界客户端
│   │   ├── events/     # SSE outbox（读写 execution_events）
│   │   ├── api/        # FastAPI 路由
│   │   ├── worker/     # Dramatiq actors, orchestrator, OpenHands client, workspace
│   │   └── artifacts/  # ArtifactStore 接口 + 实现
│   ├── alembic/        # 数据库迁移
│   └── tests/          # pytest
├── litellm/            # 兼容 profile：Dockerfile + config + 预算回调
├── vendor/ai-gateways/ # New API 固定 revision 与可复现源码
├── web/                # Next.js (App Router)
├── demo/               # 演示 fixtures
├── scripts/            # demo/eval/dev 脚本
└── docs/               # 文档
```

## 崩溃恢复

- Worker 租约通过 Valkey key + TTL 实现；过期后 sweeper 重新入队
- `conversation_id = uuid5(run_id)` 确定性，重启后通过 `GET /api/conversations/{id}` 重连
- Workspace 容器命名卷保留，可 attach 恢复
- SSE outbox：事件与状态变更同事务写入，前端按 `seq` 去重、`Last-Event-ID` 回放
- Checkpoint：每轮修改后 workspace 内 `git commit`，回滚即 `git reset --hard <ref>`
