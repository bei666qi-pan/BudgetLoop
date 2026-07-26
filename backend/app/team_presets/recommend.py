"""Deterministic local fallback recommendation executed by LangGraph."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.team_presets.catalog import CATALOG, TeamPreset, preset_to_dict


@dataclass(frozen=True)
class Recommendation:
    preset: TeamPreset
    confidence: int
    reason: str
    matched_signals: tuple[str, ...]
    fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": preset_to_dict(self.preset),
            "confidence": self.confidence,
            "reason": self.reason,
            "matched_signals": list(self.matched_signals),
            "fallback": self.fallback,
        }


class RecommendationState(TypedDict, total=False):
    goal: str
    industry: str | None
    pace: str
    risk: str
    limit: int
    normalized: str
    category_hints: tuple[str, ...]
    scored: list[tuple[int, tuple[str, ...], TeamPreset]]
    use_fallback: bool
    recommendations: list[Recommendation]


def _normalize_node(state: RecommendationState) -> RecommendationState:
    values = (state.get("goal"), state.get("industry"))
    normalized = " ".join(value.strip().lower() for value in values if value and value.strip())
    return {"normalized": normalized}


def _classify_node(state: RecommendationState) -> RecommendationState:
    text = state["normalized"]
    hints = tuple(
        preset.category
        for preset in CATALOG
        if preset.id != "general-project"
        and any(keyword.lower() in text for signal in preset.signals for keyword in signal.keywords)
    )
    return {"category_hints": tuple(dict.fromkeys(hints))}


def _rank_node(state: RecommendationState) -> RecommendationState:
    text = state["normalized"]
    industry = state.get("industry")
    pace = state.get("pace", "steady")
    risk = state.get("risk", "balanced")
    scored: list[tuple[int, tuple[str, ...], TeamPreset]] = []

    for preset in CATALOG:
        if preset.id == "general-project":
            continue
        score = 0
        matched: list[str] = []
        for signal in preset.signals:
            if any(keyword.lower() in text for keyword in signal.keywords):
                score += signal.weight
                matched.append(signal.label)
        if industry and industry.strip().lower() in " ".join(preset.industries).lower():
            score += 5
            matched.append(f"行业：{industry.strip()}")
        if pace in preset.pace_tags:
            score += 1
        if risk in preset.risk_tags:
            score += 1
        scored.append((score, tuple(dict.fromkeys(matched)), preset))

    scored.sort(key=lambda item: (-item[0], item[2].id))
    return {"scored": scored, "use_fallback": not scored or scored[0][0] <= 2}


def _recommendation_route(state: RecommendationState) -> str:
    return "fallback" if state["use_fallback"] else "explain"


def _fallback_node(_state: RecommendationState) -> RecommendationState:
    generic = next(preset for preset in CATALOG if preset.id == "general-project")
    return {
        "recommendations": [
            Recommendation(
                preset=generic,
                confidence=55,
                reason="暂未识别到明确行业信号，先用覆盖规划、执行和验收的通用团队稳妥启动。",
                matched_signals=("通用安全兜底",),
                fallback=True,
            )
        ]
    }


def _explain_node(state: RecommendationState) -> RecommendationState:
    limit = max(1, min(state.get("limit", 3), 3))
    recommendations: list[Recommendation] = []
    for score, matched, preset in state["scored"][:limit]:
        if score <= 0:
            continue
        labels = "、".join(matched[:3]) or "交付偏好"
        recommendations.append(
            Recommendation(
                preset=preset,
                confidence=min(95, 58 + score * 3),
                reason=f"目标中匹配到{labels}，适合采用「{preset.coordination_pattern}」推进。",
                matched_signals=matched,
            )
        )
    return {"recommendations": recommendations}


def _finalize_node(state: RecommendationState) -> RecommendationState:
    return {"recommendations": list(state.get("recommendations", []))}


def _build_recommendation_graph():
    graph = StateGraph(RecommendationState)
    graph.add_node("normalize", _normalize_node)
    graph.add_node("classify", _classify_node)
    graph.add_node("rank", _rank_node)
    graph.add_node("explain", _explain_node)
    graph.add_node("fallback", _fallback_node)
    graph.add_node("finalize", _finalize_node)
    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "classify")
    graph.add_edge("classify", "rank")
    graph.add_conditional_edges(
        "rank", _recommendation_route, {"explain": "explain", "fallback": "fallback"}
    )
    graph.add_edge("explain", "finalize")
    graph.add_edge("fallback", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


RECOMMENDATION_GRAPH = _build_recommendation_graph()


def recommend_presets_local(
    goal: str,
    *,
    industry: str | None = None,
    pace: str = "steady",
    risk: str = "balanced",
    limit: int = 3,
) -> list[Recommendation]:
    """Invoke the deterministic local graph; no model, telemetry or key is used."""
    result = RECOMMENDATION_GRAPH.invoke(
        {
            "goal": goal,
            "industry": industry,
            "pace": pace,
            "risk": risk,
            "limit": limit,
        }
    )
    return result["recommendations"]


# Backward-compatible public name for callers that explicitly need local matching.
recommend_presets = recommend_presets_local
