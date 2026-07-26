from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai_gateway import (
    GatewayClient,
    GatewayError,
    gateway_status,
    reset_gateway_status_cache,
    resolve_gateway_config,
)
from app.ai_gateway.config import NEW_API_PROVENANCE, GatewayConfig, safe_http_url
from app.core.config import Settings, settings
from app.main import app

pytestmark = pytest.mark.unit


def _settings(**overrides) -> Settings:
    values = {
        "ai_gateway_type": "new-api",
        "ai_gateway_base_url": "https://gateway.example/v1",
        "ai_gateway_api_key": "secret-gateway-token",
        "ai_gateway_console_url": "https://gateway.example/admin",
        "ai_gateway_recommendation_model": "budgetloop-recommendation",
        "ai_recommendation_enabled": True,
        "ai_gateway_status_ttl_seconds": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _config(**overrides) -> GatewayConfig:
    return resolve_gateway_config(_settings(**overrides))


def test_new_api_config_is_typed_normalized_and_redacted() -> None:
    config = _config()
    assert config.kind == "new-api"
    assert config.base_url == "https://gateway.example"
    assert config.openai_base_url == "https://gateway.example/v1"
    assert config.configured is True
    public = config.public_configuration()
    assert public["protocols"][:4] == [
        "OpenAI Chat Completions",
        "OpenAI Responses",
        "Claude Messages",
        "Gemini native",
    ]
    assert public["semantic_ai_router"] is False
    assert public["provenance"] == NEW_API_PROVENANCE
    assert "secret-gateway-token" not in json.dumps(public)


def test_legacy_litellm_variables_resolve_without_copying_secret() -> None:
    source = _settings(
        ai_gateway_type="",
        ai_gateway_base_url="",
        ai_gateway_api_key="",
        ai_gateway_console_url="",
        ai_gateway_recommendation_model="legacy-model",
        litellm_base_url="http://litellm:4000",
        litellm_master_key="legacy-secret",
    )
    config = resolve_gateway_config(source)
    assert config.kind == "litellm"
    assert config.openai_base_url == "http://litellm:4000/v1"
    assert config.api_key == "legacy-secret"
    assert "legacy-secret" not in json.dumps(config.public_configuration())


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/socket",
        "https://user:secret@example.com",
        "https://example.com?token=secret",
        "javascript:alert(1)",
        "",
    ],
)
def test_safe_http_url_rejects_unsafe_values(url: str) -> None:
    assert safe_http_url(url) is None


def test_incomplete_config_fails_closed_with_stable_reason() -> None:
    config = _config(ai_gateway_api_key="")
    assert config.configured is False
    assert config.configuration_reason == "missing_gateway_key"
    with pytest.raises(GatewayError, match="missing_gateway_key"):
        GatewayClient(config).preflight()


def test_client_preflight_and_recommendation_use_only_gateway_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "budgetloop-recommendation"}]})
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "budgetloop-recommendation"
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 4096
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"recommendations": []}'}}]},
        )

    client = GatewayClient(_config(), transport=httpx.MockTransport(handler))
    assert client.preflight() == "2xx"
    result = client.recommend([{"role": "user", "content": "bounded"}])
    assert result.content == '{"recommendations": []}'
    assert all(request.headers["authorization"] == "Bearer secret-gateway-token" for request in seen)
    assert all("secret-gateway-token" not in request.url.query.decode() for request in seen)


def test_compatible_preflight_uses_invalid_chat_probe_when_models_are_unavailable() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(403)
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content) == {"model": "budgetloop-recommendation", "messages": []}
        return httpx.Response(400, json={"error": {"message": "messages cannot be empty"}})

    assert GatewayClient(
        _config(ai_gateway_type="compatible"), transport=httpx.MockTransport(handler)
    ).preflight() == "2xx"
    assert [request.url.path for request in seen] == ["/v1/models", "/v1/chat/completions"]


def test_compatible_preflight_does_not_hide_chat_authentication_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403 if request.url.path == "/v1/models" else 401)

    with pytest.raises(GatewayError, match="authentication_failed"):
        GatewayClient(
            _config(ai_gateway_type="compatible"), transport=httpx.MockTransport(handler)
        ).preflight()


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "authentication_failed"), (429, "rate_limited"), (503, "upstream_unavailable")],
)
def test_client_maps_http_errors_without_raw_body(status: int, code: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status, text="upstream leaked sk-secret-value")
    )
    with pytest.raises(GatewayError) as captured:
        GatewayClient(_config(), transport=transport).preflight()
    assert captured.value.code == code
    assert "sk-secret-value" not in str(captured.value)


def test_client_maps_timeout_without_raw_exception() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("contains secret", request=request)

    with pytest.raises(GatewayError) as captured:
        GatewayClient(_config(), transport=httpx.MockTransport(timeout)).recommend([])
    assert captured.value.code == "timeout"
    assert "secret" not in str(captured.value)


def test_reasoning_recommendation_uses_longer_bounded_read_timeout(monkeypatch) -> None:
    config = _config(
        ai_gateway_type="compatible",
        ai_gateway_read_timeout_seconds=8,
        ai_gateway_reasoning_effort="max",
        ai_gateway_thinking_enabled=True,
        ai_gateway_thinking_budget_tokens=65_536,
    )
    captured: list[float | None] = []
    original_client = GatewayClient._client

    def observed_client(self, *, read_timeout_seconds=None):
        captured.append(read_timeout_seconds)
        return original_client(self, read_timeout_seconds=read_timeout_seconds)

    monkeypatch.setattr(GatewayClient, "_client", observed_client)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"recommendations": []}'}}]},
        )
    )
    GatewayClient(config, transport=transport).recommend([])
    assert captured == [GatewayClient.REASONING_RECOMMENDATION_TIMEOUT_SECONDS]
    assert captured[0] <= 120


def test_gateway_status_is_redacted_and_cacheable() -> None:
    calls = 0

    class FakeClient:
        def __init__(self, _config: GatewayConfig) -> None:
            pass

        def preflight(self) -> str:
            nonlocal calls
            calls += 1
            return "2xx"

    config = resolve_gateway_config(
        _settings(ai_gateway_status_ttl_seconds=30)
    )
    reset_gateway_status_cache()
    first = gateway_status(config=config, client_factory=FakeClient)
    second = gateway_status(config=config, client_factory=FakeClient)
    assert first == second
    assert calls == 1
    assert first["healthy"] is True
    assert "secret-gateway-token" not in json.dumps(first)


def test_status_endpoint_is_authenticated_and_contains_no_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.ai_gateway.gateway_status",
        lambda: {**_config().public_configuration(), "healthy": True, "reason_code": None},
    )
    with TestClient(app) as client:
        assert client.get("/api/ai-gateway/status").status_code == 401
        response = client.get(
            "/api/ai-gateway/status",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
    assert response.status_code == 200
    assert response.json()["type"] == "new-api"
    assert "secret-gateway-token" not in response.text
