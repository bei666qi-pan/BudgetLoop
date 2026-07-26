#!/usr/bin/env bash
# BudgetLoop 本地裸跑开发环境（backend + worker + web，不走 docker 应用镜像）。
#
# 前提：
#   1. 基础设施已起：docker compose up -d postgres valkey new-api
#      （postgres/valkey/new-api 仍由 compose 提供，本脚本只裸跑应用进程）
#   2. 环境变量已加载：set -a && source .env && set +a
#      注意裸跑时 DATABASE_URL/REDIS_URL/LITELLM_BASE_URL 的主机名要指向
#      localhost（compose 里的 postgres/valkey/new-api 主机名只在容器网络内有效），
#      例如：
#        export DATABASE_URL=postgresql://budgetloop:...@localhost:5432/budgetloop
#        export REDIS_URL=redis://localhost:6379/0
#        export LITELLM_BASE_URL=http://localhost:4000
#   3. backend 依赖已装（pip install -e backend/ 或 uv sync），web 依赖已装（npm i）
set -euo pipefail
cd "$(dirname "$0")/.."

# --- 依赖检查 ---
missing=0
for cmd in python3 node npm; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "缺少依赖: $cmd"; missing=1; }
done
python3 -c "import uvicorn" 2>/dev/null || { echo "缺少 Python 依赖: uvicorn（先装 backend 依赖）"; missing=1; }
python3 -c "import dramatiq" 2>/dev/null || { echo "缺少 Python 依赖: dramatiq（先装 backend 依赖）"; missing=1; }
[ "$missing" -eq 0 ] || exit 1

: "${DATABASE_URL:?需要 DATABASE_URL（指向 localhost 的业务库）}"
: "${REDIS_URL:?需要 REDIS_URL}"
: "${LITELLM_BASE_URL:?需要 LITELLM_BASE_URL}"

PIDS=()
cleanup() {
  echo "停止子进程..."
  kill "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- backend control-plane（uvicorn, :8000） ---
echo "启动 control-plane: uvicorn app.main:app :8000"
(cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
PIDS+=($!)

# --- dramatiq worker ---
# 注意：worker 需要能访问 docker.sock 以拉起 workspace 容器，
# 裸跑时本机必须有 Docker 且 AGENT_SERVER_IMAGE 可拉取。
echo "启动 worker: dramatiq app.worker.actors"
(cd backend && python3 -m dramatiq app.worker.actors -p 1 -t 4) &
PIDS+=($!)

# --- web（next dev, :3000） ---
echo "启动 web: next dev :3000"
(cd web && npm run dev) &
PIDS+=($!)

echo "全部已启动：web http://localhost:3000  api http://localhost:8000"
wait
