"""BudgetLoop LiteLLM 预算拦截回调。

加载方式（以官方文档为准，https://docs.litellm.ai/docs/proxy/logging
"Custom Callback Class [Async]" 一节）：config.yaml 中
`litellm_settings: callbacks: budget_callback.proxy_handler_instance`，
LiteLLM 从 config.yaml 同目录 import 本模块并取模块级实例
`proxy_handler_instance`，挂入 litellm.callbacks。

钩子签名以 litellm/integrations/custom_logger.py 源码为准：
- async_pre_call_hook(user_api_key_dict, cache, data, call_type)
    返回修改后的 dict 放行；raise 异常拒绝调用。
- async_post_call_success_hook(data, user_api_key_dict, response)
- async_post_call_failure_hook(request_data, original_exception,
    user_api_key_dict, traceback_str=None)

职责：把 worker 的 step 粒度预算预留细化到每一次真实 LLM HTTP 调用
（含 condenser 与 SDK 内部重试——它们都会重新过 pre-call 钩子）。
SQL 语义与 backend/app/budget/manager.py 的 RESERVE/SETTLE/RELEASE 保持一致。

fail 策略：
- pre-call 阶段 fail-closed：DB 出错即拒绝调用（宁可误拒，不可超支）；
- post-call 阶段只 log 不阻断（调用已发生，账务问题另行补偿）。
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Optional, Union

import psycopg
from litellm.exceptions import BudgetExceededError
from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger("budgetloop.budget_callback")

DEFAULT_EST_TOKENS = 4000
DEFAULT_EST_COST = 0.02

# --- SQL：与 backend/app/budget/manager.py 语义一致（psycopg 命名占位符） ---

RESERVE_SQL = """
UPDATE task_budgets
SET reserved_calls  = reserved_calls + 1,
    reserved_tokens = reserved_tokens + %(est_tokens)s,
    reserved_cost   = reserved_cost + %(est_cost)s
WHERE run_id = %(run_id)s
  AND used_calls + reserved_calls < max_llm_calls
  AND used_tokens + reserved_tokens + %(est_tokens)s <= max_total_tokens
  AND used_cost + reserved_cost + %(est_cost)s <= max_cost
  AND EXISTS (SELECT 1 FROM task_runs WHERE id = %(run_id)s AND (deadline_at IS NULL OR now() < deadline_at))
RETURNING reserved_calls
"""

SETTLE_SQL = """
UPDATE task_budgets
SET used_calls      = used_calls + 1,
    used_tokens     = used_tokens + %(actual_tokens)s,
    used_cost       = used_cost + %(actual_cost)s,
    reserved_calls  = GREATEST(reserved_calls - 1, 0),
    reserved_tokens = GREATEST(reserved_tokens - %(est_tokens)s, 0),
    reserved_cost   = GREATEST(reserved_cost - %(est_cost)s, 0)
WHERE run_id = %(run_id)s
"""

RELEASE_SQL = """
UPDATE task_budgets
SET reserved_calls  = GREATEST(reserved_calls - 1, 0),
    reserved_tokens = GREATEST(reserved_tokens - %(est_tokens)s, 0),
    reserved_cost   = GREATEST(reserved_cost - %(est_cost)s, 0)
WHERE run_id = %(run_id)s
"""

# llm_calls 表由 backend 用 SQLAlchemy 建表，id 无 DB 侧默认值，
# 必须显式 gen_random_uuid()（PG13+ 内置）。
# ON CONFLICT (call_id) DO NOTHING：worker 会以同一 call_id upsert 补全，
# 这里只登记 call_kind='other' 的网关侧记录，冲突即视为 worker 已写，跳过。
_INSERT_COLUMNS = """
INSERT INTO llm_calls (
    id, run_id, call_id, iteration, call_kind, agent_name, model, provider,
    started_at, ended_at, duration_ms,
    prompt_tokens, completion_tokens, reasoning_tokens,
    cache_read_tokens, cache_write_tokens, total_tokens,
    token_source, estimated_cost, finish_reason, request_status, retry_count
) VALUES (
    gen_random_uuid(), %(run_id)s, %(call_id)s, 0, 'other', 'litellm-callback',
    %(model)s, %(provider)s,
    now(), now(), NULL,
    %(prompt_tokens)s, %(completion_tokens)s, %(reasoning_tokens)s,
    %(cache_read_tokens)s, %(cache_write_tokens)s, %(total_tokens)s,
    'actual', %(estimated_cost)s, %(finish_reason)s, %(request_status)s, 0
)
"""
INSERT_LLM_CALL_SQL = _INSERT_COLUMNS + "\nON CONFLICT (call_id) DO NOTHING"

# 兼容退路：若业务库尚未给 llm_calls.call_id 加唯一约束，
# ON CONFLICT (call_id) 会报 InvalidColumnReference，退化为 NOT EXISTS 守卫。
_INSERT_VALUES = """
    gen_random_uuid(), %(run_id)s, %(call_id)s, 0, 'other', 'litellm-callback',
    %(model)s, %(provider)s,
    now(), now(), NULL,
    %(prompt_tokens)s, %(completion_tokens)s, %(reasoning_tokens)s,
    %(cache_read_tokens)s, %(cache_write_tokens)s, %(total_tokens)s,
    'actual', %(estimated_cost)s, %(finish_reason)s, %(request_status)s, 0
