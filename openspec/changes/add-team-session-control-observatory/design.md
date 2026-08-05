## Context

BudgetLoop 已具备 WorkContainer + WorkSession 多 Session 独立执行能力，通过 PostgreSQL 唯一事实源管理预算账本、SSE 事件流和协作消息。但当前 `containers/[id]/page.tsx` 工作区仍以原始三面板轮询方式运作，缺乏：

1. **团队级观测聚合**：无法在 5 秒内判断团队整体状态、每个 Agent 行为、预算消耗速率和超支风险
2. **观测与控制同屏**：查看进度需切换到 Run 页面，控制操作（暂停/预算调整）在不同路径
3. **消息状态机**：SessionMessage 只有 queued/delivered，无 ack 确认和幂等去重，CLI 引擎无法热注入时缺乏诚实反馈
4. **防失控机制**：无对话轮数/Token 上限、无自发自收/广播防护
5. **结构化进度**：进度仅由心跳事件推断，无 Agent 主动声明的里程碑/阻塞/证据
6. **团队用量聚合**：Token/费用视图限于单个 Run，无团队总量和预算耗尽预测
7. **SSE 断线处理**：当前仅轮询，无连接状态指示和过期数据提示

架构约束：FastAPI + PostgreSQL + SSE（不引入 WebSocket），复用现有 WorkContainer/WorkSession/TaskBudget/LlmCall/SessionMessage/ExecutionEvent 模型，预算账本为唯一记账来源。

## Goals / Non-Goals

**Goals:**
- 团队观测台作为 `/containers/[id]` 的默认视图，5 秒内呈现团队全貌
- 团队对话可控：消息状态机、幂等、防失控、CLI 安全检查点诚实反馈
- 进度不造假：基于 Agent 声明的结构化进度信号，不额外调用 LLM
- 用量基于真实数据：团队聚合从 llm_calls 和 task_budgets 实时计算
- 实时控制幂等可审计：Pause/Resume/Cancel/预算调整均写入审计事件
- 保持现有视觉方向，复用现有 CSS 组件类，不重建导航和页面结构
- 桌面三栏 + 移动端标签，390px 无横向溢出

**Non-Goals:**
- 不引入 WebSocket、GraphQL 或第二状态系统
- 不重写 Run 详情页面（仅扩展为团队上下文感知）
- 不修改旧单任务创建/运行流程
- 不暴露隐藏推理、凭据或其他 Session 的 private_context
- 不用动画、Token 或时间流逝伪造进度
- 不增加 LLM 调用以刷新进度

## Decisions

### D1: 团队 SSE 事件流复用现有 execution_events 表 + 新 team_events 视图

**选择**: 在 `execution_events` 表中增加 `container_id` 列（可为 null），新增 `GET /api/work-containers/{id}/stream` SSE 端点，查询 WHERE container_id = X 并按 seq 排序。旧 run 级 SSE 端点保持不变。

**替代方案**: 新建 team_events 表存储团队级事件。**否决**: 增加写入路径复杂度，跨表查询回放困难。现有 execution_events 的 seq 机制已成熟，加列成本低。

**理由**: 复用成熟的 SSE outbox 模式，增量查询 `after_seq`，`Last-Event-ID` 断线重连，与现有 `/api/runs/{id}/stream` 共享实现。

### D2: 消息状态机在 PostgreSQL 中实现，不在前端

**选择**: 在 `session_messages` 表增加 `message_type`（message/handoff/progress_update/system_fact）、`idempotency_key`（unique constraint）、`acknowledged_at`（timestamptz nullable）、`status`（queued/injected/acknowledged/failed）。状态转换由 worker 在安全检查点执行 SQL UPDATE。

**替代方案**: Redis pub/sub 管理状态。**否决**: 无法保证幂等去重和持久化一致性。

**理由**: PostgreSQL 唯一约束保证幂等；状态转换在同一个 worker 事务中与 delivery_event 原子提交；acknowledged 仅在 Agent 真实调用 `send_message` 成功时设置。

### D3: 团队用量聚合使用 PostgreSQL 聚合查询，不做预计算缓存

**选择**: `GET /api/work-containers/{id}/usage` 实时聚合所有所属 Session 的 `task_budgets` 和 `llm_calls`。不引入物化视图或缓存表。

**替代方案**: Redis 缓存或物化视图。**否决**: 预算数据变化频繁（每次 LLM 调用），缓存失效策略复杂且容易展示过期数据。团队规模小（2-8 个 Session），聚合查询在 <100ms 内完成。

