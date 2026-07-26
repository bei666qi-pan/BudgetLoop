"""HMAC-signed, short-lived capabilities that never contain the upstream key."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.ai_gateway import GatewayConfig, resolve_gateway_config
from app.ai_gateway.local_settings import load_local_settings
from app.core.config import Settings, settings

TOKEN_PREFIX = "blrt1"
RUNTIME_AUDIENCE = "managed-ai-app"


class RuntimeCapabilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RuntimeClaims:
    run_id: uuid.UUID
    model: str
    audience: str
    expires_at: int


def managed_runtime_enabled(source: Settings | None = None) -> bool:
    source = source or settings
    if source is settings:
        local = load_local_settings()
        if local is not None:
            return local.managed_app_inheritance_enabled
    return source.managed_ai_runtime_enabled


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_key(config: GatewayConfig, source: Settings) -> bytes:
    if not config.api_key or not source.api_token:
        raise RuntimeCapabilityError("runtime_unconfigured")
    return hmac.new(
        source.api_token.encode("utf-8"),
        config.api_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def issue_runtime_capability(
    run_id: uuid.UUID | str,
    *,
    model: str | None = None,
    now: int | None = None,
    config: GatewayConfig | None = None,
    source: Settings | None = None,
) -> str:
    source = source or settings
    if not managed_runtime_enabled(source):
        raise RuntimeCapabilityError("runtime_disabled")
    config = config or resolve_gateway_config(source if source is not settings else None)
    if not config.configured:
        raise RuntimeCapabilityError("runtime_unconfigured")
    selected_model = (model or config.default_model or config.recommendation_model).strip()
    if not selected_model:
        raise RuntimeCapabilityError("runtime_model_missing")
    issued_at = int(time.time() if now is None else now)
    try:
        normalized_run_id = str(uuid.UUID(str(run_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeCapabilityError("invalid_runtime_run_id") from exc
    payload = {
        "aud": RUNTIME_AUDIENCE,
        "exp": issued_at + source.managed_ai_runtime_token_ttl_seconds,
        "model": selected_model,
        "run_id": normalized_run_id,
        "v": 1,
    }
    encoded = _b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _b64encode(
        hmac.new(_signing_key(config, source), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{TOKEN_PREFIX}.{encoded}.{signature}"


def validate_runtime_capability(
    token: str,
    *,
    now: int | None = None,
    config: GatewayConfig | None = None,
    source: Settings | None = None,
) -> RuntimeClaims:
    source = source or settings
    if not managed_runtime_enabled(source):
        raise RuntimeCapabilityError("runtime_disabled")
    config = config or resolve_gateway_config(source if source is not settings else None)
    try:
        prefix, encoded, supplied_signature = token.split(".", 2)
        if prefix != TOKEN_PREFIX:
            raise ValueError
        expected_signature = _b64encode(
            hmac.new(
                _signing_key(config, source),
                encoded.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError
        payload: Any = json.loads(_b64decode(encoded))
        if not isinstance(payload, dict) or set(payload) != {
            "aud",
            "exp",
            "model",
            "run_id",
            "v",
        }:
            raise ValueError
        claims = RuntimeClaims(
            run_id=uuid.UUID(str(payload["run_id"])),
            model=str(payload["model"]),
            audience=str(payload["aud"]),
            expires_at=int(payload["exp"]),
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeCapabilityError("invalid_runtime_capability") from exc
    current = int(time.time() if now is None else now)
    if claims.audience != RUNTIME_AUDIENCE:
        raise RuntimeCapabilityError("invalid_runtime_audience")
    if claims.expires_at <= current:
        raise RuntimeCapabilityError("runtime_capability_expired")
    if not claims.model or len(claims.model) > 120:
        raise RuntimeCapabilityError("invalid_runtime_model")
    return claims


def managed_runtime_environment(
    run_id: uuid.UUID | str,
    *,
    container: bool = False,
    config: GatewayConfig | None = None,
    source: Settings | None = None,
) -> dict[str, str]:
    source = source or settings
    if not managed_runtime_enabled(source):
        return {}
    config = config or resolve_gateway_config(source if source is not settings else None)
    try:
        token = issue_runtime_capability(
            run_id,
            config=config,
            source=source,
        )
    except RuntimeCapabilityError:
        return {}
    base_url = (
        source.managed_ai_runtime_container_base_url
        if container
        else source.managed_ai_runtime_base_url
    ).rstrip("/")
    gemini_base_url = base_url[:-3] if base_url.endswith("/v1") else base_url
    container_base_url = source.managed_ai_runtime_container_base_url.rstrip("/")
    container_gemini_base_url = (
        container_base_url[:-3]
        if container_base_url.endswith("/v1")
        else container_base_url
    )
    model = config.default_model or config.recommendation_model
    return {
        "OPENAI_BASE_URL": base_url,
        "OPENAI_API_KEY": token,
        "OPENAI_MODEL": model,
        "GOOGLE_GEMINI_BASE_URL": gemini_base_url,
        "GEMINI_API_KEY": token,
        "GEMINI_API_KEY_AUTH_MECHANISM": "bearer",
        "GEMINI_MODEL": model,
        # Gemini CLI relaunches inside a sibling Docker sandbox. Keep this
        # non-secret alternate origin process-only so that container can reach
        # the control plane without changing Codex's worker-local route.
        "BUDGETLOOP_AI_CONTAINER_GEMINI_BASE_URL": container_gemini_base_url,
        "BUDGETLOOP_AI_MANAGED": "1",
    }
