"""Cached redacted AI gateway health facts."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from app.ai_gateway.client import GatewayClient, GatewayError
from app.ai_gateway.config import GatewayConfig, resolve_gateway_config

_lock = threading.Lock()
_cache_key: tuple | None = None
_cache_until = 0.0
_cache_value: dict | None = None


def reset_gateway_status_cache() -> None:
    global _cache_key, _cache_until, _cache_value
    with _lock:
        _cache_key = None
        _cache_until = 0.0
        _cache_value = None


def _key(config: GatewayConfig) -> tuple:
    return (
        config.kind,
        config.base_url,
        bool(config.api_key),
        config.recommendation_model,
        config.default_model,
        config.deployment_label,
        config.network_label,
        config.reasoning_effort,
        config.thinking_enabled,
        config.thinking_budget_tokens,
        config.managed_app_inheritance_enabled,
        config.recommendation_enabled,
        config.configuration_reason,
    )


def gateway_status(
    *,
    config: GatewayConfig | None = None,
    client_factory: Callable[[GatewayConfig], GatewayClient] = GatewayClient,
    force: bool = False,
) -> dict:
    global _cache_key, _cache_until, _cache_value
    config = config or resolve_gateway_config()
    now = time.monotonic()
    key = _key(config)
    with _lock:
        if not force and _cache_key == key and _cache_value is not None and now < _cache_until:
            return dict(_cache_value)

    public = config.public_configuration()
    if not config.configured:
        result = {
            **public,
            "healthy": False,
            "reason_code": config.configuration_reason,
            "status_class": None,
        }
    elif not config.recommendation_enabled:
        result = {
            **public,
            "healthy": False,
            "reason_code": "ai_disabled",
            "status_class": None,
        }
    else:
        try:
            status_class = client_factory(config).preflight()
            result = {
                **public,
                "healthy": True,
                "reason_code": None,
                "status_class": status_class,
            }
        except GatewayError as exc:
            result = {
                **public,
                "healthy": False,
                "reason_code": exc.code,
                "status_class": exc.status_class,
            }

    with _lock:
        _cache_key = key
        _cache_until = now + config.status_ttl_seconds
        _cache_value = dict(result)
    return result
