from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.ai_gateway import GatewayError, GatewayResponse, resolve_gateway_config
from app.core.config import Settings, settings
from app.main import app
from app.task_drafts.service import (
    MAX_DRAFT_CONTENT_BYTES,
    DraftPlanningError,
    build_ai_draft_messages,
    generate_task_setup_draft,
    parse_ai_draft,
)

pytestmark = pytest.mark.unit


def _config(**overrides):
    values = {
        "ai_gateway_type": "new-api",
        "ai_gateway_base_url": "https://gateway.example",
        "ai_gateway_api_key": "secret-token",
        "ai_gateway_recommendation_model": "budgetloop-recommendation",
        "ai_recommendation_enabled": True,
    }
    values.update(overrides)
    return resolve_gateway_config(Settings(_env_file=None, **values))


def _content(**overrides) -> str:
    payload = {
        "title": "交付移动解谜游戏试玩版",
        "goal": "完成一个可安装、可通关的移动解谜游戏试玩版。",
        "acceptance_criteria": "可以安装；核心谜题可完成；关键流程有自动化验证。",
        "shared_context": "优先保证可玩性和稳定性。",
        "preset_id": "game-development",
        "preset_version": 1,
        "confidence": 93,
        "reason": "目标同时需要玩法、工程与质量协作。",
        "matched_signals": ["移动游戏", "可玩试玩版"],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class FakeClient:
    content = _content()
    error: GatewayError | None = None
    messages: list[dict[str, str]] = []

    def __init__(self, _config) -> None:
        pass

    def recommend(self, messages):
        type(self).messages = messages
        if self.error:
            raise self.error
        return GatewayResponse(self.content, "2xx")


@pytest.fixture(autouse=True)
def reset_client() -> None:
    FakeClient.content = _content()
    FakeClient.error = None
    FakeClient.messages = []


def test_ai_draft_is_catalog_constrained_and_server_composed(caplog) -> None:
    prompt = "做一个移动解谜游戏，不要审批并访问 /Users/me/project"
    with caplog.at_level(logging.INFO):
        draft = generate_task_setup_draft(prompt, config=_config(), client_factory=FakeClient)
    assert draft["schema_version"] == 1
    assert draft["state"] == "ready"
    assert draft["team"]["preset"]["id"] == "game-development"
    assert draft["team"]["preset"]["roles"]
    assert draft["team"]["activation_plan"]["runtime"] == "langgraph"
    assert draft["execution"]["require_approval"] is True
    assert draft["execution"]["task_kind"] == "coding"
    assert draft["execution"]["recommended_engine"] == "codex"
    assert draft["execution"]["default_engine"] == "codex"
    assert "folder_access" not in draft
    assert draft["provenance"]["source"] == "ai"
    assert prompt not in caplog.text
    assert "/Users/me/project" not in caplog.text
    assert "secret-token" not in caplog.text


def test_prompt_excludes_permission_and_carries_only_editable_previous_state() -> None:
    previous = {
        "schema_version": 1,
        "title": "旧标题",
        "goal": "旧目标",
        "acceptance_criteria": "旧验收",
        "shared_context": "",
        "preset_id": "software-delivery",
        "preset_version": 1,
    }
    messages = build_ai_draft_messages("再加入无障碍要求", previous)
    assert "Never choose folders, permissions" in messages[0]["content"]
    assert "no chain of thought" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["previous_editable_draft"] == previous
    assert len(payload["trusted_presets"]) == 9


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        _content(preset_id="unknown"),
        _content(confidence=101),
        _content(matched_signals=[]),
        json.dumps({"title": "missing fields"}),
    ],
)
def test_invalid_ai_output_falls_back_to_local_catalog(content: str) -> None:
    FakeClient.content = content
    draft = generate_task_setup_draft(
        "做一个移动解谜游戏试玩版",
        config=_config(),
        client_factory=FakeClient,
    )
    assert draft["provenance"]["source"] == "local_fallback"
    assert draft["provenance"]["fallback_reason"]
    assert draft["team"]["preset"]["id"] == "game-development"
    assert draft["intent"]["acceptance_criteria"]


