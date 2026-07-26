"""Comprehensive tests for the LiteLLM budget callback (P0 module)."""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest
from litellm.exceptions import BudgetExceededError

# --- Import the module under test ---
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "litellm"))
from budget_callback import (  # noqa: E402
    DEFAULT_EST_COST,
    DEFAULT_EST_TOKENS,
    INSERT_LLM_CALL_FALLBACK_SQL,
    INSERT_LLM_CALL_SQL,
    RELEASE_SQL,
    RESERVE_SQL,
    SETTLE_SQL,
    BudgetLoopBudgetHandler,
    _AsyncPool,
    _estimates,
    _extract_finish_reason,
    _extract_usage,
    _get,
    _get_pool,
    _meta,
    proxy_handler_instance,
)

pytestmark = pytest.mark.unit


# ============================================================================
# _get
# ============================================================================


class _FakeObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_get_dict_access():
    assert _get({"a": 1}, "a") == 1


def test_get_dict_missing_key_default():
    assert _get({"a": 1}, "b") is None
    assert _get({"a": 1}, "b", "fallback") == "fallback"


def test_get_object_access():
    obj = _FakeObj(a=42)
    assert _get(obj, "a") == 42


def test_get_object_missing_attr_default():
    obj = _FakeObj(a=42)
    assert _get(obj, "b") is None
    assert _get(obj, "b", "fallback") == "fallback"


def test_get_none_object():
    assert _get(None, "a") is None
    assert _get(None, "a", 99) == 99


# ============================================================================
# _extract_usage
# ============================================================================


def test_extract_usage_openai_style():
    response = {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
            "prompt_tokens_details": {"cached_tokens": 10},
            "completion_tokens_details": {"reasoning_tokens": 50},
        }
    }
    result = _extract_usage(response)
    assert result["prompt_tokens"] == 100
    assert result["completion_tokens"] == 200
    assert result["total_tokens"] == 300
    assert result["cache_read_tokens"] == 10  # OpenAI cached_tokens = cache read
    assert result["reasoning_tokens"] == 50
    assert result["cache_write_tokens"] is None  # no Anthropic-style field


def test_extract_usage_anthropic_style():
    response = {
        "usage": {
            "prompt_tokens": 500,
            "completion_tokens": 800,
            "total_tokens": 1300,
            "cache_creation_input_tokens": 200,
        }
    }
    result = _extract_usage(response)
    assert result["prompt_tokens"] == 500
    assert result["cache_write_tokens"] == 200


def test_extract_usage_minimal_response():
    response = {"usage": {"total_tokens": 50}}
    result = _extract_usage(response)
    assert result["total_tokens"] == 50
    assert result["prompt_tokens"] is None
    assert result["cache_read_tokens"] is None


def test_extract_usage_empty_usage():
    response = {"usage": {}}
    result = _extract_usage(response)
    assert result["total_tokens"] is None


def test_extract_usage_none_response():
    result = _extract_usage(None)
    assert result["total_tokens"] is None


# ============================================================================
# _extract_finish_reason
# ============================================================================


def test_extract_finish_reason_standard():
    response = {"choices": [{"finish_reason": "stop"}]}
    assert _extract_finish_reason(response) == "stop"


def test_extract_finish_reason_empty_choices():
    assert _extract_finish_reason({"choices": []}) is None


def test_extract_finish_reason_no_choices_key():
    assert _extract_finish_reason({}) is None


# ============================================================================
# _meta / _estimates
# ============================================================================


def test_meta_standard():
    data = {"metadata": {"task_run_id": "run-123"}}
    assert _meta(data) == {"task_run_id": "run-123"}


def test_meta_missing():
    assert _meta(None) == {}
    assert _meta({}) == {}


def test_estimates_explicit():
    meta = {"est_tokens": 2000, "est_cost": 0.05}
    tokens, cost = _estimates(meta)
    assert tokens == 2000
    assert cost == 0.05


def test_estimates_defaults():
    tokens, cost = _estimates({})
    assert tokens == DEFAULT_EST_TOKENS
    assert cost == DEFAULT_EST_COST


# ============================================================================
# SQL syntax verification
# ============================================================================


def test_reserve_sql_clauses():
    sql = RESERVE_SQL
    assert "UPDATE task_budgets" in sql
    assert "WHERE run_id" in sql
    assert "RETURNING reserved_calls" in sql
    assert "EXISTS (SELECT 1 FROM task_runs" in sql
    assert "reserved_calls + 1" in sql


