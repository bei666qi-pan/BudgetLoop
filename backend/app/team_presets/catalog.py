"""Typed loader for CrewAI-compatible Agent Team preset YAML.

CrewAI's public role/goal/backstory and task vocabulary keeps the catalog
portable. BudgetLoop extensions add bounded budgets, skills, provenance and
MetaGPT-style SOP stages while preserving PostgreSQL as the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


@dataclass(frozen=True)
class SourceReference:
    key: str
    repository: str
    url: str
    license: str
    reviewed_stars: int
    reviewed_at: str
    integration: str


@dataclass(frozen=True)
class RoleBudget:
    max_total_tokens: int
    max_wall_time_seconds: int
    max_active_runtime_seconds: int
    max_llm_calls: int
    max_cost: float
    max_parallel_llm_calls: int


@dataclass(frozen=True)
class RolePreset:
    key: str
    role: str
    goal: str
    backstory: str
    skills: tuple[str, ...]
    budget: RoleBudget
    optional: bool = False

    @property
    def responsibility(self) -> str:
        """Backward-compatible name used by the existing session context."""
        return self.backstory


@dataclass(frozen=True)
class TaskPreset:
    key: str
    description: str
    expected_output: str
    agent: str


@dataclass(frozen=True)
class MatchSignal:
    label: str
    keywords: tuple[str, ...]
    weight: int


@dataclass(frozen=True)
class SOPStage:
    id: str
    agents: tuple[str, ...]
    requires_handoff: tuple[str, ...]
    review_gate: bool = False


@dataclass(frozen=True)
class TeamPreset:
    id: str
    version: int
    name: str
    category: str
    summary: str
    best_for: str
    coordination_pattern: str
    default_workspace_policy: str
    industries: tuple[str, ...]
    pace_tags: tuple[str, ...]
    risk_tags: tuple[str, ...]
    sources: tuple[SourceReference, ...]
    signals: tuple[MatchSignal, ...]
    roles: tuple[RolePreset, ...]
    tasks: tuple[TaskPreset, ...]
    sop_entry: str
    sop_stages: tuple[SOPStage, ...]


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping")
    return value


def _sequence(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be a list")
    return value


def _text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value.strip()


def _integer(value: Any, location: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{location} must be an integer >= {minimum}")
    return value


def _number(value: Any, location: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise ValueError(f"{location} must be a number >= {minimum}")
    return float(value)


def _text_tuple(value: Any, location: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = _sequence(value, location)
    result = tuple(_text(item, f"{location}[{index}]") for index, item in enumerate(values))
    if not allow_empty and not result:
        raise ValueError(f"{location} must not be empty")
    return result


def _parse_budget(value: Any, location: str) -> RoleBudget:
    raw = _mapping(value, location)
    return RoleBudget(
        max_total_tokens=_integer(raw.get("max_total_tokens"), f"{location}.max_total_tokens", minimum=1),
        max_wall_time_seconds=_integer(
            raw.get("max_wall_time_seconds"), f"{location}.max_wall_time_seconds", minimum=1
        ),
        max_active_runtime_seconds=_integer(
            raw.get("max_active_runtime_seconds"),
            f"{location}.max_active_runtime_seconds",
            minimum=1,
        ),
        max_llm_calls=_integer(raw.get("max_llm_calls"), f"{location}.max_llm_calls", minimum=1),
        max_cost=_number(raw.get("max_cost"), f"{location}.max_cost"),
        max_parallel_llm_calls=_integer(
            raw.get("max_parallel_llm_calls"),
            f"{location}.max_parallel_llm_calls",
            minimum=1,
        ),
    )


def _parse_sources(value: Any) -> dict[str, SourceReference]:
    sources: dict[str, SourceReference] = {}
    for key, item in _mapping(value, "sources").items():
        location = f"sources.{key}"
        raw = _mapping(item, location)
        integration = _text(raw.get("integration"), f"{location}.integration")
        if integration not in {"runtime", "pattern"}:
            raise ValueError(f"{location}.integration must be runtime or pattern")
        sources[key] = SourceReference(
            key=key,
            repository=_text(raw.get("repository"), f"{location}.repository"),
            url=_text(raw.get("url"), f"{location}.url"),
            license=_text(raw.get("license"), f"{location}.license"),
            reviewed_stars=_integer(raw.get("reviewed_stars"), f"{location}.reviewed_stars", minimum=1),
            reviewed_at=_text(raw.get("reviewed_at"), f"{location}.reviewed_at"),
            integration=integration,
        )
    return sources


def _parse_preset(value: Any, index: int, sources: dict[str, SourceReference]) -> TeamPreset:
    location = f"presets[{index}]"
    raw = _mapping(value, location)
    preset_id = _text(raw.get("id"), f"{location}.id")

    source_keys = _text_tuple(raw.get("sources"), f"{location}.sources")
    unknown_sources = set(source_keys) - sources.keys()
    if unknown_sources:
        raise ValueError(f"{location}.sources contains unknown entries: {sorted(unknown_sources)}")

    agents_raw = _mapping(raw.get("agents"), f"{location}.agents")
    if not 2 <= len(agents_raw) <= 8:
        raise ValueError(f"{location}.agents must contain 2 to 8 roles")
    roles: list[RolePreset] = []
    for key, item in agents_raw.items():
        role_location = f"{location}.agents.{key}"
        agent = _mapping(item, role_location)
        optional = agent.get("optional", False)
        if not isinstance(optional, bool):
            raise ValueError(f"{role_location}.optional must be a boolean")
        roles.append(
            RolePreset(
                key=key,
                role=_text(agent.get("role"), f"{role_location}.role"),
                goal=_text(agent.get("goal"), f"{role_location}.goal"),
                backstory=_text(agent.get("backstory"), f"{role_location}.backstory"),
                skills=_text_tuple(agent.get("skills"), f"{role_location}.skills"),
                budget=_parse_budget(agent.get("budget"), f"{role_location}.budget"),
                optional=optional,
            )
        )

    tasks_raw = _mapping(raw.get("tasks"), f"{location}.tasks")
    tasks: list[TaskPreset] = []
    for key, item in tasks_raw.items():
        task_location = f"{location}.tasks.{key}"
        task = _mapping(item, task_location)
        agent_key = _text(task.get("agent"), f"{task_location}.agent")
        if agent_key not in agents_raw:
            raise ValueError(f"{task_location}.agent references unknown agent {agent_key!r}")
        tasks.append(
            TaskPreset(
                key=key,
                description=_text(task.get("description"), f"{task_location}.description"),
                expected_output=_text(
                    task.get("expected_output"), f"{task_location}.expected_output"
                ),
                agent=agent_key,
            )
        )

    signals: list[MatchSignal] = []
    for signal_index, item in enumerate(_sequence(raw.get("signals"), f"{location}.signals")):
        signal_location = f"{location}.signals[{signal_index}]"
        signal = _mapping(item, signal_location)
        signals.append(
            MatchSignal(
                label=_text(signal.get("label"), f"{signal_location}.label"),
                keywords=_text_tuple(signal.get("keywords"), f"{signal_location}.keywords"),
                weight=_integer(signal.get("weight"), f"{signal_location}.weight", minimum=1),
            )
        )

    sop = _mapping(raw.get("sop"), f"{location}.sop")
    entry = _text(sop.get("entry"), f"{location}.sop.entry")
    stages: list[SOPStage] = []
    stage_ids: set[str] = set()
    covered_agents: set[str] = set()
    for stage_index, item in enumerate(_sequence(sop.get("stages"), f"{location}.sop.stages")):
        stage_location = f"{location}.sop.stages[{stage_index}]"
        stage = _mapping(item, stage_location)
        stage_id = _text(stage.get("id"), f"{stage_location}.id")
        if stage_id in stage_ids:
            raise ValueError(f"{stage_location}.id duplicates {stage_id!r}")
        stage_agents = _text_tuple(stage.get("agents"), f"{stage_location}.agents")
        unknown_agents = set(stage_agents) - agents_raw.keys()
        if unknown_agents:
            raise ValueError(f"{stage_location}.agents contains unknown roles: {sorted(unknown_agents)}")
        dependencies = _text_tuple(
            stage.get("requires_handoff", []),
            f"{stage_location}.requires_handoff",
            allow_empty=True,
        )
        unknown_dependencies = set(dependencies) - stage_ids
        if unknown_dependencies:
            raise ValueError(
                f"{stage_location}.requires_handoff must reference earlier stages: "
                f"{sorted(unknown_dependencies)}"
            )
        review_gate = stage.get("review_gate", False)
        if not isinstance(review_gate, bool):
            raise ValueError(f"{stage_location}.review_gate must be a boolean")
        stages.append(SOPStage(stage_id, stage_agents, dependencies, review_gate))
        stage_ids.add(stage_id)
        covered_agents.update(stage_agents)

    if entry not in stage_ids:
        raise ValueError(f"{location}.sop.entry references unknown stage {entry!r}")
    if set(agents_raw) != covered_agents:
        missing = sorted(set(agents_raw) - covered_agents)
        raise ValueError(f"{location}.sop.stages does not activate roles: {missing}")

    return TeamPreset(
        id=preset_id,
        version=_integer(raw.get("version"), f"{location}.version", minimum=1),
        name=_text(raw.get("name"), f"{location}.name"),
        category=_text(raw.get("category"), f"{location}.category"),
        summary=_text(raw.get("summary"), f"{location}.summary"),
        best_for=_text(raw.get("best_for"), f"{location}.best_for"),
        coordination_pattern=_text(
            raw.get("coordination_pattern"), f"{location}.coordination_pattern"
        ),
        default_workspace_policy=_text(
            raw.get("default_workspace_policy"), f"{location}.default_workspace_policy"
        ),
        industries=_text_tuple(raw.get("industries"), f"{location}.industries"),
        pace_tags=_text_tuple(raw.get("pace_tags"), f"{location}.pace_tags"),
        risk_tags=_text_tuple(raw.get("risk_tags"), f"{location}.risk_tags"),
        sources=tuple(sources[key] for key in source_keys),
        signals=tuple(signals),
        roles=tuple(roles),
        tasks=tuple(tasks),
        sop_entry=entry,
        sop_stages=tuple(stages),
    )


def load_catalog(path: Path = CATALOG_PATH) -> tuple[TeamPreset, ...]:
    """Safely load and validate a complete preset catalog."""
    try:
        raw_document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to load preset catalog {path}: {exc}") from exc
    document = _mapping(raw_document, "catalog")
    if document.get("schema_version") != 1:
        raise ValueError("catalog.schema_version must be 1")
    sources = _parse_sources(document.get("sources"))
    presets = tuple(
        _parse_preset(item, index, sources)
        for index, item in enumerate(_sequence(document.get("presets"), "presets"))
    )
    keys = [(preset.id, preset.version) for preset in presets]
    if len(keys) != len(set(keys)):
        raise ValueError("catalog contains duplicate preset id/version entries")
    if not presets:
        raise ValueError("catalog must contain at least one preset")
    return presets


CATALOG = load_catalog()
SOURCES = {source.key: source for preset in CATALOG for source in preset.sources}
_PRESETS_BY_KEY = {(preset.id, preset.version): preset for preset in CATALOG}


def get_preset(preset_id: str, version: int | None = None) -> TeamPreset | None:
    if version is not None:
        return _PRESETS_BY_KEY.get((preset_id, version))
    matches = [preset for preset in CATALOG if preset.id == preset_id]
    return max(matches, key=lambda item: item.version, default=None)


def list_presets(category: str | None = None) -> tuple[TeamPreset, ...]:
    if category in (None, "all"):
        return CATALOG
    return tuple(preset for preset in CATALOG if preset.category == category)


def budget_to_dict(budget: RoleBudget) -> dict[str, int | float]:
    return {
        "max_total_tokens": budget.max_total_tokens,
        "max_wall_time_seconds": budget.max_wall_time_seconds,
        "max_active_runtime_seconds": budget.max_active_runtime_seconds,
        "max_llm_calls": budget.max_llm_calls,
        "max_cost": budget.max_cost,
        "max_parallel_llm_calls": budget.max_parallel_llm_calls,
    }


def role_to_dict(role: RolePreset) -> dict[str, Any]:
    return {
        "key": role.key,
        "role": role.role,
        "goal": role.goal,
        "backstory": role.backstory,
        "responsibility": role.backstory,
        "skills": list(role.skills),
        "budget": budget_to_dict(role.budget),
        "optional": role.optional,
    }


def task_to_dict(task: TaskPreset) -> dict[str, str]:
    return {
        "key": task.key,
        "description": task.description,
        "expected_output": task.expected_output,
        "agent": task.agent,
    }


def source_to_dict(source: SourceReference) -> dict[str, Any]:
    return {
        "key": source.key,
        "repository": source.repository,
        "url": source.url,
        "license": source.license,
        "reviewed_stars": source.reviewed_stars,
        "reviewed_at": source.reviewed_at,
        "integration": source.integration,
        "runtime_dependency": source.integration == "runtime",
    }


def stage_to_dict(stage: SOPStage) -> dict[str, Any]:
    return {
        "id": stage.id,
        "agents": list(stage.agents),
        "requires_handoff": list(stage.requires_handoff),
        "review_gate": stage.review_gate,
    }


def aggregate_budget(roles: tuple[RolePreset, ...] | list[RolePreset]) -> dict[str, int | float]:
    return {
        "max_total_tokens": sum(role.budget.max_total_tokens for role in roles),
        "max_llm_calls": sum(role.budget.max_llm_calls for role in roles),
        "max_cost": round(sum(role.budget.max_cost for role in roles), 6),
    }


def preset_to_dict(preset: TeamPreset, *, include_blueprint: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": preset.id,
        "version": preset.version,
        "name": preset.name,
        "category": preset.category,
        "summary": preset.summary,
        "best_for": preset.best_for,
        "coordination_pattern": preset.coordination_pattern,
        "roles": [role_to_dict(role) for role in preset.roles],
        "sources": [source_to_dict(source) for source in preset.sources],
        "starter_budget": aggregate_budget(preset.roles),
        "default_workspace_policy": preset.default_workspace_policy,
        "requires_third_party_setup": False,
    }
    if include_blueprint:
        result["tasks"] = [task_to_dict(task) for task in preset.tasks]
        result["sop"] = {
            "entry": preset.sop_entry,
            "stages": [stage_to_dict(stage) for stage in preset.sop_stages],
        }
    return result
