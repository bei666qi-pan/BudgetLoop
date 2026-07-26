"""Capability-scoped AI proxy for generated applications and CLI engines."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai_gateway import GatewayClient, GatewayError, resolve_gateway_config
from app.ai_gateway.config import GatewayConfig
from app.ai_runtime import RuntimeCapabilityError, validate_runtime_capability
from app.budget.manager import BudgetRejected, TaskBudgetManager
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RunStatus
from app.core.models import TaskRun

logger = logging.getLogger(__name__)
router = APIRouter(tags=["managed-ai-runtime"])
_bearer = HTTPBearer(auto_error=False)
RuntimeCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
DatabaseSession = Annotated[Session, Depends(get_db)]
_SAFE_RESPONSE_HEADERS = frozenset({"content-type", "cache-control"})
_USAGE_BUFFER_LIMIT = 64 * 1024


@dataclass(frozen=True)
class RuntimeRequestContext:
    run_id: Any
    model: str
    raw: bytes
    payload: dict[str, Any]
    budget: TaskBudgetManager


def _public_gateway_error(error: GatewayError) -> HTTPException:
    status = 504 if error.code == "timeout" else 502
    if error.code == "rate_limited":
        status = 429
    return HTTPException(status_code=status, detail=error.code)


def _public_upstream_status(status: int) -> HTTPException:
    if status in {401, 403}:
        return HTTPException(status_code=502, detail="authentication_failed")
    if status == 429:
        return HTTPException(status_code=429, detail="rate_limited")
    if status >= 500:
        return HTTPException(status_code=502, detail="upstream_unavailable")
    return HTTPException(status_code=502, detail="gateway_rejected_request")


def _validate_credentials(credentials: RuntimeCredentials) -> Any:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid_runtime_capability")
    try:
        return validate_runtime_capability(credentials.credentials)
    except RuntimeCapabilityError as exc:
        raise HTTPException(status_code=401, detail=exc.code) from None


async def _prepare_runtime_request(
    request: Request,
    credentials: RuntimeCredentials,
    db: Session,
) -> RuntimeRequestContext:
    """Validate the common runtime boundary before protocol-specific checks."""
    claims = _validate_credentials(credentials)
    run = db.get(TaskRun, claims.run_id)
    if run is None:
        raise HTTPException(status_code=401, detail="runtime_run_unavailable")
    try:
        status = RunStatus(run.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="runtime_run_unavailable") from None
    if status.is_terminal:
        raise HTTPException(status_code=409, detail="runtime_run_unavailable")

    raw = await request.body()
    if len(raw) > settings.managed_ai_runtime_max_request_bytes:
        raise HTTPException(status_code=413, detail="runtime_request_too_large")
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="invalid_runtime_request") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="invalid_runtime_request")

    return RuntimeRequestContext(
        claims.run_id,
        claims.model,
        raw,
        payload,
        TaskBudgetManager(db, claims.run_id),
    )


def _reserve_runtime_budget(db: Session, budget: TaskBudgetManager) -> None:
    try:
        budget.reserve(
            settings.managed_ai_runtime_est_tokens,
            settings.managed_ai_runtime_est_cost,
        )
        db.commit()
    except BudgetRejected:
        db.rollback()
        raise HTTPException(status_code=429, detail="runtime_budget_rejected") from None


def _settle_runtime_budget(
    db: Session,
    budget: TaskBudgetManager,
    actual_tokens: int | None,
) -> None:
    budget.settle(
        settings.managed_ai_runtime_est_tokens,
        settings.managed_ai_runtime_est_cost,
        actual_tokens if actual_tokens is not None else settings.managed_ai_runtime_est_tokens,
        0.0,
    )
    db.commit()


def _release_runtime_budget(db: Session, budget: TaskBudgetManager) -> None:
    db.rollback()
    budget.release(
        settings.managed_ai_runtime_est_tokens,
        settings.managed_ai_runtime_est_cost,
    )
    db.commit()


def _usage_tokens(value: Any) -> int | None:
    """Extract only standard aggregate usage fields from a native response."""
    if not isinstance(value, dict):
        return None
    usage = value.get("usage")
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int) and total >= 0:
            return total
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            return max(0, input_tokens) + max(0, output_tokens)
    gemini_usage = value.get("usageMetadata")
    if isinstance(gemini_usage, dict):
        total = gemini_usage.get("totalTokenCount")
        if isinstance(total, int) and total >= 0:
            return total
    response = value.get("response")
    if isinstance(response, dict):
        nested = _usage_tokens(response)
        if nested is not None:
            return nested
    return None


def _apply_native_reasoning_policy(
    payload: dict[str, Any],
    *,
    protocol: str,
) -> dict[str, Any]:
    """Enforce the operator's reasoning profile without translating protocols."""
    config = resolve_gateway_config()
    selected = dict(payload)
    if protocol == "responses":
        if config.reasoning_effort:
            selected["reasoning_effort"] = config.reasoning_effort
        if config.thinking_enabled:
            selected["thinking"] = {
                "type": "enabled",
                "budget_tokens": config.thinking_budget_tokens,
            }
    elif protocol == "gemini" and config.thinking_enabled:
        generation = selected.get("generationConfig")
        generation = dict(generation) if isinstance(generation, dict) else {}
        generation["thinkingConfig"] = {
            "thinkingBudget": config.thinking_budget_tokens,
            "includeThoughts": True,
        }
        selected["generationConfig"] = generation
    return selected