def test_settle_sql_clauses():
    sql = SETTLE_SQL
    assert "UPDATE task_budgets" in sql
    assert "GREATEST(reserved_calls - 1, 0)" in sql
    assert "GREATEST(reserved_tokens - %(est_tokens)s, 0)" in sql
    assert "GREATEST(reserved_cost - %(est_cost)s, 0)" in sql
    assert "used_calls" in sql
    assert "used_tokens" in sql
    assert "used_cost" in sql


def test_release_sql_clauses():
    sql = RELEASE_SQL
    assert "reserved_calls" in sql
    assert "reserved_tokens" in sql
    assert "reserved_cost" in sql
    assert "used_calls" not in sql
    assert "used_tokens" not in sql
    assert "used_cost" not in sql


def test_insert_llm_call_sql_clauses():
    sql = INSERT_LLM_CALL_SQL
    assert "INSERT INTO llm_calls" in sql
    assert "ON CONFLICT (call_id) DO NOTHING" in sql
    assert "gen_random_uuid()" in sql
    assert "'other'" in sql
    assert "'litellm-callback'" in sql


def test_insert_llm_call_fallback_sql_clauses():
    sql = INSERT_LLM_CALL_FALLBACK_SQL
    assert "INSERT INTO llm_calls" in sql
    assert "WHERE NOT EXISTS (SELECT 1 FROM llm_calls WHERE call_id" in sql
    assert "ON CONFLICT" not in sql


# ============================================================================
# _AsyncPool
# ============================================================================


@pytest.mark.asyncio
async def test_pool_acquire_returns_idle_connection():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    fake_conn = MagicMock(spec=psycopg.AsyncConnection)
    fake_conn.closed = False
    fake_conn.broken = False
    pool._idle.put_nowait(fake_conn)
    result = await pool.acquire()
    assert result is fake_conn


@pytest.mark.asyncio
async def test_pool_acquire_creates_new_connection_under_max():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    with patch.object(pool, "_dsn", "host=localhost dbname=test"):
        with patch("psycopg.AsyncConnection.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = MagicMock(spec=psycopg.AsyncConnection)
            result = await pool.acquire()
            assert mock_connect.called
            assert pool._created == 1
            assert result is mock_connect.return_value


@pytest.mark.asyncio
async def test_pool_acquire_waits_when_pool_full():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=1)
    pool._created = 1  # simulate at max

    # Put a connection into the idle queue after a short delay to unblock
    async def delayed_put():
        await asyncio.sleep(0.05)
        fake = MagicMock(spec=psycopg.AsyncConnection)
        fake.closed = False
        fake.broken = False
        pool._idle.put_nowait(fake)

    asyncio.create_task(delayed_put())
    result = await pool.acquire()
    assert result is not None


@pytest.mark.asyncio
async def test_pool_release_returns_healthy_connection():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    conn = MagicMock(spec=psycopg.AsyncConnection)
    conn.closed = False
    conn.broken = False
    await pool.release(conn)
    assert pool._idle.qsize() == 1


@pytest.mark.asyncio
async def test_pool_release_discards_closed_connection():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    pool._created = 3
    conn = MagicMock(spec=psycopg.AsyncConnection)
    conn.closed = True
    conn.broken = False
    await pool.release(conn)
    assert pool._created == 2
    conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_pool_release_discards_broken_connection():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    pool._created = 2
    conn = MagicMock(spec=psycopg.AsyncConnection)
    conn.closed = False
    conn.broken = True
    await pool.release(conn)
    assert pool._created == 1
    conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_pool_acquire_handles_connection_failure():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    with patch("psycopg.AsyncConnection.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = psycopg.OperationalError("connection refused")
        with pytest.raises(psycopg.OperationalError):
            await pool.acquire()
        # _created should be decremented back
        assert pool._created == 0


@pytest.mark.asyncio
async def test_pool_concurrent_acquires_respect_max_size():
    pool = _AsyncPool(dsn="host=localhost dbname=test", max_size=2)
    pool._created = 0

    fake_conn = MagicMock(spec=psycopg.AsyncConnection)
    fake_conn.closed = False
    fake_conn.broken = False

    connect_count = 0

    async def mock_connect(dsn):
        nonlocal connect_count
        connect_count += 1
        await asyncio.sleep(0.02)
        return MagicMock(spec=psycopg.AsyncConnection)

    with patch("psycopg.AsyncConnection.connect", new=mock_connect):
        results = await asyncio.gather(
            pool.acquire(),
            pool.acquire(),
        )
    assert len(results) == 2
    assert connect_count == 2
    assert pool._created == 2


# ============================================================================
# _get_pool
# ============================================================================


@pytest.mark.asyncio
async def test_get_pool_creates_pool_lazily():
    # Reset the global pool
    import budget_callback

    budget_callback._pool = None
    with patch.dict("os.environ", {"BUDGETLOOP_DATABASE_URL": "postgres://localhost/test"}):
        pool = await _get_pool()
        assert isinstance(pool, _AsyncPool)
        assert budget_callback._pool is pool
    budget_callback._pool = None  # clean up


@pytest.mark.asyncio
async def test_get_pool_reuses_existing_pool():
    import budget_callback

    budget_callback._pool = None
    with patch.dict("os.environ", {"BUDGETLOOP_DATABASE_URL": "postgres://localhost/test"}):
        p1 = await _get_pool()
        p2 = await _get_pool()
        assert p1 is p2
    budget_callback._pool = None


@pytest.mark.asyncio
async def test_get_pool_raises_without_env_var():
    import budget_callback

    budget_callback._pool = None
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="BUDGETLOOP_DATABASE_URL not set"):
            await _get_pool()
    budget_callback._pool = None


