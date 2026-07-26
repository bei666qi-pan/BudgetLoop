from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.ai_gateway import GatewayClient, resolve_gateway_config
from app.ai_gateway.local_settings import (
    LocalGatewaySettings,
    load_local_settings,
    public_local_settings,
    save_local_settings,
)
from app.ai_runtime import (
    RuntimeCapabilityError,
    issue_runtime_capability,
    managed_runtime_environment,
    validate_runtime_capability,
)
from app.api.runtime_ai import (
    NativeUsageTracker,
    managed_chat_completions,
    managed_gemini_stream,
    managed_responses,
)
from app.core.config import Settings, settings
from app.main import app
from app.worker.cli_client import engine_environment
from app.worker.workspace_manager import WorkspaceManager

pytestmark = pytest.mark.unit


def _settings(**overrides) -> Settings:
    values = {
        "api_token": "operator-token",
        "ai_gateway_type": "compatible",
        "ai_gateway_base_url": "https://gateway.example/v1",
        "ai_gateway_api_key": "upstream-secret",
        "ai_gateway_recommendation_model": "recommend-model",
        "ai_gateway_default_model": "app-model",
        "ai_gateway_reasoning_effort": "max",
        "ai_gateway_thinking_enabled": True,
        "ai_gateway_thinking_budget_tokens": 65_536,
        "managed_ai_runtime_enabled": True,
        "managed_ai_runtime_token_ttl_seconds": 600,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_local_settings_are_atomic_validated_and_secret_free(monkeypatch, tmp_path) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setenv("BUDGETLOOP_LOCAL_AI_SETTINGS_PATH", str(path))
    selected = LocalGatewaySettings(
        base_url="https://gateway.example/v1",
        recommendation_model="recommend-model",
        default_model="app-model",
        reasoning_effort="max",
        thinking_enabled=True,
        thinking_budget_tokens=65_536,
    )
    save_local_settings(selected)
    assert path.stat().st_mode & 0o777 == 0o600
    assert load_local_settings() == selected
    assert "api_key" not in path.read_text(encoding="utf-8")


def test_public_local_settings_never_returns_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BUDGETLOOP_LOCAL_AI_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(
        "app.ai_gateway.local_settings.read_keychain_secret", lambda: "secret-value"
    )
    public = public_local_settings()
    assert public["secret_configured"] is True
    assert "secret-value" not in json.dumps(public)
    assert "api_key" not in public


def test_settings_endpoint_uses_environment_as_secret_free_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SKIP_MIGRATIONS", "1")
    monkeypatch.setenv("BUDGETLOOP_LOCAL_AI_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings, "ai_gateway_type", "compatible")
    monkeypatch.setattr(settings, "ai_gateway_base_url", "https://gateway.example/v1")
    monkeypatch.setattr(settings, "ai_gateway_api_key", "upstream-secret")
    monkeypatch.setattr(settings, "ai_gateway_recommendation_model", "recommend-model")
    monkeypatch.setattr(settings, "ai_gateway_default_model", "app-model")
    monkeypatch.setattr(settings, "ai_gateway_reasoning_effort", "max")
    monkeypatch.setattr(settings, "ai_gateway_thinking_enabled", True)
    monkeypatch.setattr(settings, "ai_gateway_thinking_budget_tokens", 65_536)
    with TestClient(app) as client:
        response = client.get(
            "/api/ai-gateway/settings",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
    assert response.status_code == 200
    assert response.json()["base_url"] == "https://gateway.example/v1"
    assert response.json()["reasoning_effort"] == "max"
    assert response.json()["thinking_budget_tokens"] == 65_536
    assert "upstream-secret" not in response.text
    assert "api_key" not in response.json()


def test_reasoning_policy_is_max_and_not_silently_downgraded() -> None:
    source = _settings()
    config = resolve_gateway_config(source)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "max"
        assert body["thinking"] == {"type": "enabled", "budget_tokens": 65_536}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"recommendations": []}'}}]},
        )

    GatewayClient(config, transport=httpx.MockTransport(handler)).recommend([])


def test_runtime_capability_validates_scope_tamper_and_expiry() -> None:
    source = _settings()
    config = resolve_gateway_config(source)
    run_id = uuid.uuid4()
    token = issue_runtime_capability(run_id, now=100, source=source, config=config)
    claims = validate_runtime_capability(token, now=101, source=source, config=config)
    assert claims.run_id == run_id
    assert claims.model == "app-model"
    with pytest.raises(RuntimeCapabilityError, match="invalid_runtime_capability"):
        validate_runtime_capability(token + "x", now=101, source=source, config=config)
    with pytest.raises(RuntimeCapabilityError, match="runtime_capability_expired"):
        validate_runtime_capability(token, now=701, source=source, config=config)


def test_invalid_run_id_never_breaks_workspace_setup() -> None:
    source = _settings()
    config = resolve_gateway_config(source)
    with pytest.raises(RuntimeCapabilityError, match="invalid_runtime_run_id"):
        issue_runtime_capability("run1", source=source, config=config)
    assert managed_runtime_environment("run1", source=source, config=config) == {}


def _runtime_request(body: bytes, *, query: bytes = b"") -> Request:
    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/", "query_string": query},
        receive,
    )