**理由**: 简单正确，始终展示最新数据。若性能成为瓶颈，再考虑物化视图作为优化，不作为初始设计。

### D4: 进度信号由 Agent 声明，不推断

**选择**: 新增 `session_progress_signals` 表，Agent 通过结构化输出声明进度。字段：summary, milestone, completed_items, next_step, blocked, blocker_reason, needs_operator, evidence。仅当 Agent 实际声明时更新。心跳事件、工具调用不自动生成进度。

**替代方案**: 从 execution_events 推断进度。**否决**: 心跳只能证明活跃，不能代表完成。推断逻辑容易造假且难以维护。

**理由**: 进度声明是 Agent 协调协议的一部分，Agent 在 milestone 达成时主动声明。前端仅展示，不推测。

### D5: 防失控在控制平面强制执行，非纯提示词约束

**选择**: 在 `app/collaboration/service.py` 增加防失控检查：
- 去重：`idempotency_key` unique constraint 阻止重复消息
- 禁止自发自收：sender_session_id != recipient_session_id 约束
- 禁止跨容器：container_id 必须相同
- 轮数上限：单容器每分钟最多 N 条自动消息（worker 内计数器 + Valkey TTL），N 默认为 30，可通过 `PATCH /api/work-containers/{id}/budget` 的 `max_team_messages_per_minute` 字段配置
- 自动回复轮数上限：同一触发链最多 M 轮自动回复，M 默认为 5，可通过 `max_auto_reply_rounds` 字段配置
- Token 上限：inbox 消息累计 Token 不超过当前预算的 X%，X 默认为 5，可通过 `inbox_token_ratio` 字段配置
- 达到上限后：暂停该容器的自动回复，生成 audit_event，通知操作员

**理由**: 提示词只能约束行为意图，不能防止 bug 或无限循环。控制平面硬限制是唯一可靠的防失控手段。

### D6: 前端 SSE 连接使用 EventSource + 降级轮询

**选择**: 桌面端使用 `EventSource` 连接团队 SSE 端点。断线时自动重连（浏览器原生行为），重连期间显示"数据可能过期"标签。若 SSE 不可用（某些代理/防火墙），降级为 3s 轮询。移动端默认使用 5s 轮询以节省电量。

**替代方案**: 仅 SSE 不降级。**否决**: 企业代理环境可能拦截 SSE。

**理由**: 平衡实时性和兼容性。EventSource 原生支持 Last-Event-ID 回放，比手动 fetch 轮询更高效。

### D7: 审计事件表 team_audit_events 独立于 execution_events

**选择**: 新增 `team_audit_events` 表，记录所有人工干预操作（暂停/恢复/取消/预算调整/纠偏指令）。字段：id, container_id, session_id (nullable, team-level 时为 null), action, old_value (JSONB), new_value (JSONB), operator (from auth token), created_at。

**理由**: 审计事件与执行事件语义不同——审计事件是操作员触发的控制操作，执行事件是 Agent 触发的执行事实。分表避免混合语义，便于合规审计。

### D8: 桌面三栏 + 移动标签的布局策略

**选择**: 桌面端（≥1280px）使用 CSS Grid 三栏：左侧 SessionRail（w-72）、中间 TeamChat（flex-1）、右侧 Inspector（w-80）。移动端（<1280px）使用三标签切换：成员/对话/控制。审批、阻塞和超支风险跨标签通过顶部固定横幅展示。

**替代方案**: 移动端堆叠布局。**否决**: 堆叠布局导致"控制"不可达，违反观测与控制同屏原则。

**理由**: 标签式切换在 390px 可用，无横向溢出。关键告警（审批/阻塞/超支）跨标签可见确保操作员不错过。

## Design Details

### 用户路径

1. 操作员从导航进入 Agent Team → 团队列表页（现有）
2. 点击团队 → 团队观测台（新页面替换现有 container workspace）
3. 进入 5 秒内可判断：
   - 顶部栏：团队状态（运行中/暂停/阻塞）、阶段、Token/费用/时间、连接状态
   - 左侧：各 Session 状态、当前动作、用量压力
   - 中间：团队频道最新消息或选中 Session 对话
   - 右侧：进度/用量/控制检查器
4. 操作员可：发消息、暂停/恢复/停止、调整预算、查看详情
5. 点击单个 Session → 中间面板切换到该 Session 对话 + 右侧更新为该 Session 的详情
6. 深度调试 → 点击 Run ID 跳转到 Run 详情页（现有页面）

