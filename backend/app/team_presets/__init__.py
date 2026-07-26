"""Versioned Agent Team presets backed by a local LangGraph runtime."""

from app.team_presets.activation import build_activation_plan
from app.team_presets.ai_recommend import (
    RecommendationOutcome,
    build_ai_recommendation_messages,
    parse_ai_recommendations,
    recommend_presets_ai_first,
)
from app.team_presets.catalog import CATALOG, get_preset, list_presets, preset_to_dict
from app.team_presets.recommend import recommend_presets, recommend_presets_local

__all__ = [
    "CATALOG",
    "build_activation_plan",
    "build_ai_recommendation_messages",
    "get_preset",
    "list_presets",
    "parse_ai_recommendations",
    "preset_to_dict",
    "recommend_presets",
    "recommend_presets_ai_first",
    "recommend_presets_local",
    "RecommendationOutcome",
]