@pytest.mark.asyncio
async def test_runtime_proxy_rejects_oversize_and_model_mismatch(monkeypatch) -> None:
    run_id = uuid.uuid4()
    claims = SimpleNamespace(run_id=run_id, model="app-model")
    monkeypatch.setattr("app.api.runtime_ai.validate_runtime_capability", lambda _token: claims)
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status="EXECUTING")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="scoped")

    monkeypatch.setattr(settings, "managed_ai_runtime_max_request_bytes", 1)
    with pytest.raises(HTTPException) as oversize:
        await managed_chat_completions(_runtime_request(b"{}"), credentials, db)
    assert (oversize.value.status_code, oversize.value.detail) == (
        413,
        "runtime_request_too_large",
    )

    monkeypatch.setattr(settings, "managed_ai_runtime_max_request_bytes", 10_000)
    body = json.dumps({"model": "other-model", "messages": []}).encode()
    with pytest.raises(HTTPException) as mismatch:
        await managed_chat_completions(_runtime_request(body), credentials, db)
    assert (mismatch.value.status_code, mismatch.value.detail) == (
        403,
        "runtime_model_not_allowed",
    )
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_responses_proxy_replaces_runtime_auth_and_settles_usage(monkeypatch) -> None:
    run_id = uuid.uuid4()
    claims = SimpleNamespace(run_id=run_id, model="app-model")
    monkeypatch.setattr("app.api.runtime_ai.validate_runtime_capability", lambda _token: claims)
    monkeypatch.setattr(
        "app.api.runtime_ai.resolve_gateway_config",
        lambda: resolve_gateway_config(_settings()),
    )
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": "response-1", "usage": {"total_tokens": 17}},
            headers={"Content-Type": "application/json", "X-Secret": "no"},
        )

    monkeypatch.setattr(
        "app.api.runtime_ai._native_http_client",
        lambda config: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Authorization": f"Bearer {config.api_key}"},
        ),
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status="EXECUTING")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="scoped-runtime")
    response = await managed_responses(
        _runtime_request(json.dumps({"model": "app-model", "input": "hi"}).encode()),
        credentials,
        db,
    )

    assert response.status_code == 200
    assert seen["authorization"] == "Bearer upstream-secret"
    assert "scoped-runtime" not in json.dumps(seen)
    assert seen["url"] == "https://gateway.example/v1/responses"
    assert seen["payload"] == {
        "model": "app-model",
        "input": "hi",
        "reasoning_effort": "max",
        "thinking": {"type": "enabled", "budget_tokens": 65_536},
    }
    assert "x-secret" not in response.headers
    assert db.execute.call_count == 2