### 桌面端 ASCII 线框（≥1280px）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [BudgetLoop] [开始] [Agent Team] [新建] [设置]        ●已连接   [新建Session] │
├──────────────────────────────────────────────────────────────────────────────┤
│ ▲ 团队状态: 运行中  |  阶段: 实现+审查  |  Tokens: 45.2K/200K  |  ¥2.83/¥15  │
│   耗时: 12m  |  2/4 运行中  1 等待  1 阻塞  |  [暂停] [停止]                 │
├────────────────┬──────────────────────────────────────┬───────────────────────┤
│ Sessions        │ Team Channel / Session Chat           │ Inspector            │
│  (w-72)         │  (flex-1)                            │  (w-80)              │
│                 │                                      │                       │
│ [全部消息 ▾]    │ ┌──────────────────────────────────┐ │ [进度 ▾]              │
│                 │ │ 📢 Coordinator · 2m ago          │ │ ─────────────────     │
│ ● 后端实现      │ │ 共享上下文已更新：API契约v2       │ │ ✅ 后端实现           │
│   运行中·阶段3  │ │                                    │ │   完成: 数据模型+迁移 │
│   Tok 12.4K    │ │ 📤 后端实现 → 前端开发 · 1m ago   │ │   下一步: API路由实现 │
│   压力: NORMAL │ │ Handoff: 接口定义完成             │ │   证据: models.py L392│
│                 │ │ 接收方下一步:                       │ │                       │
│ ● 前端开发      │ │ 1. 使用POST /api/tasks            │ │ ◐ 前端开发           │
│   运行中·阶段2  │ │ 2. Budget字段见shared_context      │ │   里程碑: 组件创建     │
│   Tok 9.8K     │ │                                    │ │   完成: 3/5           │
│   压力: NORMAL │ │ 📋 测试编写 · just now             │ │   阻塞: 等待后端API   │
│                 │ │ [PROGRESS] 完成2/5测试用例        │ │   需操作员: 否        │
│ ● 测试编写      │ │                                    │ │                       │
│   运行中·阶段1  │ │ ⚠ System · 3m ago                 │ │ ⚪ 测试编写           │
│   Tok 3.1K     │ │ 测试编写Session预算消耗达70%       │ │   进行中: 编写测试用例 │
│   压力: CONSERV│ │                                    │ │                       │
│                 │ │                                    │ │ [用量 ▾]              │
│ ○ 代码审查      │ │ ┌──────────────────────────────┐  │ │ ─────────────────     │
│   等待中        │ │ │ 📝 @后端实现 接口文档的... │  │ │ 团队:                 │
│   依赖: 后端    │ │ │ [Session: 全部 ▾] [发送]    │  │ │ Tok 45.2K/200K(22.6%)│
│                 │ │ └──────────────────────────────┘  │ │ ¥2.83/¥15(18.9%)     │
│ ○ 文档编写      │ │                                    │ │ 耗时: 12m / 60m       │
│   等待中        │ │                                    │ │ 压力: NORMAL          │
│   依赖: 前端    │ │                                    │ │ 调用: 34/80           │
│                 │ │                                    │ │ 消耗: 1.3K tok/min    │
│                 │ │                                    │ │ 预计耗尽: 2h 15m      │
│                 │ │                                    │ │                       │
│                 │ │                                    │ │ [控制 ▾]              │
│                 │ │                                    │ │ ─────────────────     │
│                 │ │                                    │ │ 团队控制:             │
│                 │ │                                    │ │ [暂停] [恢复] [停止]  │
│                 │ │                                    │ │ 预算: 200K → [调整]   │
│                 │ │                                    │ │ 并行: 2 → [调整]      │
│                 │ │                                    │ │                       │
│                 │ │                                    │ │ 选中Session: 后端实现  │
│                 │ │                                    │ │ [暂停] [取消]         │
│                 │ │                                    │ │ 预算: 80K → [调整]    │
│                 │ │                                    │ │ 追加指令: [发送]      │
└────────────────┴──────────────────────────────────────┴───────────────────────┘
```

### 移动端 ASCII 线框（390px）

```
┌─────────────────────────┐
│ [BudgetLoop] [Team] [⚙] │
├─────────────────────────┤
│ ⚠ 测试编写 预算消耗70%  │ ← 跨标签告警横幅
│ 1 个阻塞 · 需处理       │
├─────────────────────────┤
│ 团队: 运行中  2/4 活跃  │
│ Tok 45.2K  ¥2.83  12m  │
│ [暂停] [停止]           │
├─────────────────────────┤
│ [成员] [对话] [控制]    │ ← 标签切换
├─────────────────────────┤
│                         │
│  (标签内容区域)          │
│                         │
│  成员标签: Session列表   │
│  对话标签: 团队频道      │
│  控制标签: 进度+用量     │
│            +控制操作     │
│                         │
└─────────────────────────┘
```

### 消息状态机

```
                ┌─────────┐
                │ queued  │ ← 消息创建时的初始状态
                └────┬────┘
                     │ worker 在安全检查点检测到消息
                     ▼
                ┌──────────┐
                │ injected │ ← 消息已注入到 Agent 的 iteration instruction
                └────┬─────┘
                     │ Agent 在 send_message 中确认收到
                     ▼
                ┌──────────────┐
           ┌───│ acknowledged │ ← 仅 Agent 真实确认时设置
           │   └──────────────┘
           │
           │   ┌────────┐
           └──►│ failed │ ← Agent 返回错误或超时未确认
               └────────┘
