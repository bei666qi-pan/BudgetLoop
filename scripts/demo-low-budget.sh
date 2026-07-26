#!/usr/bin/env bash
# BudgetLoop 受限预算演示：
#   同一 order-service 修复任务，但预算卡得很紧（max_llm_calls=4、
#   max_total_tokens=8000），预期 run 以 BUDGET_EXHAUSTED 或
#   PARTIAL_COMPLETED 收尾，而不是盲目烧钱跑到底。
#
# 用法：API_TOKEN=xxx ./scripts/demo-low-budget.sh
# 环境变量同 demo.sh（API_BASE / API_TOKEN）。
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-budgetloop-dev-token}"

for cmd in curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "缺少依赖: $cmd"; exit 1; }
done

echo "==> 创建任务（fixture=order-service，受限预算 max_llm_calls=4 / max_total_tokens=8000）"
create_resp=$(curl -sfS -X POST "$API_BASE/api/tasks" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-low-budget-$(date +%s)" \
  -d '{
    "name": "修复订单服务库存超扣（受限预算）",
    "description": "demo/order-service 在并发下 POST /orders 超卖、库存变负。请定位根因并修复，使 tests/test_concurrency.py 全绿。",
    "workdir": "/workspace/project",
    "template": "fix_bug",
    "require_approval": false,
    "strategy": "dynamic",
    "fixture": "order-service",
    "budget": {
      "max_total_tokens": 8000,
      "max_wall_time_seconds": 1800,
      "max_active_runtime_seconds": 900,
      "max_llm_calls": 4,
      "max_cost": 0.5,
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
  used_calls=$(echo "$run_json" | jq -r .budget.used_calls)
  remaining_calls=$(echo "$run_json" | jq -r .budget.remaining_calls)
  echo "  status=$status used_calls=$used_calls remaining_calls=$remaining_calls"
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
if [[ "$status" =~ ^(BUDGET_EXHAUSTED|PARTIAL_COMPLETED)$ ]]; then
  echo "符合预期：预算受限场景以 $status 收尾（预算护栏生效，未超支）。"
else
  echo "注意：预期 BUDGET_EXHAUSTED/PARTIAL_COMPLETED，实际 $status（任务也可能在 4 次调用内碰巧修好）。"
fi
echo "报告(JSON):  curl -H 'Authorization: Bearer $API_TOKEN' $API_BASE/api/runs/$run_id/report | jq ."
echo "Web 查看:   http://localhost:3000/runs/$run_id"
