from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.team_presets import CATALOG, build_activation_plan, recommend_presets
from app.team_presets.catalog import (
    CATALOG_PATH,
    aggregate_budget,
    get_preset,
    list_presets,
    load_catalog,
    preset_to_dict,
)

EXPECTED_PRESETS = {
    "general-project",
    "software-delivery",
    "game-development",
    "business-growth",
    "product-launch",
    "brand-content",
    "market-research",
    "data-analysis",
    "customer-support",
}


def _catalog_document() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def _write_catalog(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_catalog_loads_all_beginner_presets_with_high_star_provenance() -> None:
    assert {preset.id for preset in CATALOG} == EXPECTED_PRESETS
    assert all(2 <= len(preset.roles) <= 8 for preset in CATALOG)
    sources = {source.key: source for preset in CATALOG for source in preset.sources}
    assert sources["langgraph"].integration == "runtime"
    assert sources["langgraph"].reviewed_stars >= 10_000
    assert all(source.reviewed_stars >= 10_000 for source in sources.values())
    assert {source.integration for source in sources.values()} == {"runtime", "pattern"}


def test_catalog_preserves_crewai_fields_and_stable_serialization() -> None:
    game = get_preset("game-development", 1)
    assert game is not None
    assert game.roles[0].role == "制作人与项目统筹"
    assert game.roles[0].goal
    assert game.roles[0].backstory
    assert all(task.description and task.expected_output and task.agent for task in game.tasks)
    assert preset_to_dict(game) == preset_to_dict(game)
    assert preset_to_dict(game)["sources"][-1]["runtime_dependency"] is True
    assert preset_to_dict(game)["requires_third_party_setup"] is False


def test_category_version_lookup_and_aggregate_budget() -> None:
    business = list_presets("business")
    assert [preset.id for preset in business] == ["business-growth", "product-launch"]
    assert list_presets("missing") == ()
    assert get_preset("game-development").version == 1  # type: ignore[union-attr]
    assert get_preset("missing") is None
    game = get_preset("game-development")
    assert game is not None
    totals = aggregate_budget(game.roles)
    assert totals == {"max_total_tokens": 116_000, "max_llm_calls": 100, "max_cost": 25.0}


def test_langgraph_recommendation_ranks_game_and_is_deterministic() -> None:
    first = recommend_presets("做一个手机解谜游戏试玩版", pace="fast", risk="creative")
    second = recommend_presets("做一个手机解谜游戏试玩版", pace="fast", risk="creative")
    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    assert first[0].preset.id == "game-development"
    assert first[0].confidence == 95
    assert "游戏" in first[0].matched_signals
    assert first[0].fallback is False


def test_langgraph_recommendation_uses_public_generic_fallback() -> None:
    recommendations = recommend_presets("帮我处理这个事情")
    assert len(recommendations) == 1
    assert recommendations[0].preset.id == "general-project"
    assert recommendations[0].confidence == 55
    assert recommendations[0].fallback is True
    assert recommendations[0].matched_signals == ("通用安全兜底",)


def test_activation_graph_invocation_emits_waves_handoffs_and_gates() -> None:
    game = get_preset("game-development")
    assert game is not None
    plan = build_activation_plan(game)
    assert plan["runtime"] == "langgraph"
    assert plan["entry"] == "planning"
    assert plan["activation_waves"] == [
        {"stage": "planning", "roles": ["producer"]},
        {"stage": "design", "roles": ["designer", "visual"]},
        {"stage": "implementation", "roles": ["client"]},
        {"stage": "review", "roles": ["qa"]},
    ]
    assert plan["required_handoffs"][-1] == {
        "from_stage": "implementation",
        "to_stage": "review",
    }
    assert plan["review_gates"] == ["design", "review"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update(schema_version=2), "schema_version"),
        (
            lambda doc: doc["presets"][0]["agents"]["lead"].pop("backstory"),
            "backstory",
        ),
        (
            lambda doc: doc["presets"][0]["sop"]["stages"][1].update(
                requires_handoff=["future-stage"]
            ),
            "earlier stages",
        ),
    ],
)
def test_invalid_catalog_is_rejected(tmp_path: Path, mutation, message: str) -> None:
    document = _catalog_document()
    mutation(document)
    with pytest.raises(ValueError, match=message):
        load_catalog(_write_catalog(tmp_path, document))


def test_unsafe_yaml_tags_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to load"):
        load_catalog(path)