"""
INSERT_LLM_CALL_FALLBACK_SQL = (
    "INSERT INTO llm_calls (id, run_id, call_id, iteration, call_kind, agent_name, model, provider,"
    " started_at, ended_at, duration_ms, prompt_tokens, completion_tokens, reasoning_tokens,"
    " cache_read_tokens, cache_write_tokens, total_tokens, token_source, estimated_cost,"
    " finish_reason, request_status, retry_count)\n"
    "SELECT " + _INSERT_VALUES +
    "\nWHERE NOT EXISTS (SELECT 1 FROM llm_calls WHERE call_id = %(call_id)s)"
)


# --- 模块级懒建连接池（最小实现：有界、按需建连、坏连接丢弃重建） ---


class _AsyncPool:
    def __init__(self, dsn: str, max_size: int = 4):
        self._dsn = dsn
        self._max_size = max_size
        self._idle: asyncio.LifoQueue = asyncio.LifoQueue()
        self._created = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> psycopg.AsyncConnection:
        try:
            return self._idle.get_nowait()
        except asyncio.QueueEmpty:
            pass
        async with self._lock:
            if self._created < self._max_size:
                self._created += 1
                try:
                    return await psycopg.AsyncConnection.connect(self._dsn)
                except Exception:
                    self._created -= 1
                    raise
        return await self._idle.get()

    async def release(self, conn: psycopg.AsyncConnection) -> None:
        if conn.closed or conn.broken:
            async with self._lock:
                self._created -= 1
            try:
                await conn.close()
            except Exception:
                pass
            return
        self._idle.put_nowait(conn)


_pool: Optional[_AsyncPool] = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> _AsyncPool:
    global _pool
    async with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("BUDGETLOOP_DATABASE_URL")
            if not dsn:
                raise RuntimeError("BUDGETLOOP_DATABASE_URL not set")
            _pool = _AsyncPool(dsn)
    return _pool


async def _execute(sql: str, params: dict) -> list:
    """短事务执行一条 SQL，返回 fetchall 结果。"""
    pool = await _get_pool()
    conn = await pool.acquire()
    try:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                if cur.description is not None:
                    return await cur.fetchall()
                return []
    finally:
        await pool.release(conn)


async def _insert_llm_call(params: dict) -> None:
    try:
        await _execute(INSERT_LLM_CALL_SQL, params)
    except psycopg.errors.InvalidColumnReference:
        # call_id 上无唯一约束（backend 尚未加），退化方案
        logger.warning("llm_calls.call_id has no unique constraint; using NOT EXISTS fallback")
        await _execute(INSERT_LLM_CALL_FALLBACK_SQL, params)


# --- 从 litellm 对象安全取值的工具 ---


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_usage(response: Any) -> dict:
    usage = _get(response, "usage") or {}
    completion_details = _get(usage, "completion_tokens_details")
    prompt_details = _get(usage, "prompt_tokens_details")
    return {
        "prompt_tokens": _get(usage, "prompt_tokens"),
        "completion_tokens": _get(usage, "completion_tokens"),
        "total_tokens": _get(usage, "total_tokens"),
        "reasoning_tokens": _get(completion_details, "reasoning_tokens"),
        # OpenAI: prompt_tokens_details.cached_tokens（cache read）
        "cache_read_tokens": _get(prompt_details, "cached_tokens"),
        # Anthropic: cache_creation_input_tokens（cache write）
        "cache_write_tokens": _get(usage, "cache_creation_input_tokens"),
    }


def _extract_finish_reason(response: Any) -> Optional[str]:
    choices = _get(response, "choices") or []
    if choices:
        return _get(choices[0], "finish_reason")
    return None


def _meta(data: Optional[dict]) -> dict:
    return ((data or {}).get("metadata") or {})


def _estimates(meta: dict) -> tuple[int, float]:
    return (
        int(meta.get("est_tokens", DEFAULT_EST_TOKENS)),
        float(meta.get("est_cost", DEFAULT_EST_COST)),
    )


class BudgetLoopBudgetHandler(CustomLogger):
    """每次真实 LLM HTTP 调用的预算预留/结算/释放。"""

    async def async_pre_call_hook(
        self,
        user_api_key_dict,
        cache,
        data: dict,
        call_type: str,
    ) -> Optional[Union[Exception, str, dict]]:
        meta = _meta(data)
        run_id = meta.get("task_run_id")
        if not run_id:
            # demo 简化：未携带 task_run_id 的调用（如手工 curl 调试）直接放行。
            logger.info("budget-callback: no task_run_id in metadata, allowing call unchecked")
            return data

        est_tokens, est_cost = _estimates(meta)
        try:
            rows = await _execute(
                RESERVE_SQL,
                {"run_id": run_id, "est_tokens": est_tokens, "est_cost": est_cost},
            )
        except Exception as exc:
            # fail-closed：账务不可用时拒绝调用
            logger.exception("budget-callback: reserve DB error, rejecting call (fail-closed)")
            raise BudgetExceededError(
                current_cost=0.0,
                max_budget=0.0,
                message=f"BudgetLoop: budget ledger unavailable, rejecting call for run {run_id}: {exc}",
            )
        if not rows:
            raise BudgetExceededError(
                current_cost=0.0,
                max_budget=0.0,
                message=(
                    f"BudgetLoop: budget exhausted or deadline passed for run {run_id} "
                    f"(est_tokens={est_tokens}, est_cost={est_cost})"
                ),
            )
        return data

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict,
        response: Any,
    ) -> Any:
        try:
            meta = _meta(data)
            run_id = meta.get("task_run_id")
            if not run_id:
                return response
            est_tokens, est_cost = _estimates(meta)

            usage = _extract_usage(response)
            hidden = getattr(response, "_hidden_params", None) or {}
            cost = hidden.get("response_cost")
            actual_tokens = usage["total_tokens"] or 0
            actual_cost = float(cost) if cost is not None else 0.0

            await _execute(
                SETTLE_SQL,
                {
                    "run_id": run_id,
                    "est_tokens": est_tokens,
                    "est_cost": est_cost,
                    "actual_tokens": actual_tokens,
                    "actual_cost": actual_cost,
                },
            )
            await _insert_llm_call(
                {
                    "run_id": run_id,
                    "call_id": data.get("litellm_call_id") or _get(response, "id") or str(uuid.uuid4()),
                    "model": _get(response, "model"),
                    "provider": hidden.get("custom_llm_provider"),
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "reasoning_tokens": usage["reasoning_tokens"],
                    "cache_read_tokens": usage["cache_read_tokens"],
                    "cache_write_tokens": usage["cache_write_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "estimated_cost": cost,
                    "finish_reason": _extract_finish_reason(response),
                    "request_status": "success",
                }
            )
        except Exception:
            # post-call 阶段不阻断：调用已发生，账务异常只记录
            logger.exception("budget-callback: settle/log failed (non-blocking)")
        return response

    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict,
        traceback_str: Optional[str] = None,
    ) -> None:
        try:
            meta = _meta(request_data)
            run_id = meta.get("task_run_id")
            if not run_id:
                return None
            est_tokens, est_cost = _estimates(meta)

            await _execute(
                RELEASE_SQL,
                {"run_id": run_id, "est_tokens": est_tokens, "est_cost": est_cost},
            )
            await _insert_llm_call(
                {
                    "run_id": run_id,
                    "call_id": request_data.get("litellm_call_id") or str(uuid.uuid4()),
                    "model": request_data.get("model"),
                    "provider": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "reasoning_tokens": None,
                    "cache_read_tokens": None,
                    "cache_write_tokens": None,
                    "total_tokens": None,
                    "estimated_cost": None,
                    "finish_reason": None,
                    "request_status": "failed",
                }
            )
        except Exception:
            logger.exception("budget-callback: release/log failed (non-blocking)")
        return None


# config.yaml 中 callbacks: budget_callback.proxy_handler_instance 引用的实例
proxy_handler_instance = BudgetLoopBudgetHandler()
