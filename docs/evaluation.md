# BudgetLoop 评测说明

## 评测目标

对比三种策略在同一任务上的表现，验证 BudgetLoop 动态预算策略的量化效果。

## 策略

| 策略 | 说明 |
|---|---|
| `none` | 无预算基线——Agent 不感知任何预算限制，完整执行 |
| `fixed` | 固定预算，静态分配——有用量上限但不做动态调整 |
| `dynamic` | BudgetLoop 动态预算——阶段重分配、压力模式、策略切换 |

## 运行评测

### 前置条件

1. 完整的 Docker Compose 环境启动（`docker compose up -d`）
2. 有效的 LLM API Key
3. order-service fixture 可访问

### 执行脚本

```bash
python scripts/evaluate.py \
  --api-base http://localhost:8000 \
  --token budgetloop-dev-token \
  --rounds 3
```

参数说明：
- `--api-base`：Control Plane 地址
- `--token`：API 鉴权令牌
- `--rounds`：每种策略重复次数（≥1，越多越有统计意义）

### 采集指标

| 指标 | 来源 |
|---|---|
| 是否完成任务 | `final_report.status == "COMPLETED"` |
| 总 Token | `llm_calls.total_tokens` 累加（`token_source=actual`） |
| 总 Wall Time | `run.finished_at - run.started_at` |
| 总 Active Runtime | `run.active_runtime_ms` |
| LLM 调用次数 | `llm_calls` 行数（按 `call_kind` 拆分） |
| 测试通过率 | 最后一条 `test_results` 的 `passed / (passed+failed)` |
| 无效调用次数 | `llm_calls.effective == false` 的计数 |
| 策略切换次数 | `final_report.strategy_switches` 条目数 |

### 输出

```markdown
# BudgetLoop Evaluation Results

| Strategy | Rounds | % Complete | Avg Tokens | Avg Wall Time | Avg Calls | % Passed | Ineffective Calls | Switches |
|----------|--------|------------|------------|---------------|-----------|----------|-------------------|----------|
| none     | 3      | 67%        | 124,500    | 980s          | 18.3      | 82%      | 4.0               | 0        |
| fixed    | 3      | 33%        | 48,000     | 1200s         | 8.0       | 67%      | 2.0               | 0        |
| dynamic  | 3      | 67%        | 58,000     | 780s          | 9.7       | 85%      | 1.3               | 2.3      |
```

结果写入 `docs/evaluation-results.md`。

### 无 LLM API Key 时

评测脚本会输出可复现说明：

```
No LLM_API_KEY configured. To run the evaluation with real models:
  1. Set LLM_API_KEY in .env
  2. Start docker compose
  3. Run: python scripts/evaluate.py --rounds 3

Results will be written to docs/evaluation-results.md
```

**严禁编造实验结论。**

## 评测脚本技术细节

- 使用 Python stdlib + httpx（与后端同一依赖，无需额外安装）
- 任务定义同 `scripts/demo.sh`（order-service fixture）
- 串行执行各 run（避免并发预算干扰）
- 等待超时：5 分钟/run（可配置）
- 优雅处理任务失败/超时（部分指标记为 N/A）
