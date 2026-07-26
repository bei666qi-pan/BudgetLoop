#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

export SKIP_MIGRATIONS=${SKIP_MIGRATIONS:-1}
export API_TOKEN=${API_TOKEN:-budgetloop-dev-token}

(
  cd "$ROOT/backend"
  exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$ROOT/web"
  export NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE:-http://127.0.0.1:8000}
  export NEXT_PUBLIC_API_TOKEN=${NEXT_PUBLIC_API_TOKEN:-$API_TOKEN}
  exec npm run dev -- --hostname 127.0.0.1 --port 3000
)
