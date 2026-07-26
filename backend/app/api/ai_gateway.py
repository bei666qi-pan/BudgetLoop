"""Redacted AI gateway status and authenticated local personalization API."""

from typing import Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.ai_gateway import gateway_status, resolve_gateway_config
from app.ai_gateway.local_settings import (
    LocalGatewaySettings,
    public_local_settings,
    save_local_settings,
    write_keychain_secret,
)
from app.ai_gateway.status import reset_gateway_status_cache
from app.core.config import settings

router = APIRouter(tags=["ai-gateway"])


def _public_gateway_settings() -> dict:
    config = resolve_gateway_config()
    kind = config.kind if config.kind in {"new-api", "litellm", "compatible"} else "compatible"
    fallback = LocalGatewaySettings(
        kind=cast(Literal["new-api", "litellm", "compatible"], kind),
        base_url=config.openai_base_url,
        console_url=config.console_url or "",
        recommendation_model=config.recommendation_model,
        default_model=config.default_model,
        deployment_label=config.deployment_label,
        network_label=config.network_label,
        reasoning_effort=config.reasoning_effort or "",
        thinking_enabled=config.thinking_enabled,
        thinking_budget_tokens=config.thinking_budget_tokens if config.thinking_enabled else 0,
        managed_app_inheritance_enabled=config.managed_app_inheritance_enabled,
    )
    return public_local_settings(
        environment_secret_configured=bool(settings.ai_gateway_api_key.strip()),
        fallback=fallback,
    )


@router.get("/ai-gateway/status")
def get_ai_gateway_status() -> dict:
    return gateway_status()


class LocalGatewaySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    base_url: str
    console_url: str = ""
    recommendation_model: str
    default_model: str
    deployment_label: str = ""
    network_label: str = ""
    reasoning_effort: str = ""
    thinking_enabled: bool = False
    thinking_budget_tokens: int = Field(default=0, ge=0, le=65_536)
    managed_app_inheritance_enabled: bool = True
    api_key: str | None = Field(default=None, max_length=8_192)


@router.get("/ai-gateway/settings")
def get_ai_gateway_settings() -> dict:
    return _public_gateway_settings()


@router.put("/ai-gateway/settings")
def update_ai_gateway_settings(payload: LocalGatewaySettingsUpdate) -> dict:
    try:
        selected = LocalGatewaySettings.model_validate(
            payload.model_dump(exclude={"api_key"})
        )
        if payload.api_key is not None and payload.api_key.strip():
            write_keychain_secret(payload.api_key)
        save_local_settings(selected)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    reset_gateway_status_cache()
    return _public_gateway_settings()
