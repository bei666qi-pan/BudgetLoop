# Competition Summary —— 面向评委的说明

## 真实业务问题

当前主流 Coding Agent（GitHub Copilot、Cursor、v0 等）的主要痛点是**缺乏运行时可观测的预算感知闭环**。它们可以提供代码建议，但：

- 无法对每一次 LLM 调用做细粒度的使用统计与成本控制
- 无法在 Token/时间/费用超支时主动降级或改变策略
- 工具调用结果依赖于模型"声称"，而非真实执行
- 低效和重复调用无法被系统性识别
- 失败后没有结构化的自我修复能力

BudgetLoop 解决的是**"Agent 不知道自己花了多少钱、有没有用，也不会在预算不够时自己收手"**的问题。

## Loop Engineering 如何落地

Loop Engineering 的核心理念是**感知→决策→执行→反馈→优化**的闭环。BudgetLoop 在每个环节的实现如下：

### 1. 感知（Perceive）

- **逐次 LLM 调用观测**：每一次真实 HTTP 调用的 prompt/completion/reasoning/cache tokens、TTFT、duration、cost、finish_reason 全部独立记录
- **工具执行追踪**：每个工具调用的名称、参数、开始/结束时间、退出码、输出摘要、存储引用
- **测试反馈实时采集**：解析真实测试运行输出，提取 pass/fail/skip 计数作为信号
- **执行事件时间线**：所有状态变更、阶段切换、预算更新、策略调整以事件流形式推送

### 2. 决策（Decide）

- **原子预算预检**：每次 LLM 调用前，对 PostgreSQL 执行条件 UPDATE（CAS 语义），并发安全地防止穿透额度
- **多层边界**：worker 层预留（step 粒度） + New API Token/渠道配额；旧部署仍可显式使用 LiteLLM 回调 profile
- **双时间预算**：wall-clock 绝对截止（等待审批也流逝） + active runtime 执行时间（审批等待期间暂停）
- **压力模式自适应**：剩余资源比例驱动 NORMAL → CONSERVATIVE → CRITICAL 升级
- **确定性进展评分**：测试通过/失败 δ、编译错误 δ、diff 规模、动作指纹重复检测——纯计算函数，无 LLM 参与

### 3. 执行（Execute）

- **复用 OpenHands V1 SDK 作推理与工具循环内核**：不重造通用 Agent Loop，站在开源肩膀上
- **每个 task_run 一个独立 Workspace 容器**：隔离工作目录、资源限制、文件系统沙箱
- **`max_iteration_per_run=1`**：一个 BudgetLoop iteration 只驱动一个 OpenHands step，保证预算控制的粒度和精度

### 4. 反馈（Feedback）

- **测试执行的真实证据**：验证修改后的代码是否满足验收标准
- **git diff 比较**：确认修改范围是否合理、是否引入无关变更
- **动作指纹去重**：检测相同工具+相同参数的重复调用
- **回归检测**：通过测试减少或失败增加且 diff 无变化 → 标记回归

### 5. 优化（Optimize）

- **阶段预算重分配**：阶段提前完成 → 余额转入后续阶段；高消耗低进展 → 封顶并转移资源
- **策略切换**：连续低分+重复动作 → 改变假设/扩大证据；回归累积 → 回滚 checkpoint；CRITICAL 压力 → 最小修复
- **审批闸门**：危险动作需人工确认；拒绝理由作为反馈重新规划
- **部分完成**：预算耗尽时输出可解释的中间结果与后续建议，而非直接崩溃

## 核心创新

1. **逐次调用的预算原子拦截**：不是"事后统计"或"前端显示"，是 PostgreSQL 行锁串行化的预检+预留+结算三段式记账，并发安全的硬上限
2. **网关可替换架构**：worker 预算预留 + New API 网关配额；旧部署可保留 LiteLLM 逐调用回调
3. **双时间口径压力模式**：wall clock 与 active runtime 分别计算，审批等待不计入执行时间
4. **可解释的确定性评分**：不用 LLM 自评，信号是事实，评分是公开权重的算术
5. **复用而非重造**：OpenHands/Codex/Gemini CLI/OpenCode 做执行引擎，New API 做多协议网关，BudgetLoop 只做控制面

## 可量化效果（评测框架）

通过 `scripts/evaluate.py` 对比 A（无预算）/ B（固定静态预算）/ C（BudgetLoop 动态预算）三组：

| 指标 | 采集方式 |
|---|---|
| 是否完成任务 | final report status |
| 总 Token | llm_calls 累加 (token_source=actual) |
| 总 Wall/Active 时间 | task_runs.finished_at - started_at / active_runtime_ms |
| LLM 调用次数 | llm_calls 计数 (按 call_kind 拆分) |
| 测试通过率 | test_results 最后一条 |
| 无效调用次数 | effective=false 的 llm_calls 计数 |
| 策略切换次数 | strategy_switches 记录数 |

## 演示流程

```bash
cp .env.example .env && vim .env  # 填 Key
docker compose up -d              # 一键启动
bash scripts/demo.sh              # 正常预算 → 完整修复
bash scripts/demo-low-budget.sh   # 受限预算 → 降级演示
open http://localhost:3000        # 观察实时时间线
```

## 与现有开源 Agent 的差异

| | OpenHands | AutoGPT/Copilot | BudgetLoop |
|---|---|---|---|
| 预算硬上限 | 无 | 无 | 有（PG 原子 CAS）|
| 调用预算与网关配额 | 无 | 无 | 有（worker+New API；LiteLLM 兼容）|
| 压力模式降级 | 无 | 无 | 有（双时间口径）|
| 进展自评 | 无 | 依赖 LLM 判断 | 确定性信号（无 LLM）|
| 可配置审批 | 无 | 无 | 有（拒绝后重规划）|
| Agent 内核 | 自己就是 | 自己实现 | 复用 OpenHands |
