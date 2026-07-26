# Demo 操作指南

## 前置条件

1. Docker 29+ 可用
2. 合法授权的模型上游与 New API 网关 Token
3. 项目仓库位于 `/BudgetLoop`

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，更换 NEW_API_SESSION_SECRET；首次启动后在 New API 控制台
# 配置上游、budgetloop-recommendation 别名并创建 AI_GATEWAY_API_KEY

# 2. 一键启动所有服务
docker compose up -d

# 3. 验证各服务健康
curl http://localhost:8000/api/health  # Control Plane
curl http://localhost:3001/api/status  # New API
curl http://localhost:3000             # Web UI
```

## 场景一：正常预算演示（完整修复闭环）

```bash
bash scripts/demo.sh
```

该脚本执行以下步骤：

1. 创建任务：修复订单接口并发超扣——针对 `demo/order-service/` fixture
2. Budget: `max_total_tokens=100000, max_llm_calls=20, max_cost=5.0, max_wall_time=1200s`
3. 等待循环执行（worker 自动驱动 OpenHands）
4. 打开运行页链接，观察：
   - **Loop 时间线**：计划→扫描→分析→修改→验证→修复→完成的完整轨迹
   - **LLM 调用表**：每一次调用按 agent/condenser 分类，Token/耗时/费用/评分
   - **预算视图**：已用 vs 剩余、阶段预算分布、燃尽趋势
   - 若出现危险命令，**审批弹窗**要求确认
5. 查看最终报告：验收标准是否达成、修改文件、测试结果、总量统计、策略调整

预期：Agent 识别出 check-then-act 竞态根因 → 将扣减改为原子 SQL → 测试全绿 → COMPLETED。

## 场景二：受限预算演示（压力模式与部分完成）

```bash
bash scripts/demo-low-budget.sh
```

Budget: `max_total_tokens=8000, max_llm_calls=4, max_wall_time=600s, max_active_runtime=300s`

预期：

1. Agent 在前期阶段正常进行
2. 中途 token 或时间紧张，压力模式从 NORMAL → CONSERVATIVE 或 CRITICAL
3. 停止大范围分析，专注最小修复
4. 若预算耗尽→ BUDGET_EXHAUSTED，输出**部分完成但可解释的报告**
5. 报告中展示：已发现根因（check-then-act），建议修改为原子 SQL，剩余预算不足以完成验证

## Demo Fixture 说明

### `demo/order-service/` (正式演示)

轻量 FastAPI + psycopg 订单服务。

- **Bug**：`POST /orders` 先 SELECT 后 UPDATE，并发下库存被重复扣减成负数
- **表面现象**：偶发失败、库存为负——不是数据库故障，是应用层竞态
- **正确修法**：`UPDATE products SET stock = stock - :q WHERE id = :id AND stock >= :q RETURNING stock` 一条原子 SQL
- **朴素陷阱**：加 sleep/重试只能掩盖个别情况，并发压测仍然超扣
- **测试**：16 线程并发的 `test_concurrent_orders_never_oversell` 稳定复现

### `demo/smoke-fixture/` (快速冒烟)

纯 stdlib Python unittest——用于快速自检，不依赖 PostgreSQL。

## 观察要点

1. **不是单次超长模型调用**：每一轮 BudgetLoop iteration = 一个 OpenHands step
2. **工具结果是真实的**：Shell 命令实际在工作区容器内执行，测试输出来自真实测试运行
3. **评分基于确定性信号**：失败测试减少加分、重复动作扣分——不是 LLM 主观"这个改动好不好"
4. **压力模式变化可追溯**：时间线中的 `pressure_changed` 事件解释了升级时机与原因
5. **策略切换有据可查**：连续低分 → `change_hypothesis`，回归累积 → `rollback`，CRITICAL → `minimal_fix`
