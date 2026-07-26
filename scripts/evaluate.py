#!/usr/bin/env python3
"""BudgetLoop 策略评测脚本。

同一 task 建三个 run（strategy=none/fixed/dynamic），等待全部终态后
从 API 拉取 llm_calls / test_result 事件 / report，统计各策略表现，
输出 markdown 表格到 docs/evaluation-results.md。

原则：只统计 API 真实返回的数据；数据缺失记 "n/a"，严禁编造。
无 LLM_API_KEY 时打印可复现说明并以退出码 0 结束（不跑评测）。

用法：
    python scripts/evaluate.py [--api-base http://localhost:8000] \
        [--token budgetloop-dev-token] [--rounds 1]
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_STATUSES = {"COMPLETED", "PARTIAL_COMPLETED", "FAILED", "BUDGET_EXHAUSTED", "CANCELLED"}
STRATEGIES = ["none", "fixed", "dynamic"]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "evaluation-results.md"

TASK_BODY = {
    "name": "评测：修复订单服务库存超扣",
    "description": (
        "demo/order-service 在并发下 POST /orders 超卖、库存变负。"
        "请定位根因并修复，使 tests/test_concurrency.py 全绿。"
    ),
    "workdir": "/workspace/project",
    "template": "fix_bug",
    "require_approval": False,
    "fixture": "order-service",
    "budget": {
        "max_total_tokens": 200000,
        "max_wall_time_seconds": 1800,
        "max_active_runtime_seconds": 900,
        "max_llm_calls": 60,
        "max_cost": 5.0,
        "max_parallel_llm_calls": 2,
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BudgetLoop 策略评测")
    p.add_argument("--api-base", default=os.environ.get("API_BASE", "http://localhost:8000"))
    p.add_argument("--token", default=os.environ.get("API_TOKEN", "budgetloop-dev-token"))
    p.add_argument("--rounds", type=int, default=1, help="重复轮数（每轮 3 个 run）")
    p.add_argument("--poll-interval", type=float, default=10.0)
    p.add_argument("--timeout", type=float, default=2400.0, help="单个 run 最长等待秒数")
    return p.parse_args()


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ApiClient:
    def __init__(self, base: str, token: str):
        import httpx  # 延迟导入，保证 --help / 无 key 路径不依赖 httpx

        self._client = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def get(self, path: str, **kwargs):
        return self._client.get(path, **kwargs)

    def post(self, path: str, json: dict):
        return self._client.post(path, json=json)


def create_runs(api: ApiClient) -> dict[str, str]:
    """建一个 task + 三个不同 strategy 的 run，返回 {strategy: run_id}。"""
    body = dict(TASK_BODY, strategy="none")
    resp = api.post("/api/tasks", json=body)
    resp.raise_for_status()
    created = resp.json()
    task_id = created["task_id"]
    runs = {"none": created["run_id"]}
    for strategy in ("fixed", "dynamic"):
        resp = api.post(f"/api/tasks/{task_id}/runs", json={"strategy": strategy})
        resp.raise_for_status()
        runs[strategy] = resp.json()["run_id"]
    return runs


def wait_terminal(api: ApiClient, run_id: str, poll: float, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        resp = api.get(f"/api/runs/{run_id}")
        resp.raise_for_status()
        detail = resp.json()
        status = detail["run"]["status"]
        if status in TERMINAL_STATUSES:
            return detail
        if time.monotonic() > deadline:
            raise TimeoutError(f"run {run_id} 超过 {timeout}s 未到终态（当前 {status}）")
        time.sleep(poll)


def fetch_all_events(api: ApiClient, run_id: str) -> list[dict]:
    events: list[dict] = []
    after_seq = 0
    while True:
        resp = api.get(f"/api/runs/{run_id}/events", params={"after_seq": after_seq})
        resp.raise_for_status()
        batch = resp.json().get("events", [])
        if not batch:
            return events
        events.extend(batch)
        after_seq = batch[-1]["seq"]


def test_pass_rate(events: list[dict]) -> float | None:
    """从 test_result 事件统计通过率；无法判定返回 None。"""
    passed = failed = 0
    for e in events:
        if e.get("type") != "test_result":
            continue
        payload = e.get("payload") or {}
        v = payload.get("passed")
        if v is None:
            status = str(payload.get("status", "")).lower()
            if status in ("passed", "pass", "success", "ok"):
                v = True
            elif status in ("failed", "fail", "error"):
                v = False
        if v is True:
            passed += 1
        elif v is False:
            failed += 1
    total = passed + failed
    return passed / total if total else None


def collect_run_metrics(api: ApiClient, run_id: str) -> dict:
    detail = wait_terminal(api, run_id, POLL_INTERVAL, RUN_TIMEOUT)
    run = detail["run"]
    budget = detail.get("budget") or {}

    calls_resp = api.get(f"/api/runs/{run_id}/llm-calls")
    calls_resp.raise_for_status()
    calls = calls_resp.json()
    if isinstance(calls, dict):  # 兼容 {"calls": [...]} 包装
        calls = calls.get("calls", calls.get("llm_calls", []))

    events = fetch_all_events(api, run_id)

    report_resp = api.get(f"/api/runs/{run_id}/report")
    report = report_resp.json() if report_resp.status_code == 200 else None

    calls_by_kind: dict[str, int] = {}
    ineffective = 0
    token_sum = 0
    for c in calls:
        kind = c.get("call_kind") or "unknown"
        calls_by_kind[kind] = calls_by_kind.get(kind, 0) + 1
        if c.get("effective") is False:
            ineffective += 1
        token_sum += c.get("total_tokens") or 0

    started, finished = parse_ts(run.get("started_at")), parse_ts(run.get("finished_at"))
    wall_seconds = (finished - started).total_seconds() if started and finished else None

    return {
        "status": run.get("status"),
        "completed": run.get("status") == "COMPLETED",
        "total_tokens": budget.get("used_tokens", token_sum),
        "wall_seconds": wall_seconds,
        "active_seconds": (run.get("active_runtime_ms") or 0) / 1000.0,
        "llm_calls": len(calls),
        "calls_by_kind": calls_by_kind,
        "test_pass_rate": test_pass_rate(events),
        "ineffective_calls": ineffective,
        "strategy_switches": sum(1 for e in events if e.get("type") == "strategy_switched"),
        "has_report": report is not None,
    }


def fmt(value, ndigits: int = 1) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{ndigits}f}"
    return str(value)


def aggregate(rows: list[dict]) -> dict:
    def mean(key):
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return statistics.mean(vals) if vals else None

    kinds: dict[str, float] = {}
    for r in rows:
        for k, v in r["calls_by_kind"].items():
            kinds[k] = kinds.get(k, 0) + v / len(rows)
    return {
        "completed": f"{sum(1 for r in rows if r['completed'])}/{len(rows)}",
        "total_tokens": mean("total_tokens"),
        "wall_seconds": mean("wall_seconds"),
        "active_seconds": mean("active_seconds"),
        "llm_calls": mean("llm_calls"),
        "calls_by_kind": kinds,
        "test_pass_rate": mean("test_pass_rate"),
        "ineffective_calls": mean("ineffective_calls"),
        "strategy_switches": mean("strategy_switches"),
    }


def render_markdown(results: dict[str, list[dict]], rounds: int) -> str:
    lines = [
        "# BudgetLoop 策略评测结果",
        "",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 轮数：{rounds}（每轮 strategy=none/fixed/dynamic 各 1 个 run，同一 task）",
        f"- 任务：{TASK_BODY['name']}（fixture=order-service，预算见脚本 TASK_BODY）",
        "- 数据来源：control-plane API 实测值；缺失记 n/a。",
        "",
        "| 指标 | none | fixed | dynamic |",
        "| --- | --- | --- | --- |",
    ]
    aggs = {s: aggregate(results[s]) for s in STRATEGIES}

    def row(label, key, pct=False):
        cells = []
        for s in STRATEGIES:
            v = aggs[s][key]
            if pct and isinstance(v, float):
                cells.append(f"{v * 100:.1f}%")
            else:
                cells.append(fmt(v))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    row("完成（COMPLETED）", "completed")
    row("总 token", "total_tokens")
    row("wall 时间 (s)", "wall_seconds")
    row("active 时间 (s)", "active_seconds")
    row("LLM 调用数", "llm_calls")
    for kind in sorted({k for a in aggs.values() for k in a["calls_by_kind"]}):
        cells = [fmt(aggs[s]["calls_by_kind"].get(kind, 0)) for s in STRATEGIES]
        lines.append(f"| 　其中 call_kind={kind} | " + " | ".join(cells) + " |")
    row("测试通过率", "test_pass_rate", pct=True)
    row("无效调用数（effective=false）", "ineffective_calls")
    row("策略切换次数", "strategy_switches")

    lines += [
        "",
        "## 各 run 明细",
        "",
        "| strategy | 轮次 | status | tokens | wall(s) | active(s) | 调用数 | 通过率 | 无效调用 | 策略切换 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in STRATEGIES:
        for i, r in enumerate(results[s], 1):
            rate = f"{r['test_pass_rate'] * 100:.1f}%" if isinstance(r.get("test_pass_rate"), float) else "n/a"
            lines.append(
                f"| {s} | {i} | {r['status']} | {r['total_tokens']} | {fmt(r['wall_seconds'])} | "
                f"{fmt(r['active_seconds'])} | {r['llm_calls']} | {rate} | "
                f"{r['ineffective_calls']} | {r['strategy_switches']} |"
            )
    lines.append("")
    return "\n".join(lines)


POLL_INTERVAL = 10.0
RUN_TIMEOUT = 2400.0


def main() -> int:
    global POLL_INTERVAL, RUN_TIMEOUT
    args = parse_args()
    POLL_INTERVAL = args.poll_interval
    RUN_TIMEOUT = args.timeout

    if not os.environ.get("LLM_API_KEY"):
        print(
            "未检测到 LLM_API_KEY，跳过评测（退出码 0）。\n"
            "复现步骤：\n"
            "  1. cp .env.example .env，填入真实 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL\n"
            "  2. set -a && source .env && set +a\n"
            "  3. docker compose up -d（postgres/valkey/new-api/control-plane/worker 全部健康）\n"
            f"  4. python scripts/evaluate.py --api-base {args.api_base} --rounds {args.rounds}\n"
            "评测只统计 API 实测数据，不会生成任何模拟结果。"
        )
        return 0

    try:
        import httpx  # noqa: F401
    except ImportError:
        print("缺少依赖 httpx：pip install httpx（建议在虚拟环境中）", file=sys.stderr)
        return 2

    api = ApiClient(args.api_base, args.token)
    results: dict[str, list[dict]] = {s: [] for s in STRATEGIES}

    for round_no in range(1, args.rounds + 1):
        print(f"== 第 {round_no}/{args.rounds} 轮：创建 task + 3 个 run")
        runs = create_runs(api)
        for strategy, run_id in runs.items():
            print(f"   strategy={strategy} run_id={run_id}")
        for strategy, run_id in runs.items():
            print(f"   等待 {strategy} ({run_id}) 到终态...")
            metrics = collect_run_metrics(api, run_id)
            print(f"   {strategy}: status={metrics['status']} tokens={metrics['total_tokens']}")
            results[strategy].append(metrics)

    md = render_markdown(results, args.rounds)
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    print(f"\n结果已写入 {OUTPUT_PATH}\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
