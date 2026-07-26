#!/usr/bin/env bash
# BudgetLoop 正常预算演示：
#   创建任务（fixture=order-service，预算充足）→ 轮询 run 直到终态 → 打印报告 URL。
#
# 用法：API_TOKEN=xxx ./scripts/demo.sh
# 环境变量：
#   API_BASE   control-plane 地址（默认 http://localhost:8000）
#   API_TOKEN  静态令牌（默认 budgetloop-dev-token，与 .env.example 一致）
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-budgetloop-dev-token}"

for cmd in curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "缺少依赖: $cmd"; exit 1; }
done

echo "==> 创建任务（fixture=order-service，预算充足）"
# fixture 字段为契约扩展（见 docs/api-contract.md 的任务字段；
# backend 未识别时会按 pydantic 默认行为忽略多余字段，不影响演示）。
create_resp=$(curl -sfS -X POST "$API_BASE/api/tasks" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-order-service-$(date +%s)" \
  -d '{
    "name": "修复订单服务库存超扣",
    "description": "demo/order-service 在并发下 POST /orders 超卖、库存变负。请定位根因并修复，使 tests/test_concurrency.py 全绿。",
    "workdir": "/workspace/project",
    "template": "fix_bug",
    "require_approval": false,
    "strategy": "dynamic",
    "fixture": "order-service",
    "budget": {
      "max_total_tokens": 200000,
      "max_wall_time_seconds": 1800,
      "max_active_runtime_seconds": 900,
      "max_llm_calls": 60,
      "max_cost": 5.0,
      "max_parallel_llm_calls": 2
    }
  }')
echo "$create_resp" | jq .
task_id=$(echo "$create_resp" | jq -r .task_id)
run_id=$(echo "$create_resp" | jq -r .run_id)
echo "task_id=$task_id run_id=$run_id"

# --- 轮询 run 状态直到终态 ---
TERMINAL='^(COMPLETED|PARTIAL_COMPLETED|FAILED|BUDGET_EXHAUSTED|CANCELLED)$'
deadline=$(( $(date +%s) + 1800 ))
status=""
echo "==> 轮询 run 状态（最长 30 分钟）"
while [ "$(date +%s)" -lt "$deadline" ]; do
  run_json=$(curl -sfS "$API_BASE/api/runs/$run_id" -H "Authorization: Bearer $API_TOKEN")
  status=$(echo "$run_json" | jq -r .run.status)
  iteration=$(echo "$run_json" | jq -r .run.iteration)
  used_tokens=$(echo "$run_json" | jq -r .budget.used_tokens)
  used_calls=$(echo "$run_json" | jq -r .budget.used_calls)
  echo "  status=$status iteration=$iteration used_calls=$used_calls used_tokens=$used_tokens"
  if [[ "$status" =~ $TERMINAL ]]; then
    break
  fi
  sleep 5
done

if [[ ! "$status" =~ $TERMINAL ]]; then
  echo "!! 超时未到终态，最后状态: $status"
  exit 1
fi

echo "==> run 终态: $status"
echo "报告(JSON):  curl -H 'Authorization: Bearer $API_TOKEN' $API_BASE/api/runs/$run_id/report | jq ."
echo "报告(Markdown): $API_BASE/api/runs/$run_id/report/export?format=md"
echo "Web 查看:   http://localhost:3000/runs/$run_id"
