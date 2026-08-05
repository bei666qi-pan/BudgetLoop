## Why

BudgetLoop 现有 WorkContainer + WorkSession 提供了多 Agent 独立执行的基础能力，但缺乏统一的团队级观测面和控制面。操作员进入容器工作区后无法在 5 秒内判断团队整体健康状况、各 Agent 实时行为、预算消耗速率与超支风险，也无法在观测的同时执行暂停、预算调整、纠偏指令等控制操作。团队会话间的协作消息缺乏可控的状态机、防滥用保护和天花板限制，存在失控互聊和 Token 浪费的风险。本轮将现有多 Session 能力升级为可持续协作、实时观测、实时控制且不会失控消耗的团队工作空间。

## What Changes

- **团队级三栏观测台**：在桌面端保留左侧 Session 列表（状态/动作/用量压力/异常）、中间团队频道与单 Session 对话、右侧可折叠进度/用量/控制检查器。顶部栏展示团队状态、阶段、Token/费用/时间、连接状态及暂停/继续/停止。移动端使用"成员/对话/控制"标签。
- **团队对话协议**：操作员可向指定 Session 发消息；Session 间可提问/回答/澄清/Handoff；协调者可发布公开上下文；Agent 可发布简短进度/阻塞/交付摘要。每条消息记录 sender/receiver/type/time/idempotency_key/status。状态机为 queued→injected→acknowledged 或 failed。CLI 不能热注入时在安全检查点注入并诚实显示"等待下次执行检查点"。
- **防无限互聊机制**：仅允许显式 @目标或依赖关系触发自动响应；限制团队对话轮数/消息数/Token；消息去重；禁止自发自收、跨容器投递和广播式 N×N 回复；达到上限后暂停自动回复并请求用户决定。Handoff 只含结论/证据/未决问题/下一步。
- **团队进度观测**：每个 Session 展示状态/阶段/当前公开动作/最后活动/里程碑/下一步/阻塞/需用户处理/证据/迭代。团队展示运行/等待/暂停/阻塞/完成计数、激活阶段、未满足依赖、最近里程碑和下一关注项。仅明确有限里程碑时显示百分比。不额外调用 LLM 刷新进度。
- **团队用量观测**：团队总量和 Session 拆分均展示已用/预留/剩余 Token、费用、调用数、墙钟/活跃时间、并行数、消耗速度、预计耗尽时间及 NORMAL/CONSERVATIVE/CRITICAL 压力。默认仅 Token/费用/时间/健康状态，详情折叠。全部基于真实 llm_calls 和预算账本，缺失字段显示"未上报"。
- **团队实时控制**：团队级暂停/恢复/停止/调整预算/并行度/发送纠偏指令；Session 级暂停/恢复/取消/追加指令/调整预算。Pause/Resume/Cancel/预算更新幂等；取消需确认；预算不低于 used+reserved；修改前显示新旧值和影响；暂停后不启动新调用；加预算后显式恢复。SSE 断线显示数据可能过期。所有人工干预写入审计事件。guided/autonomous 切换需解释影响并确认。
- **统一 Agent 协调协议**：提示词约束 Agent 沟通行为——仅完成角色目标，协作消息简短发给明确接收者，真实里程碑才更新进度，阻塞时说明事实/已尝试/所需行动，不重复报活跃，升级协调者/操作员。预算压力升高时减少探索、复用证据、优先验收。完成声明附测试/文件/命令证据。
- **SSE 团队公开事件流**：团队级别的事件流聚合所有 Session 的公开事件、消息状态变更、进度更新和控制操作审计。

## Capabilities

### New Capabilities
- `team-observatory-dashboard`: 团队级三栏观测台 UI，含桌面端三栏布局和移动端标签式布局，状态/进度/用量/控制同屏展示
- `team-communication-protocol`: 团队对话协议，含消息状态机(queued/injected/acknowledged/failed)、幂等、防失控、CLI 安全检查点注入和诚实送达声明
- `team-progress-observability`: 团队和 Session 级结构化进度观测，基于真实里程碑而非心跳事件，不额外调用 LLM
- `team-budget-observatory`: 团队总量和 Session 拆分用量观测，Token/费用/时间/调用数/并行度/消耗速度/预计耗尽/压力模式，缺失字段显示"未上报"
- `team-runtime-control`: 团队级和 Session 级实时控制能力，含暂停/恢复/取消/预算调整/并行度/纠偏指令，幂等、审计、确认语义
- `agent-coordination-protocol`: 统一 Agent 协调协议，约束沟通行为、进度报告、阻塞升级、预算压力适应和完成声明规范

### Modified Capabilities
- `team-session-collaboration`: 扩展消息模型增加 type/idempotency_key/acknowledged 状态、防失控限制、CLI 安全检查点注入
- `autonomous-agent-team-execution`: 增加团队暂停/恢复/停止对自主模式的影响语义，guided/autonomous 运行时切换确认流程
- `work-container-lifecycle`: 容器级暂停/恢复/停止能力，团队状态派生，预算和并行度运行时调整
- `run-command-center`: 扩展为团队上下文中可感知容器归属和团队级控制
- `token-observatory`: 扩展支持团队总量聚合以及 team_id 维度的用量查询
- `operator-workspace`: 团队观测台作为 Agent Team 区域的主要操作界面
- `managed-runtime-budget-accounting`: 支持团队级预算聚合和预留一致性，避免重复结算

## Impact

- **API**: 新增 GET/POST/PATCH 团队观测台端点（事件流、用量聚合、控制操作），扩展现有 container/session 端点增加消息确认、进度更新、预算运行时 PATCH
- **Database**: 新增 `team_audit_events` 表（人工干预审计）、扩展现有 `session_messages` 表增加 type/idempotency_key/acknowledged_at 字段、新增 `session_progress_signals` 表（结构化进度）
- **Frontend**: 重构 `containers/[id]/page.tsx` 为团队观测台三栏布局，新增 `TeamObservatoryDashboard`、`TeamChat`、`TeamBudgetPanel`、`TeamControlBar` 等组件
- **Backend**: 新增 `app/api/team_observatory.py` 路由模块，扩展 `app/collaboration/service.py` 增加消息确认和防失控，扩展 `app/budget/manager.py` 增加团队聚合查询
- **SSE**: 新增团队级 `GET /api/work-containers/{id}/stream` SSE 端点，聚合 Session 公开事件
- **兼容性**: 旧单任务 Run 页面不受影响；旧容器页面保持可用但被新观测台替代为默认入口；CLI 引擎适配器增加安全检查点通知机制