@pytest.mark.asyncio
async def test_gemini_stream_strips_query_capability_and_tracks_sse_usage(monkeypatch) -> None:
    run_id = uuid.uuid4()
    claims = SimpleNamespace(run_id=run_id, model="app-model")
    monkeypatch.setattr("app.api.runtime_ai.validate_runtime_capability", lambda _token: claims)
    monkeypatch.setattr(
        "app.api.runtime_ai.resolve_gateway_config",
        lambda: resolve_gateway_config(_settings()),
    )
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=(
                b'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}\n\n'
                b'data: {"usageMetadata":{"totalTokenCount":23}}\n\n'
            ),
            headers={"Content-Type": "text/event-stream"},
        )

    monkeypatch.setattr(
        "app.api.runtime_ai._native_http_client",
        lambda config: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Authorization": f"Bearer {config.api_key}"},
        ),
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status="EXECUTING")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="scoped-runtime")
    response = await managed_gemini_stream(
        "app-model",
        _runtime_request(
            json.dumps({"contents": [{"parts": [{"text": "hi"}]}]}).encode(),
            query=b"alt=sse&key=scoped-runtime",
        ),
        credentials,
        db,
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert b"totalTokenCount" in body
    assert seen["authorization"] == "Bearer upstream-secret"
    assert seen["url"] == (
        "https://gateway.example/v1beta/models/app-model:streamGenerateContent?alt=sse"
    )
    assert seen["payload"]["generationConfig"]["thinkingConfig"] == {
        "thinkingBudget": 65_536,
        "includeThoughts": True,
    }
    assert "scoped-runtime" not in json.dumps(seen)
    assert db.execute.call_count == 2


def test_native_usage_tracker_is_bounded_and_understands_responses_events() -> None:
    tracker = NativeUsageTracker()
    tracker.feed(b"x" * 100_000)
    tracker.feed(b'\ndata: {"response":{"usage":{"input_tokens":3,"output_tokens":5}}}\n')
    tracker.finish()
    assert tracker.total_tokens == 8


def test_runtime_environment_is_default_on_and_disableable() -> None:
    source = _settings()
    config = resolve_gateway_config(source)
    environment = managed_runtime_environment(uuid.uuid4(), source=source, config=config)
    assert environment["OPENAI_BASE_URL"].endswith("/api/runtime/ai/v1")
    assert environment["OPENAI_MODEL"] == "app-model"
    assert environment["GOOGLE_GEMINI_BASE_URL"].endswith("/api/runtime/ai")
    assert environment["BUDGETLOOP_AI_CONTAINER_GEMINI_BASE_URL"].startswith(
        "http://host.docker.internal"
    )
    assert environment["GEMINI_MODEL"] == "app-model"
    assert environment["GEMINI_API_KEY_AUTH_MECHANISM"] == "bearer"
    assert environment["GEMINI_API_KEY"] == environment["OPENAI_API_KEY"]
    assert "upstream-secret" not in json.dumps(environment)
    disabled = managed_runtime_environment(
        uuid.uuid4(),
        source=_settings(managed_ai_runtime_enabled=False),
        config=config,
    )
    assert disabled == {}


def test_cli_environment_injects_only_scoped_runtime(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "cli_engine_state_root", str(tmp_path / "state"))
    runtime = {
        "OPENAI_BASE_URL": "http://127.0.0.1/runtime",
        "OPENAI_API_KEY": "scoped-token",
        "OPENAI_MODEL": "app-model",
        "BUDGETLOOP_AI_MANAGED": "1",
        "UNSAFE": "must-not-pass",
    }
    environment = engine_environment("codex", runtime_env=runtime)
    assert environment["OPENAI_API_KEY"] == "scoped-token"
    assert "UNSAFE" not in environment
    config = (tmp_path / "state" / "codex" / "config.toml").read_text(encoding="utf-8")
    assert 'wire_api = "responses"' in config
    assert 'model_reasoning_effort = "xhigh"' in config
    assert "scoped-token" not in config


def test_docker_workspace_receives_scoped_runtime_env(monkeypatch) -> None:
    runtime = {
        "OPENAI_BASE_URL": "http://host.docker.internal/runtime",
        "OPENAI_API_KEY": "scoped-token",
        "OPENAI_MODEL": "app-model",
        "BUDGETLOOP_AI_MANAGED": "1",
    }
    monkeypatch.setattr(
        "app.worker.workspace_manager.managed_runtime_environment",
        lambda _run_id, container=False: runtime if container else {},
    )
    client = MagicMock()
    volume = client.volumes.get.return_value
    volume.name = "volume"
    container = client.containers.run.return_value
    container.id = "container"
    container.ports = {"8000/tcp": [{"HostPort": "32000"}]}
    manager = WorkspaceManager(docker_client=client)
    monkeypatch.setattr(manager, "_wait_healthy", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())
    handle = manager.provision(str(uuid.uuid4()))
    docker_environment = client.containers.run.call_args.kwargs["environment"]
    assert docker_environment["OPENAI_API_KEY"] == "scoped-token"
    assert handle.runtime_env == runtime


def test_settings_endpoint_is_authenticated_write_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SKIP_MIGRATIONS", "1")
    monkeypatch.setenv("BUDGETLOOP_LOCAL_AI_SETTINGS_PATH", str(tmp_path / "settings.json"))
    written: list[str] = []
    monkeypatch.setattr("app.api.ai_gateway.write_keychain_secret", written.append)
    monkeypatch.setattr("app.ai_gateway.local_settings.read_keychain_secret", lambda: "stored")
    payload = {
        "kind": "compatible",
        "base_url": "https://gateway.example/v1",
        "console_url": "",
        "recommendation_model": "recommend-model",
        "default_model": "app-model",
        "deployment_label": "Private model",
        "network_label": "Secure access",
        "reasoning_effort": "max",
        "thinking_enabled": True,
        "thinking_budget_tokens": 65_536,
        "managed_app_inheritance_enabled": False,
        "api_key": "replacement-secret",
    }
    with TestClient(app) as client:
        assert client.get("/api/ai-gateway/settings").status_code == 401
        response = client.put(
            "/api/ai-gateway/settings",
            headers={"Authorization": f"Bearer {settings.api_token}"},
            json=payload,
        )
    assert response.status_code == 200
    assert written == ["replacement-secret"]
    assert response.json()["secret_configured"] is True
    assert "replacement-secret" not in response.text
    assert response.json()["managed_app_inheritance_enabled"] is False