# ============================================================================
# BudgetLoopBudgetHandler.async_pre_call_hook
# ============================================================================


@pytest.mark.asyncio
async def test_pre_call_no_task_run_id_allows_call():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {}}
    result = await handler.async_pre_call_hook({}, {}, data, "completion")
    assert result is data


@pytest.mark.asyncio
async def test_pre_call_successful_reserve():
    handler = BudgetLoopBudgetHandler()
    data = {
        "metadata": {
            "task_run_id": "run-uuid",
            "est_tokens": 500,
            "est_cost": 0.01,
        }
    }
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = [(1,)]
        result = await handler.async_pre_call_hook({}, {}, data, "completion")
        assert result is data
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert call_args[0] == RESERVE_SQL
        assert call_args[1] == {"run_id": "run-uuid", "est_tokens": 500, "est_cost": 0.01}


@pytest.mark.asyncio
async def test_pre_call_budget_exhausted():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {"task_run_id": "run-uuid"}}
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = []
        with pytest.raises(BudgetExceededError, match="budget exhausted or deadline passed"):
            await handler.async_pre_call_hook({}, {}, data, "completion")


@pytest.mark.asyncio
async def test_pre_call_db_error_fail_closed():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {"task_run_id": "run-uuid"}}
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = psycopg.OperationalError("DB down")
        with pytest.raises(BudgetExceededError, match="budget ledger unavailable"):
            await handler.async_pre_call_hook({}, {}, data, "completion")


@pytest.mark.asyncio
async def test_pre_call_default_estimates():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {"task_run_id": "run-uuid"}}
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = [(1,)]
        await handler.async_pre_call_hook({}, {}, data, "completion")
        call_args = mock_exec.call_args[0]
        assert call_args[1]["est_tokens"] == DEFAULT_EST_TOKENS
        assert call_args[1]["est_cost"] == DEFAULT_EST_COST


# ============================================================================
# BudgetLoopBudgetHandler.async_post_call_success_hook
# ============================================================================


@pytest.mark.asyncio
async def test_post_call_success_no_task_run_id():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {}}
    response = object()
    result = await handler.async_post_call_success_hook(data, {}, response)
    assert result is response


@pytest.mark.asyncio
async def test_post_call_success_settles_budget():
    handler = BudgetLoopBudgetHandler()
    run_id = str(uuid.uuid4())
    call_id = str(uuid.uuid4())
    data = {
        "metadata": {"task_run_id": run_id, "est_tokens": 300, "est_cost": 0.02},
        "litellm_call_id": call_id,
    }
    response = MagicMock()
    response.id = "resp-id"
    response.model = "gpt-4"
    response.usage = MagicMock()
    response.usage.total_tokens = 400
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 300
    type(response.usage).prompt_tokens_details = MagicMock()
    type(response.usage).completion_tokens_details = MagicMock()
    response.usage.prompt_tokens_details.cached_tokens = None
    response.usage.completion_tokens_details.reasoning_tokens = None
    response.usage.cache_creation_input_tokens = None

    # _hidden_params with cost
    response._hidden_params = {
        "response_cost": 0.04,
        "custom_llm_provider": "openai",
    }
    # choices for finish_reason
    choice = MagicMock()
    choice.finish_reason = "stop"
    response.choices = [choice]

    with (
        patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec,
        patch("budget_callback._insert_llm_call", new_callable=AsyncMock) as mock_insert,
    ):
        mock_exec.return_value = []
        result = await handler.async_post_call_success_hook(data, {}, response)
        assert result is response
        # SETTLE_SQL called with correct params
        settle_call = mock_exec.call_args_list[0]
        assert settle_call[0][0] == SETTLE_SQL
        assert settle_call[0][1]["run_id"] == run_id
        assert settle_call[0][1]["actual_tokens"] == 400
        assert settle_call[0][1]["actual_cost"] == 0.04
        # _insert_llm_call also called
        mock_insert.assert_called_once()