```

- `queued`: 用户或 Session 发送消息后的初始状态。前端显示"已排队"。
- `injected`: worker 已将消息注入到下一次 iteration prompt 中。CLI 引擎无法热注入时，前端显示"等待下次执行检查点"。
- `acknowledged`: Agent 在 `send_message` 工具调用中明确确认收到。`acknowledged_at` 记录时间戳。
- `failed`: Agent 返回错误、3 次注入后仍未确认或 Session 终止。前端显示"送达失败"。

CLI 引擎降级：CLI 引擎（Codex/Gemini CLI/OpenCode）不支持运行时热注入对话。消息在**安全检查点**（每次 iteration 开始前）注入。前端状态为 `queued` → `injected` 时显示"等待下次执行检查点"而非"已送达"。仅 Agent 调用 send_message 工具后状态才变为 `acknowledged`。

### 运行状态机（容器/Session）

```
容器状态:
  active ──[pause]──► paused ──[resume]──► active
     │                   │
     │                   └──[stop]──► completed
     │
     └──[stop]──► completed

Session 状态 (映射到 RunStatus):
  PENDING → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED
     │        │         │
     │        │         ├──[session_pause]──► PAUSED ──[session_resume]──► RUNNING
     │        │         │
     │        │         └──[session_cancel]──► CANCELLED
     │        │
     │        └──[container_pause]──► Session 保持 QUEUED 但不投递
     │
     └──[container_pause]──► 不投递；[container_resume]──► 投递
```

- 容器级暂停：暂停所有 RUNNING Session 的当前 Run，阻止 QUEUED/PENDING Session 投递。已在 QUEUED 中的 Run 等待安全检查点后不启动新 LLM 调用。
- Session 级暂停：仅暂停指定 Session 的 Run，不影响其他 Session。
- 停止不可逆；暂停快速可逆（< 1 秒）。
- guided/autonomous 切换：运行时切换需明确确认。自主模式暂停后恢复时重新评估阶段依赖。

### 预算一致性

```
团队预算聚合 = SUM(各 Session task_budget.used_*) 
                + SUM(各 Session task_budget.reserved_*)
                （不含 completed/failed/cancelled Session 的 reserved）
团队预算上限 = SUM(各 Session task_budget.max_*)
                （不含 unlimited 标记的 Session，unlimited 显示为"∞"）
```

- 预算调整 PATCH 遵循 `new_max >= used + reserved` 约束，不满足返回 422。
- 预算耗尽后增加额度不会静默恢复——需显式调用 Resume 端点。
- 调低并行度 `max_parallel_llm_calls` 仅影响新发起的 LLM 调用，已在途的不中断。
- 所有预算修改写入 `team_audit_events` 记录 old/new 值。
- 费用聚合：仅当 `estimated_cost` 字段非 null 时计入，否则显示"未上报"。
- 保留语义：`reserved_*` 仅对 RUNNING/QUEUED 状态的 Session 计为"已预留"。

### SSE 数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Worker       │────►│ execution_   │────►│ SSE Endpoint │
│ emit_event() │     │ events 表    │     │ poll/notify  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                    ┌──────────────┐              │
                    │ EventSource  │◄─────────────┘
                    │ (前端)       │
                    └──────┬───────┘
                           │ 断线？
                           ▼
                    ┌──────────────┐
                    │ 降级轮询 3s  │
                    │ Last-Event-ID│
                    └──────────────┘
```

