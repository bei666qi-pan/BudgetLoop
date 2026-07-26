"""Typed AI gateway configuration resolved without exposing secrets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from app.core.config import Settings, settings

GatewayKind = Literal["new-api", "litellm", "compatible"]
VALID_GATEWAY_KINDS = frozenset({"new-api", "litellm", "compatible"})

NEW_API_PROVENANCE = {
    "name": "New API",
    "repository": "QuantumNous/new-api",
    "repository_url": "https://github.com/QuantumNous/new-api",
    "release": "v1.0.0-rc.21",
    "revision": "bde9b2f44887d34ec54799ae191d50f97914359e",
    "license": "AGPL-3.0",
    "reviewed_stars": 43_370,
    "reviewed_at": "2026-07-25",
}

_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "new-api": (
        "OpenAI Chat Completions",
        "OpenAI Responses",
        "Claude Messages",
        "Gemini native",
        "Custom authorized upstreams",
    ),
    "litellm": ("OpenAI-compatible", "Provider routing"),
    "compatible": ("OpenAI-compatible",),
}

_ROUTING: dict[str, str] = {
    "new-api": "New API 渠道优先级、权重、重试与限流",
    "litellm": "LiteLLM 路由（兼容模式）",
    "compatible": "由自定义兼容网关负责",
}


def safe_http_url(value: str, *, strip_v1: bool = False) -> str | None:
    """Return a normalized HTTP(S) URL with no credentials/query/fragment."""
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    path = parsed.path.rstrip("/")
    if strip_v1 and path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


@dataclass(frozen=True)
class GatewayConfig:
    kind: str
    base_url: str | None
    api_key: str
    console_url: str | None
    recommendation_model: str
    default_model: str
    deployment_label: str
    network_label: str
    reasoning_effort: str | None
    thinking_enabled: bool
    thinking_budget_tokens: int
    managed_app_inheritance_enabled: bool
    recommendation_enabled: bool
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_response_bytes: int
    status_ttl_seconds: float
    configuration_reason: str | None = None

    @property
    def configured(self) -> bool:
        return self.configuration_reason is None

    @property
    def openai_base_url(self) -> str:
        return f"{self.base_url}/v1" if self.base_url else ""

    @property
    def protocols(self) -> tuple[str, ...]:
        return _PROTOCOLS.get(self.kind, ())

    @property
    def routing(self) -> str:
        return _ROUTING.get(self.kind, "未配置")

    @property
    def provenance(self) -> dict | None:
        return dict(NEW_API_PROVENANCE) if self.kind == "new-api" else None

    def public_configuration(self) -> dict:
        return {
            "type": self.kind,
            "configured": self.configured,
            "recommendation_enabled": self.recommendation_enabled,
            "recommendation_model": self.recommendation_model or None,
            "default_model": self.default_model or None,
            "deployment_label": self.deployment_label or None,
            "network_label": self.network_label or None,
            "reasoning_effort": self.reasoning_effort,
            "thinking_enabled": self.thinking_enabled,
            "thinking_budget_tokens": (
                self.thinking_budget_tokens if self.thinking_enabled else None
            ),
            "managed_app_runtime": {
                "enabled": self.managed_app_inheritance_enabled,
                "credential_source": "budgetloop_scoped_runtime",
                "project_env_required": False,
                "browser_direct_access": False,
            },
            "console_url": self.console_url if self.kind == "new-api" else None,
            "protocols": list(self.protocols),
            "routing": self.routing,
            "semantic_ai_router": False,
            "provenance": self.provenance,
        }


def resolve_gateway_config(source: Settings | None = None) -> GatewayConfig:
    use_local = source is None
    source = source or settings
    local = None
    local_secret = ""
    if use_local:
        from app.ai_gateway.local_settings import load_local_settings, read_keychain_secret

        local = load_local_settings()
        if local is not None:
            local_secret = read_keychain_secret()

    def selected(local_value: str, environment_value: str) -> str:
        return local_value if local is not None and local_value else environment_value

    explicit_kind = selected(local.kind if local else "", source.ai_gateway_type).strip().lower()
    if explicit_kind:
        kind = explicit_kind
    elif selected(local.base_url if local else "", source.ai_gateway_base_url).strip() or (
        local_secret or source.ai_gateway_api_key.strip()
    ):
        kind = "new-api"
    elif source.litellm_master_key.strip():
        kind = "litellm"
    else:
        kind = "new-api"

    if kind == "litellm":
        base_value = (
            selected(local.base_url if local else "", source.ai_gateway_base_url)
            or source.litellm_base_url
        )
        api_key = local_secret or source.ai_gateway_api_key or source.litellm_master_key
    else:
        base_value = selected(local.base_url if local else "", source.ai_gateway_base_url)
        api_key = local_secret or source.ai_gateway_api_key

    base_url = safe_http_url(base_value, strip_v1=True)
    console_url = safe_http_url(
        selected(local.console_url if local else "", source.ai_gateway_console_url)
    )
    model = selected(
        local.recommendation_model if local else "",
        source.ai_gateway_recommendation_model,
    ).strip()
    default_model = (
        selected(local.default_model if local else "", source.ai_gateway_default_model).strip()
        or model
    )
    deployment_label = selected(
        local.deployment_label if local else "", source.ai_gateway_deployment_label
    ).strip()
    network_label = selected(local.network_label if local else "", source.ai_gateway_network_label).strip()
    reasoning_effort = (
        selected(
            local.reasoning_effort if local else "",
            source.ai_gateway_reasoning_effort,
        ).strip().lower()
        or None
    )
    thinking_enabled = local.thinking_enabled if local is not None else source.ai_gateway_thinking_enabled
    thinking_budget_tokens = (
        local.thinking_budget_tokens
        if local is not None
        else source.ai_gateway_thinking_budget_tokens
    )
    managed_app_inheritance_enabled = (
        local.managed_app_inheritance_enabled
        if local is not None
        else source.managed_ai_runtime_enabled
    )
    reason: str | None = None
    if kind not in VALID_GATEWAY_KINDS:
        reason = "invalid_gateway_type"
    elif base_url is None:
        reason = "invalid_or_missing_gateway_url"
    elif not api_key.strip():
        reason = "missing_gateway_key"
    elif source.ai_recommendation_enabled and not model:
        reason = "missing_recommendation_model"

    return GatewayConfig(
        kind=kind,
        base_url=base_url,
        api_key=api_key.strip(),
        console_url=console_url,
        recommendation_model=model,
        default_model=default_model,
        deployment_label=deployment_label,
        network_label=network_label,
        reasoning_effort=reasoning_effort,
        thinking_enabled=thinking_enabled,
        thinking_budget_tokens=thinking_budget_tokens,
        managed_app_inheritance_enabled=managed_app_inheritance_enabled,
        recommendation_enabled=source.ai_recommendation_enabled,
        connect_timeout_seconds=source.ai_gateway_connect_timeout_seconds,
        read_timeout_seconds=source.ai_gateway_read_timeout_seconds,
        max_response_bytes=source.ai_gateway_max_response_bytes,
        status_ttl_seconds=source.ai_gateway_status_ttl_seconds,
        configuration_reason=reason,
    )