class NativeUsageTracker:
    """Bounded SSE metadata observer; content is neither logged nor persisted."""

    def __init__(self) -> None:
        self._buffer = b""
        self.total_tokens: int | None = None

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._buffer = (self._buffer + chunk)[-_USAGE_BUFFER_LIMIT:]
        lines = self._buffer.splitlines(keepends=True)
        self._buffer = lines.pop() if lines and not lines[-1].endswith((b"\n", b"\r")) else b""
        for line in lines:
            selected = line.strip()
            if selected.startswith(b"data:"):
                selected = selected[5:].strip()
            if not selected or selected == b"[DONE]" or not selected.startswith(b"{"):
                continue
            try:
                tokens = _usage_tokens(json.loads(selected))
            except (ValueError, TypeError):
                continue
            if tokens is not None:
                self.total_tokens = tokens

    def finish(self) -> None:
        if not self._buffer:
            return
        pending = self._buffer
        self._buffer = b""
        self.feed(pending + b"\n")


def _native_headers(config: GatewayConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "BudgetLoop/managed-ai-runtime",
    }


def _native_timeout(config: GatewayConfig) -> httpx.Timeout:
    return httpx.Timeout(
        connect=config.connect_timeout_seconds,
        read=None,
        write=max(config.read_timeout_seconds, 30.0),
        pool=config.connect_timeout_seconds,
    )


def _native_http_client(config: GatewayConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_native_timeout(config),
        follow_redirects=False,
        headers=_native_headers(config),
    )


async def _forward_native(
    *,
    db: Session,
    context: RuntimeRequestContext,
    upstream_path: str,
    query: str = "",
    streaming: bool,
) -> Response:
    config = resolve_gateway_config()
    if not config.configured or not config.base_url:
        _release_runtime_budget(db, context.budget)
        raise HTTPException(status_code=502, detail=config.configuration_reason or "gateway_unconfigured")
    url = f"{config.base_url}{upstream_path}{query}"
    client = _native_http_client(config)
    try:
        upstream = await client.send(
            client.build_request("POST", url, content=context.raw),
            stream=streaming,
        )
    except httpx.TimeoutException:
        await client.aclose()
        _release_runtime_budget(db, context.budget)
        raise HTTPException(status_code=504, detail="timeout") from None
    except httpx.HTTPError:
        await client.aclose()
        _release_runtime_budget(db, context.budget)
        raise HTTPException(status_code=502, detail="gateway_unreachable") from None

    if not upstream.is_success:
        await upstream.aclose()
        await client.aclose()
        _release_runtime_budget(db, context.budget)
        raise _public_upstream_status(upstream.status_code)

    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() in _SAFE_RESPONSE_HEADERS
    }
    if not streaming:
        content = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        if len(content) > config.max_response_bytes:
            _release_runtime_budget(db, context.budget)
            raise HTTPException(status_code=502, detail="response_too_large")
        try:
            tokens = _usage_tokens(json.loads(content))
        except (ValueError, TypeError):
            tokens = None
        _settle_runtime_budget(db, context.budget, tokens)
        return Response(content=content, status_code=upstream.status_code, headers=response_headers)

    tracker = NativeUsageTracker()

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                tracker.feed(chunk)
                yield chunk
        finally:
            tracker.finish()
            await upstream.aclose()
            await client.aclose()
            try:
                _settle_runtime_budget(db, context.budget, tracker.total_tokens)
            except Exception:
                db.rollback()
                logger.exception(
                    "managed AI runtime stream budget settlement failed",
                    extra={"run_id": str(context.run_id), "model": context.model},
                )

    return StreamingResponse(body(), status_code=upstream.status_code, headers=response_headers)


