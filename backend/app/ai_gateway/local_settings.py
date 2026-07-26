"""Authenticated local gateway personalization with OS-backed secret storage."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai_gateway.config import safe_http_url

KEYCHAIN_SERVICE = "BudgetLoop AI Gateway API Key"


def settings_path() -> Path:
    override = os.environ.get("BUDGETLOOP_LOCAL_AI_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "BudgetLoop"
        / "ai-gateway.json"
    )


class LocalGatewaySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["new-api", "litellm", "compatible"] = "compatible"
    base_url: str = ""
    console_url: str = ""
    recommendation_model: str = ""
    default_model: str = ""
    deployment_label: str = ""
    network_label: str = ""
    reasoning_effort: str = ""
    thinking_enabled: bool = False
    thinking_budget_tokens: int = Field(default=0, ge=0, le=65_536)
    managed_app_inheritance_enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if value and safe_http_url(value, strip_v1=True) is None:
            raise ValueError("gateway URL must be a safe HTTP(S) URL")
        return value.strip()

    @field_validator("console_url")
    @classmethod
    def validate_console_url(cls, value: str) -> str:
        if value and safe_http_url(value) is None:
            raise ValueError("console URL must be a safe HTTP(S) URL")
        return value.strip()

    @field_validator(
        "recommendation_model",
        "default_model",
        "deployment_label",
        "network_label",
        "reasoning_effort",
    )
    @classmethod
    def validate_bounded_text(cls, value: str) -> str:
        selected = value.strip()
        if len(selected) > 120 or any(ord(char) < 32 for char in selected):
            raise ValueError("setting contains unsupported characters")
        return selected

    @field_validator("reasoning_effort")
    @classmethod
    def validate_effort(cls, value: str) -> str:
        selected = value.strip().lower()
        if selected not in {"", "low", "medium", "high", "max"}:
            raise ValueError("reasoning effort must be low, medium, high or max")
        return selected


def load_local_settings() -> LocalGatewaySettings | None:
    path = settings_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LocalGatewaySettings.model_validate(data)
    except (OSError, ValueError, TypeError):
        return None


def save_local_settings(value: LocalGatewaySettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".ai-gateway-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value.model_dump(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        with suppress(OSError):
            os.unlink(temporary)
        raise


def _security_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["security", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def keychain_supported() -> bool:
    return platform.system() == "Darwin"


def read_keychain_secret() -> str:
    if not keychain_supported():
        return ""
    result = _security_command(
        "find-generic-password",
        "-a",
        os.environ.get("USER", "budgetloop"),
        "-s",
        KEYCHAIN_SERVICE,
        "-w",
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def write_keychain_secret(secret: str) -> None:
    selected = secret.strip()
    if not selected:
        raise ValueError("API key cannot be blank")
    if len(selected) > 8_192 or any(char in "\r\n\0" for char in selected):
        raise ValueError("API key is invalid")
    if not keychain_supported():
        raise RuntimeError("OS secret storage is unavailable")
    result = _security_command(
        "add-generic-password",
        "-U",
        "-a",
        os.environ.get("USER", "budgetloop"),
        "-s",
        KEYCHAIN_SERVICE,
        "-w",
        selected,
    )
    if result.returncode != 0:
        raise RuntimeError("OS secret storage rejected the update")


def public_local_settings(
    *,
    environment_secret_configured: bool = False,
    fallback: LocalGatewaySettings | None = None,
) -> dict:
    """Return settings safe for the browser, preferring persisted local choices.

    A Docker-launched control plane intentionally has no access to the Mac's
    Application Support directory. In that deployment the launcher injects
    non-secret configuration through the process environment; ``fallback``
    lets the settings page present those effective values without ever
    returning the corresponding API key.
    """
    current = load_local_settings() or fallback or LocalGatewaySettings()
    return {
        **current.model_dump(),
        "secret_configured": bool(read_keychain_secret()) or environment_secret_configured,
        "secret_store": "macos_keychain" if keychain_supported() else "environment",
    }