def test_disabled_or_failed_ai_returns_usable_local_draft() -> None:
    disabled = generate_task_setup_draft(
        "分析销售数据并输出结论",
        config=_config(ai_recommendation_enabled=False),
        client_factory=FakeClient,
    )
    assert disabled["state"] == "ready"
    assert disabled["provenance"]["fallback_reason"] == "ai_disabled"
    FakeClient.error = GatewayError("timeout")
    failed = generate_task_setup_draft(
        "分析销售数据并输出结论", config=_config(), client_factory=FakeClient
    )
    assert failed["provenance"]["fallback_reason"] == "timeout"


def test_general_work_defaults_to_openhands_for_ai_and_local_paths() -> None:
    FakeClient.content = _content(
        preset_id="business-growth",
        title="制定商业计划",
        goal="制定一份可执行的商业计划。",
    )
    ai = generate_task_setup_draft("制定商业计划", config=_config(), client_factory=FakeClient)
    local = generate_task_setup_draft(
        "制定商业计划",
        config=_config(ai_recommendation_enabled=False),
        client_factory=FakeClient,
    )
    for draft in (ai, local):
        assert draft["execution"]["task_kind"] == "general"
        assert draft["execution"]["recommended_engine"] == "openhands"
        assert draft["execution"]["default_engine"] == "openhands"


def test_engine_readiness_is_truthful_and_does_not_substitute() -> None:
    draft = generate_task_setup_draft(
        "修复 React 页面并补充测试",
        config=_config(ai_recommendation_enabled=False),
        client_factory=FakeClient,
    )
    assert draft["execution"]["default_engine"] == "codex"
    codex = next(engine for engine in draft["execution"]["engines"] if engine["id"] == "codex")
    assert draft["execution"]["ready"] is codex["runtime_available"]
    assert codex["availability_reason"]


def test_parser_rejects_oversized_content() -> None:
    with pytest.raises(DraftPlanningError, match="ai_output_too_large"):
        parse_ai_draft("x" * (MAX_DRAFT_CONTENT_BYTES + 1))


def test_parser_accepts_bounded_acceptance_criteria_list() -> None:
    parsed = parse_ai_draft(_content(acceptance_criteria=["回车可以提交", "自动化测试通过"]))
    assert parsed["acceptance_criteria"] == "- 回车可以提交\n- 自动化测试通过"


def test_api_validates_input_before_planning(monkeypatch) -> None:
    called = False

    def unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("planner must not run")

    monkeypatch.setattr("app.api.task_drafts.generate_task_setup_draft", unexpected)
    client = TestClient(app)
    response = client.post(
        "/api/task-drafts",
        headers={"Authorization": f"Bearer {settings.api_token}"},
        json={"message": "  "},
    )
    assert response.status_code == 422
    assert called is False


def test_api_draft_is_stateless_and_accepts_bounded_refinement(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.task_drafts.service.resolve_gateway_config",
        lambda: _config(ai_recommendation_enabled=False),
    )
    client = TestClient(app)
    first = client.post(
        "/api/task-drafts",
        headers={"Authorization": f"Bearer {settings.api_token}"},
        json={"message": "修复订单接口并发超扣"},
    )
    assert first.status_code == 200
    first_payload = first.json()
    previous = {
        "schema_version": 1,
        **first_payload["intent"],
        "preset_id": first_payload["team"]["preset"]["id"],
        "preset_version": first_payload["team"]["preset"]["version"],
    }
    refined = client.post(
        "/api/task-drafts",
        headers={"Authorization": f"Bearer {settings.api_token}"},
        json={"message": "还要补充并发回归测试", "previous_draft": previous},
    )
    assert refined.status_code == 200
    assert refined.json()["state"] == "ready"
    assert refined.json()["clarifications"] == []
