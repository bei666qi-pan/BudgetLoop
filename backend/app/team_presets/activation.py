"""Compile MetaGPT-style SOP stages into executable LangGraph activation plans."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.team_presets.catalog import SOPStage, TeamPreset


class ActivationState(TypedDict, total=False):
    activation_waves: list[dict[str, Any]]
    required_handoffs: list[dict[str, str]]
    review_gates: list[str]


def _stage_node(stage: SOPStage):
    def activate(state: ActivationState) -> ActivationState:
        waves = list(state.get("activation_waves", []))
        handoffs = list(state.get("required_handoffs", []))
        gates = list(state.get("review_gates", []))
        waves.append({"stage": stage.id, "roles": list(stage.agents)})
        handoffs.extend(
            {"from_stage": dependency, "to_stage": stage.id}
            for dependency in stage.requires_handoff
        )
        if stage.review_gate:
            gates.append(stage.id)
        return {
            "activation_waves": waves,
            "required_handoffs": handoffs,
            "review_gates": gates,
        }

    return activate


@lru_cache(maxsize=64)
def _compile_activation_graph(preset: TeamPreset):
    graph = StateGraph(ActivationState)
    for stage in preset.sop_stages:
        graph.add_node(stage.id, _stage_node(stage))
    graph.add_edge(START, preset.sop_stages[0].id)
    for current, following in zip(preset.sop_stages, preset.sop_stages[1:], strict=False):
        graph.add_edge(current.id, following.id)
    graph.add_edge(preset.sop_stages[-1].id, END)
    return graph.compile()


def build_activation_plan(preset: TeamPreset) -> dict[str, Any]:
    """Invoke a preset-specific compiled graph and return its auditable topology."""
    result = _compile_activation_graph(preset).invoke(
        {"activation_waves": [], "required_handoffs": [], "review_gates": []}
    )
    return {
        "entry": preset.sop_entry,
        "activation_waves": result["activation_waves"],
        "required_handoffs": result["required_handoffs"],
        "review_gates": result["review_gates"],
        "runtime": "langgraph",
    }