@pytest.mark.asyncio
async def test_post_call_success_uses_response_cost():
    handler = BudgetLoopBudgetHandler()
    data = {
        "metadata": {"task_run_id": str(uuid.uuid4()), "est_tokens": 100, "est_cost": 0.01},
        "litellm_call_id": str(uuid.uuid4()),
    }
    response = MagicMock()
    response.usage = MagicMock()
    response.usage.total_tokens = 200
    response.usage.prompt_tokens = 50
    response.usage.completion_tokens = 150
    type(response.usage).prompt_tokens_details = MagicMock()
    type(response.usage).completion_tokens_details = MagicMock()
    response._hidden_params = {"response_cost": 0.03}
    response.choices = [MagicMock(finish_reason="stop")]

    with (
        patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec,
        patch("budget_callback._insert_llm_call", new_callable=AsyncMock),
    ):
        mock_exec.return_value = []
        await handler.async_post_call_success_hook(data, {}, response)
        settle_call = mock_exec.call_args_list[0]
        assert settle_call[0][1]["actual_cost"] == 0.03


@pytest.mark.asyncio
async def test_post_call_success_exception_non_blocking():
    handler = BudgetLoopBudgetHandler()
    data = {
        "metadata": {"task_run_id": str(uuid.uuid4())},
        "litellm_call_id": str(uuid.uuid4()),
    }
    response = object()
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = RuntimeError("DB crash")
        result = await handler.async_post_call_success_hook(data, {}, response)
        # should still return the response despite the exception
        assert result is response


# ============================================================================
# BudgetLoopBudgetHandler.async_post_call_failure_hook
# ============================================================================


@pytest.mark.asyncio
async def test_post_call_failure_no_task_run_id():
    handler = BudgetLoopBudgetHandler()
    result = await handler.async_post_call_failure_hook(
        {"metadata": {}}, Exception("boom"), {}
    )
    assert result is None


@pytest.mark.asyncio
async def test_post_call_failure_releases_budget():
    handler = BudgetLoopBudgetHandler()
    run_id = str(uuid.uuid4())
    call_id = str(uuid.uuid4())
    data = {
        "metadata": {"task_run_id": run_id, "est_tokens": 200, "est_cost": 0.01},
        "litellm_call_id": call_id,
        "model": "gpt-4o",
    }
    with (
        patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec,
        patch("budget_callback._insert_llm_call", new_callable=AsyncMock) as mock_insert,
    ):
        mock_exec.return_value = []
        result = await handler.async_post_call_failure_hook(
            data, Exception("api error"), {}
        )
        assert result is None
        # RELEASE_SQL called
        release_call = mock_exec.call_args_list[0]
        assert release_call[0][0] == RELEASE_SQL
        assert release_call[0][1]["run_id"] == run_id
        assert release_call[0][1]["est_tokens"] == 200
        # _insert_llm_call called with request_status='failed'
        insert_call_args = mock_insert.call_args[0][0]
        assert insert_call_args["request_status"] == "failed"
        assert insert_call_args["call_id"] == call_id


@pytest.mark.asyncio
async def test_post_call_failure_exception_non_blocking():
    handler = BudgetLoopBudgetHandler()
    data = {"metadata": {"task_run_id": str(uuid.uuid4())}}
    with patch("budget_callback._execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = RuntimeError("DB down")
        result = await handler.async_post_call_failure_hook(
            data, Exception("api error"), {}
        )
        assert result is None


# ============================================================================
# proxy_handler_instance
# ============================================================================


def test_proxy_handler_instance():
    assert isinstance(proxy_handler_instance, BudgetLoopBudgetHandler)


# ============================================================================
# _insert_llm_call fallback
# ============================================================================


@pytest.mark.asyncio
async def test_insert_llm_call_fallback_on_invalid_column_reference():
    """When call_id has no unique constraint, fallback SQL is used."""
    from budget_callback import _insert_llm_call

    call_count = [0]

    async def fake_execute(sql, params):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: the primary INSERT_LLM_CALL_SQL fails
            raise psycopg.errors.InvalidColumnReference("column does not exist")
        return []

    with patch("budget_callback._execute", new=fake_execute):
        await _insert_llm_call({"call_id": "test-cid", "run_id": "test-rid"})

    assert call_count[0] == 2  # first failed, then fallback succeeded