@router.post("/runtime/ai/v1/chat/completions")
async def managed_chat_completions(
    request: Request,
    credentials: RuntimeCredentials,
    db: DatabaseSession,
) -> dict[str, Any]:
    started = time.monotonic()
    context = await _prepare_runtime_request(request, credentials, db)
    if not isinstance(context.payload.get("messages"), list):
        raise HTTPException(status_code=422, detail="invalid_runtime_request")
    if context.payload.get("stream"):
        raise HTTPException(status_code=422, detail="runtime_streaming_not_supported")
    requested_model = str(context.payload.get("model") or context.model)
    if requested_model != context.model:
        raise HTTPException(status_code=403, detail="runtime_model_not_allowed")
    context.payload["model"] = context.model
    _reserve_runtime_budget(db, context.budget)

    status_class: str | None = None
    try:
        response, status_class = GatewayClient(resolve_gateway_config()).chat_completion(
            context.payload
        )
        usage_value = response.get("usage")
        usage = usage_value if isinstance(usage_value, dict) else {}
        actual_tokens = int(usage.get("total_tokens") or 0)
        _settle_runtime_budget(db, context.budget, actual_tokens)
        return response
    except GatewayError as exc:
        _release_runtime_budget(db, context.budget)
        status_class = exc.status_class
        raise _public_gateway_error(exc) from None
    finally:
        logger.info(
            "managed AI runtime call completed",
            extra={
                "run_id": str(context.run_id),
                "model": context.model,
                "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
                "status_class": status_class,
            },
        )


@router.post("/runtime/ai/v1/responses")
async def managed_responses(
    request: Request,
    credentials: RuntimeCredentials,
    db: DatabaseSession,
) -> Response:
    context = await _prepare_runtime_request(request, credentials, db)
    requested_model = str(context.payload.get("model") or context.model)
    if requested_model != context.model:
        raise HTTPException(status_code=403, detail="runtime_model_not_allowed")
    context.payload["model"] = context.model
    context_payload = _apply_native_reasoning_policy(context.payload, protocol="responses")
    _reserve_runtime_budget(db, context.budget)
    context = RuntimeRequestContext(
        context.run_id,
        context.model,
        json.dumps(context_payload, separators=(",", ":")).encode(),
        context_payload,
        context.budget,
    )
    return await _forward_native(
        db=db,
        context=context,
        upstream_path="/v1/responses",
        streaming=bool(context.payload.get("stream")),
    )


async def _managed_gemini(
    model: str,
    action: str,
    request: Request,
    credentials: RuntimeCredentials,
    db: Session,
) -> Response:
    context = await _prepare_runtime_request(request, credentials, db)
    if model != context.model:
        raise HTTPException(status_code=403, detail="runtime_model_not_allowed")
    payload = _apply_native_reasoning_policy(context.payload, protocol="gemini")
    context = RuntimeRequestContext(
        context.run_id,
        context.model,
        json.dumps(payload, separators=(",", ":")).encode(),
        payload,
        context.budget,
    )
    _reserve_runtime_budget(db, context.budget)
    streaming = action == "streamGenerateContent"
    query = "?alt=sse" if streaming and request.query_params.get("alt") == "sse" else ""
    return await _forward_native(
        db=db,
        context=context,
        upstream_path=f"/v1beta/models/{model}:{action}",
        query=query,
        streaming=streaming,
    )


@router.post("/runtime/ai/v1beta/models/{model}:generateContent")
async def managed_gemini_content(
    model: str,
    request: Request,
    credentials: RuntimeCredentials,
    db: DatabaseSession,
) -> Response:
    return await _managed_gemini(model, "generateContent", request, credentials, db)


@router.post("/runtime/ai/v1beta/models/{model}:streamGenerateContent")
async def managed_gemini_stream(
    model: str,
    request: Request,
    credentials: RuntimeCredentials,
    db: DatabaseSession,
) -> Response:
    return await _managed_gemini(model, "streamGenerateContent", request, credentials, db)
