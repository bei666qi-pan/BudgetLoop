"""Typed, license-aware registry for downloaded execution engine sources."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings

MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ExecutionEngine:
    id: str
    name: str
    repository: str
    url: str
    revision: str
    reviewed_stars: int
    license: str
    license_scope: str
    source_path: str
    transport: str
    command: str | None
    distribution_package: str | None
    distribution_version: str | None
    required_env: tuple[str, ...]
    credential_hint: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class EnginePreflight:
    engine_id: str
    source_downloaded: bool
    runtime_available: bool
    reason: str
    binary_path: str | None = None


def _text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value.strip()


def _load_manifest(path: Path = MANIFEST_PATH) -> tuple[str, tuple[ExecutionEngine, ...]]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to load execution engine manifest: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("execution engine manifest schema_version must be 1")
    default_engine = _text(document.get("default_engine"), "default_engine")
    raw_engines = document.get("engines")
    if not isinstance(raw_engines, list) or not raw_engines:
        raise ValueError("engines must be a non-empty list")
    engines: list[ExecutionEngine] = []
    for index, raw in enumerate(raw_engines):
        location = f"engines[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{location} must be a mapping")
        required_env = raw.get("required_env", [])
        capabilities = raw.get("capabilities", [])
        if not isinstance(required_env, list) or not isinstance(capabilities, list):
            raise ValueError(f"{location} env and capabilities must be lists")
        command = raw.get("command")
        if command is not None and not isinstance(command, str):
            raise ValueError(f"{location}.command must be a string or null")
        distribution_package = raw.get("distribution_package")
        distribution_version = raw.get("distribution_version")
        if distribution_package is not None and not isinstance(distribution_package, str):
            raise ValueError(f"{location}.distribution_package must be a string or null")
        if distribution_version is not None and not isinstance(distribution_version, str):
            raise ValueError(f"{location}.distribution_version must be a string or null")
        stars = raw.get("reviewed_stars")
        if isinstance(stars, bool) or not isinstance(stars, int) or stars < 10_000:
            raise ValueError(f"{location}.reviewed_stars must be at least 10000")
        engine = ExecutionEngine(
            id=_text(raw.get("id"), f"{location}.id"),
            name=_text(raw.get("name"), f"{location}.name"),
            repository=_text(raw.get("repository"), f"{location}.repository"),
            url=_text(raw.get("url"), f"{location}.url"),
            revision=_text(raw.get("revision"), f"{location}.revision"),
            reviewed_stars=stars,
            license=_text(raw.get("license"), f"{location}.license"),
            license_scope=_text(raw.get("license_scope"), f"{location}.license_scope"),
            source_path=_text(raw.get("source_path"), f"{location}.source_path"),
            transport=_text(raw.get("transport"), f"{location}.transport"),
            command=command,
            distribution_package=distribution_package,
            distribution_version=distribution_version,
            required_env=tuple(_text(item, f"{location}.required_env") for item in required_env),
            credential_hint=_text(raw.get("credential_hint"), f"{location}.credential_hint"),
            capabilities=tuple(_text(item, f"{location}.capabilities") for item in capabilities),
        )
        if engine.transport not in {"server", "cli"}:
            raise ValueError(f"{location}.transport must be server or cli")
        if (
            engine.transport == "cli"
            and engine.id in {"codex", "gemini-cli"}
            and (not engine.distribution_package or not engine.distribution_version)
        ):
            raise ValueError(f"{location} must pin its official CLI distribution")
        engines.append(engine)
    ids = [engine.id for engine in engines]
    if len(ids) != len(set(ids)):
        raise ValueError("execution engine ids must be unique")
    if default_engine not in ids:
        raise ValueError("default_engine must reference a registered engine")
    return default_engine, tuple(engines)


DEFAULT_ENGINE_ID, ENGINES = _load_manifest()
_BY_ID = {engine.id: engine for engine in ENGINES}


def get_engine(engine_id: str) -> ExecutionEngine | None:
    return _BY_ID.get(engine_id)


def engine_preflight(engine_id: str) -> EnginePreflight:
    engine = get_engine(engine_id)
    if engine is None:
        return EnginePreflight(engine_id, False, False, "unknown execution engine")
    source_downloaded = (PROJECT_ROOT / engine.source_path).is_dir()
    if engine.transport == "server":
        configured = bool(settings.agent_server_image.strip())
        return EnginePreflight(
            engine.id,
            source_downloaded,
            configured,
            "OpenHands Agent Server 镜像已配置" if configured else "尚未配置 OpenHands Agent Server 镜像",
        )
    binary_path = shutil.which(engine.command or "")
    missing_env = [name for name in engine.required_env if not os.environ.get(name)]
    managed_credential_ready = _managed_credentials_configured(engine.id)
    credential_ready = managed_credential_ready or _engine_credentials_configured(engine.id)
    sandbox_ready = _engine_sandbox_configured(engine.id)
    available = bool(
        settings.enable_cli_engines and binary_path and not missing_env and credential_ready and sandbox_ready
    )
    if not settings.enable_cli_engines:
        reason = "源码已准备好，但 Worker 尚未启用 CLI 引擎。启用后还会检查命令和独立凭据。"
    elif not binary_path:
        reason = f"Worker 中尚未安装 {engine.command} 命令"
    elif missing_env:
        reason = f"缺少此引擎专用的环境变量：{', '.join(missing_env)}"
    elif not credential_ready:
        key = engine.id.upper().replace("-", "_")
        reason = (
            "BudgetLoop AI 继承尚未就绪，且未配置引擎独立凭据；"
            f"请启用 AI 继承或设置 BUDGETLOOP_{key}_HOME / BUDGETLOOP_{key}_ENV_<变量名>"
        )
    elif not sandbox_ready:
        if engine.id == "gemini-cli":
            reason = (
                "Gemini CLI sandbox 尚未确认；请配置 BUDGETLOOP_GEMINI_CLI_SANDBOX_COMMAND，"
                "或在验证官方 sandbox 后设置 BUDGETLOOP_GEMINI_CLI_SANDBOX_READY=true"
            )
        else:
            reason = (
                "OpenCode 没有内置进程沙箱；请配置 BUDGETLOOP_OPENCODE_SANDBOX_COMMAND，"
                "或显式设置 BUDGETLOOP_OPENCODE_ALLOW_HOST_EXECUTION=true"
            )
    else:
        credential_source = "BudgetLoop 受管 AI" if managed_credential_ready else "引擎独立凭据"
        reason = f"命令、{credential_source}、沙箱与 Worker 生命周期适配均已就绪"
    return EnginePreflight(engine.id, source_downloaded, available, reason, binary_path)


def _engine_credentials_configured(engine_id: str) -> bool:
    key = engine_id.upper().replace("-", "_")
    prefix = f"BUDGETLOOP_{key}_ENV_"
    if any(name.startswith(prefix) and value for name, value in os.environ.items()):
        return True
    configured_home = os.environ.get(f"BUDGETLOOP_{key}_HOME")
    if not configured_home:
        return False
    home = Path(configured_home).expanduser()
    return home.is_dir() and any(home.iterdir())


def _managed_credentials_configured(engine_id: str) -> bool:
    if engine_id not in {"codex", "gemini-cli"} or not settings.managed_ai_runtime_enabled:
        return False
    try:
        from app.ai_gateway import resolve_gateway_config
        from app.ai_runtime.capability import managed_runtime_enabled

        config = resolve_gateway_config()
        return bool(
            managed_runtime_enabled()
            and config.configured
            and (config.default_model or config.recommendation_model)
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _engine_sandbox_configured(engine_id: str) -> bool:
    if engine_id == "codex":
        return True
    key = engine_id.upper().replace("-", "_")
    if os.environ.get(f"BUDGETLOOP_{key}_SANDBOX_COMMAND"):
        return True
    if engine_id == "gemini-cli":
        declared_ready = os.environ.get(
            "BUDGETLOOP_GEMINI_CLI_SANDBOX_READY", ""
        ).lower() in {
            "1",
            "true",
            "yes",
        }
        return declared_ready and bool(shutil.which("docker") or shutil.which("podman"))
    return os.environ.get("BUDGETLOOP_OPENCODE_ALLOW_HOST_EXECUTION", "").lower() in {
        "1",
        "true",
        "yes",
    }


def engine_to_dict(engine: ExecutionEngine) -> dict[str, Any]:
    preflight = engine_preflight(engine.id)
    package_installed = bool(preflight.binary_path) if engine.transport == "cli" else None
    managed_ai_ready = (
        _managed_credentials_configured(engine.id)
        if engine.id in {"codex", "gemini-cli"}
        else None
    )
    return {
        "id": engine.id,
        "name": engine.name,
        "repository": engine.repository,
        "url": engine.url,
        "revision": engine.revision,
        "reviewed_stars": engine.reviewed_stars,
        "license": engine.license,
        "license_scope": engine.license_scope,
        "source_path": engine.source_path,
        "source_downloaded": preflight.source_downloaded,
        "package_installed": package_installed,
        "managed_ai_ready": managed_ai_ready,
        "transport": engine.transport,
        "command": engine.command,
        "distribution_package": engine.distribution_package,
        "distribution_version": engine.distribution_version,
        "capabilities": list(engine.capabilities),
        "credential_hint": engine.credential_hint,
        "runtime_available": preflight.runtime_available,
        "availability_reason": preflight.reason,
        "default": engine.id == DEFAULT_ENGINE_ID,
    }


def list_engines() -> list[dict[str, Any]]:
    return [engine_to_dict(engine) for engine in ENGINES]