- `GET /api/work-containers/{id}/stream`: 团队 SSE，事件类型包含 `session_message`, `session_progress`, `session_status_change`, `team_control_audit`, `budget_pressure_change`。
- `Last-Event-ID` 回放：客户端断开后重连，自动从最后收到的 seq 继续。
- 断线指示：前端在 >10s 未收到事件时显示"数据可能过期"（黄色），>30s 显示"已断开"（红色）。
- 事件大小控制：单事件 payload 不超过 4KB。

### API 变化

**新增端点：**

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/api/work-containers/{id}/stream` | 团队 SSE 事件流 |
| `GET` | `/api/work-containers/{id}/usage` | 团队用量聚合 |
| `GET` | `/api/work-containers/{id}/progress` | 团队进度聚合 |
| `POST` | `/api/work-containers/{id}/pause` | 容器级暂停（幂等） |
| `POST` | `/api/work-containers/{id}/resume` | 容器级恢复（幂等） |
| `POST` | `/api/work-containers/{id}/stop` | 容器级停止（需确认） |
| `PATCH` | `/api/work-containers/{id}/budget` | 运行时调整预算/并行度 |
| `POST` | `/api/work-containers/{id}/correct` | 发送纠偏指令 |
| `POST` | `/api/work-containers/{id}/messages/{msg_id}/acknowledge` | 消息确认回调 |

**修改端点：**

| 方法 | 路径 | 变化 |
|------|------|------|
| `POST` | `/api/work-containers/{id}/sessions/{sid}/messages` | 增加 `message_type`, `idempotency_key`, 返回 `status` |
| `GET` | `/api/work-containers/{id}` | 增加 `team_status`, `usage_summary`, `progress_summary` |
| `GET` | `/api/containers` | 列表项增加 `team_status`, `alert_count` |
| `PATCH` | `/api/work-containers/{id}/sessions/{sid}/pause` | 记录 audit event |
| `PATCH` | `/api/work-containers/{id}/sessions/{sid}/resume` | 新增 resume 端点 |

### 数据模型变化

**session_messages 表新增列：**

```sql
ALTER TABLE session_messages ADD COLUMN message_type VARCHAR(32) NOT NULL DEFAULT 'message';
ALTER TABLE session_messages ADD COLUMN idempotency_key VARCHAR(128);
ALTER TABLE session_messages ADD COLUMN acknowledged_at TIMESTAMPTZ;
ALTER TABLE session_messages ALTER COLUMN delivery_state SET DEFAULT 'queued';
CREATE UNIQUE INDEX idx_session_messages_idempotency ON session_messages(idempotency_key) WHERE idempotency_key IS NOT NULL;
```

**新增表：**

```sql
CREATE TABLE team_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_id UUID NOT NULL REFERENCES work_containers(id),
    session_id UUID REFERENCES work_sessions(id),
    action VARCHAR(64) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    operator VARCHAR(256) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE session_progress_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES work_sessions(id),
    run_id UUID NOT NULL REFERENCES task_runs(id),
    summary TEXT,
    milestone TEXT,
    completed_items JSONB DEFAULT '[]',
    next_step TEXT,
    blocked BOOLEAN NOT NULL DEFAULT false,
    blocker_reason TEXT,
    needs_operator BOOLEAN NOT NULL DEFAULT false,
    evidence TEXT,
    iteration INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**execution_events 表新增列：**

```sql
ALTER TABLE execution_events ADD COLUMN container_id UUID REFERENCES work_containers(id);
CREATE INDEX idx_execution_events_container ON execution_events(container_id, seq) WHERE container_id IS NOT NULL;
```

### CLI 能力降级

CLI 引擎（Codex/Gemini CLI/OpenCode）的限制：

1. **热注入不可用**：CLI 进程启动后无法在运行时推入新消息。消息在每次 iteration 开始前的安全检查点注入。
2. **进度声明受限**：CLI 无原生 send_message 工具，进度信号依赖 Agent 在 `iteration_complete` 事件中结构化输出。
3. **确认延迟**：消息从 queued → injected → acknowledged 的延迟大于 server 引擎（多一轮 iteration）。

降级策略：
- 前端状态明确标注"等待下次执行检查点"，不虚构实时送达
- CLI 适配器中扩展 `normalize_json_line()` 识别进度声明和确认
- CLI worker 在每个 iteration 结束和开始时检查注入队列和确认状态

适配器扩展：在 `CLIEngineAdapter` 中增加 `check_injection_point()` 和 `extract_progress_signal()` 方法。

