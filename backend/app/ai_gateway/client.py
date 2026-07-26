"""Bounded OpenAI-compatible client used through the selected gateway."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.ai_gateway.config import GatewayConfig


class GatewayError(RuntimeError):
    """Sanitized gateway failure. The public code never contains raw exceptions."""

    def __init__(self, code: str, *, status_class: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_class = status_class


@dataclass(frozen=True)
class GatewayResponse:
    content: str
    status_class: str


def _status_error(response: httpx.Response) -> GatewayError:
    status = response.status_code
    status_class = f"{status // 100}xx"
    if status in {401, 403}:
        return GatewayError("authentication_failed", status_class=status_class)
    if status == 429:
        return GatewayError("rate_limited", status_class=status_class)
    if status >= 500:
        return GatewayError("upstream_unavailable", status_class=status_class)
    return GatewayError("gateway_rejected_request", status_class=status_class)


class GatewayClient:
    # Structured planning is deliberately bounded, but reasoning profiles need
    # longer than the short reachability/read timeout used by normal gateway IO.
    REASONING_RECOMMENDATION_TIMEOUT_SECONDS = 120.0

    def __init__(
        self,
        config: GatewayConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "BudgetLoop/ai-gateway",
        }

    def _client(self, *, read_timeout_seconds: float | None = None) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=self.config.connect_timeout_seconds,
            read=read_timeout_seconds or self.config.read_timeout_seconds,
            write=self.config.read_timeout_seconds,
            pool=self.config.connect_timeout_seconds,
        )
        return httpx.Client(
            timeout=timeout,
            transport=self._transport,
            follow_redirects=False,
            headers=self._headers(),
        )

    def _require_configured(self) -> None:
        if not self.config.configured:
            raise GatewayError(self.config.configuration_reason or "gateway_unconfigured")

    def apply_reasoning_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a copy with the configured upstream reasoning extensions."""
        selected = dict(payload)
        if self.config.reasoning_effort:
            selected["reasoning_effort"] = self.config.reasoning_effort
        if self.config.thinking_enabled:
            selected["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget_tokens,
            }
        return selected

    def preflight(self) -> str:
        """Check an OpenAI-compatible gateway without generating model output.

        ``/models`` is the standard, zero-cost probe, but some enterprise
        compatible gateways intentionally expose only Chat Completions.  For
        those gateways, a deliberately invalid empty-message request proves
        that the authenticated route is reachable when it reaches request
        validation (400/422), without consuming a model completion.
        """
        self._require_configured()
        try:
            with self._client() as client:
                response = client.get(f"{self.config.openai_base_url}/models")
        except httpx.TimeoutException as exc:
            raise GatewayError("timeout") from exc
        except httpx.HTTPError as exc:
            raise GatewayError("gateway_unreachable") from exc
        if response.is_success:
            return f"{response.status_code // 100}xx"

        # A compatible gateway may intentionally deny or omit model listing.
        # Do not relax authentication errors: the fallback must reach the
        # Chat Completions request validator before it is considered healthy.
        if self.config.kind != "compatible" or response.status_code not in {403, 404, 405}:
            raise _status_error(response)
        try:
            with self._client() as client:
                probe = client.post(
                    f"{self.config.openai_base_url}/chat/completions",
                    json={
                        "model": self.config.default_model or self.config.recommendation_model,
                        "messages": [],
                    },
                )
        except httpx.TimeoutException as exc:
            raise GatewayError("timeout") from exc
        except httpx.HTTPError as exc:
            raise GatewayError("gateway_unreachable") from exc
        if probe.status_code in {400, 422}:
            return "2xx"
        if not probe.is_success:
            raise _status_error(probe)
        return f"{probe.status_code // 100}xx"

    def recommend(self, messages: list[dict[str, str]]) -> GatewayResponse:
        self._require_configured()
        if not self.config.recommendation_enabled:
            raise GatewayError("ai_disabled")
        payload: dict[str, Any] = self.apply_reasoning_policy({
            "model": self.config.recommendation_model,
            "messages": messages,
            "temperature": 0,
            # Reasoning tokens count against this limit on DeepSeek-compatible
            # models; 800 commonly truncates before the JSON answer begins.
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        })
        planning_timeout = self.config.read_timeout_seconds
        if self.config.reasoning_effort or self.config.thinking_enabled:
            planning_timeout = max(
                planning_timeout,
                self.REASONING_RECOMMENDATION_TIMEOUT_SECONDS,
            )
        try:
            with self._client(read_timeout_seconds=planning_timeout) as client:
                response = client.post(
                    f"{self.config.openai_base_url}/chat/completions",
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise GatewayError("timeout") from exc
        except httpx.HTTPError as exc:
            raise GatewayError("gateway_unreachable") from exc
        if not response.is_success:
            raise _status_error(response)
        if len(response.content) > self.config.max_response_bytes:
            raise GatewayError("response_too_large", status_class="2xx")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise GatewayError("invalid_gateway_response", status_class="2xx") from exc
        if not isinstance(content, str) or not content.strip():
            raise GatewayError("invalid_gateway_response", status_class="2xx")
        return GatewayResponse(content=content, status_class="2xx")

    def chat_completion(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Forward one already-validated Chat Completions payload."""
        self._require_configured()
        selected = self.apply_reasoning_policy(payload)
        try:
            with self._client() as client:
                response = client.post(
                    f"{self.config.openai_base_url}/chat/completions",
                    json=selected,
                )
        except httpx.TimeoutException as exc:
            raise GatewayError("timeout") from exc
        except httpx.HTTPError as exc:
            raise GatewayError("gateway_unreachable") from exc
        if not response.is_success:
            raise _status_error(response)
        if len(response.content) > self.config.max_response_bytes:
            raise GatewayError("response_too_large", status_class="2xx")
        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayError("invalid_gateway_response", status_class="2xx") from exc
        if not isinstance(data, dict):
            raise GatewayError("invalid_gateway_response", status_class="2xx")
        return data, "2xx"