### 防失控机制

| 机制 | 实现位置 | 硬/软限制 |
|------|----------|-----------|
| 消息去重 (idempotency_key) | PostgreSQL unique constraint | 硬 |
| 禁止自发自收 | application 层 CHECK | 硬 |
| 禁止跨容器投递 | application 层 FK 约束 | 硬 |
| 容器每分钟消息上限 (默认 30) | Valkey TTL + worker 计数器 | 硬 |
| 自动回复轮数上限 (默认 5 轮) | worker 计数器 (per-session) | 硬 |
| Inbox 累计 Token 上限 (当前预算 5%) | 预算查询 + worker 校验 | 硬 |
| 禁止广播式 N×N 回复 | app 层显式 recipient 必须 | 硬 |
| 达到上限后行为 | 暂停自动回复 + audit_event + 前端通知 | 硬 |
| Agent behavior 约束 | 提示词 (运行时注入) | 软 |

### 迁移兼容

1. **session_messages 列迁移**：新增列设置 DEFAULT 值，非 nullable 列使用默认值填充现有行。
2. **execution_events container_id**：新建列允许 NULL，旧事件保持 NULL，新事件填充 container_id。
3. **前端路由**：`/containers/[id]` 页面完全替换为新观测台。旧页面组件保留但路由不可达。
4. **API 兼容**：现有端点响应增加新字段（`team_status`, `alert_count` 等），但不删除或重命名现有字段。旧客户端忽略未知字段。
5. **单任务 Run**：不受影响。`container_id` 为 NULL 的事件在 SSE 查询中自动被过滤。

### 测试策略

**后端 (pytest)：**
- 消息状态机：queued → injected → acknowledged 完整转换链路
- 消息幂等：同 idempotency_key 重复提交返回已有消息
- 禁止自发自收/跨容器：边界条件 422
- 防失控：达到消息上限后自动回复暂停
- 预算一致性：团队聚合 = SUM(Session)，调整拒绝 used+reserved 以下
- SSE 回放：Last-Event-ID 断线重连正确
- 暂停/恢复/取消：幂等性、run 状态正确
- 审计事件：每次人工干预均写入
- CLI 安全检查点注入：消息在正确 timing 注入

**前端 (Vitest)：**
- 团队用量聚合展示：Token/费用/时间正确格式化
- 缺失字段显示"未上报"而非 0
- 进度声明展示（非心跳推断）
- SSE 断线过期提示
- 桌面和 390px 移动端布局无横向溢出
- 键盘/读屏/reduced-motion
- 消息状态标签正确
- 预算调整确认弹窗 old/new 值对比

## Risks / Trade-offs

- **[风险] SSE 断线期间错过事件** → 缓解：EventSource 自动重连 + Last-Event-ID 回放，恢复后自动补全。
- **[风险] 团队用量聚合在大团队（8+ Session）性能下降** → 缓解：当前上限 8 Session，聚合 <100ms。若扩展，后续引入物化视图优化。
- **[风险] Agent 不遵守协调协议（不声明进度、不确认消息）** → 缓解：进度缺失时前端显示"Agent 未声明进度"，消息超时 3 次注入后标记 failed。控制平面硬限制防失控。
- **[风险] CLI 引擎确认延迟导致操作员以为消息丢失** → 缓解：前端诚实标注"等待下次执行检查点"，区分 server 引擎和 CLI 引擎状态。
- **[风险] 会话预算耗尽后增加额度但操作员忘了恢复** → 缓解：加预算后返回 `needs_resume: true` 标志，前端显示"已增加预算，请点击恢复"按钮。
- **[风险] 三栏布局在 1280px 笔记本上拥挤** → 缓解：SessionRail 72px + Inspector 80px = 152px 侧栏，中间约 1128px 可用。Inspector 默认折叠部分区块。用户可手动折叠侧栏。

## Open Questions (Resolved)

1. **团队对话上限参数可配置**：通过 `PATCH /api/work-containers/{id}/budget` 提供 `max_team_messages_per_minute`、`max_auto_reply_rounds`、`inbox_token_ratio` 字段。默认值作为启动值（30 条/分钟、5 轮、5% Token），操作员可运行时调整，无需重启。
2. **纠偏指令注入策略**：在下一次 iteration 前追加为高优先级系统消息（`role: system, priority: high`），置于 Agent prompt 顶部，不替换现有 prompt 内容。
3. **暂停时在途 LLM 调用**：等待完成（不启动新调用），避免浪费已在途的 Token。
