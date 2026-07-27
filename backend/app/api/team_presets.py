"""Beginner-first Agent Team catalog, recommendation and one-click creation APIs."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway import resolve_gateway_config
from app.api.tasks import BudgetSpec, _enqueue_or_warn
from app.api.work_containers import (
    CreateWorkSessionRequest,
    _container_dict,
    _container_or_404,
    _create_work_session_records,
)
from app.collaboration.autonomous import eligible_autonomous_runs, is_autonomous
from app.core.db import get_db
from app.core.enums import RunStatus, Strategy, TaskTemplate, WorkspacePolicy
from app.core.models import TaskRun, WorkContainer, WorkSession, utcnow
from app.execution_engines import DEFAULT_ENGINE_ID, engine_preflight, get_engine
from app.policy.workspace_access import (
    FolderAccess,
    normalize_project_dir,
    validate_workspace_access,
)
from app.team_presets import (
    CATALOG,
    build_activation_plan,
    get_preset,
    list_presets,
    preset_to_dict,
    recommend_presets_ai_first,
)
from app.team_presets.catalog import RolePreset, budget_to_dict

router = APIRouter(tags=["agent-team-presets"])
DbSession = Annotated[Session, Depends(get_db)]
RequiredIdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)]

MAX_ROLE_TOKENS = 200_000
MAX_ROLE_WALL_SECONDS = 7_200
MAX_ROLE_ACTIVE_SECONDS = 3_600
MAX_ROLE_CALLS = 100
MAX_ROLE_COST = 50.0
MAX_ROLE_PARALLEL_CALLS = 8


class RecommendPresetRequest(BaseModel):
    model_config = {"extra": "forbid"}

    goal: str = Field(min_length=3, max_length=10_000)
    industry: str | None = Field(default=None, max_length=100)
    pace: Literal["steady", "fast"] = "steady"
    risk: Literal["steady", "balanced", "creative"] = "balanced"

    @field_validator("goal")
    @classmethod
    def reject_blank_goal(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("goal must contain at least 3 meaningful characters")
        return value


class RoleBudgetOverride(BaseModel):
    model_config = {"extra": "forbid"}

    max_total_tokens: int | None = Field(default=None, ge=1, le=MAX_ROLE_TOKENS)
    max_wall_time_seconds: int | None = Field(default=None, ge=1, le=MAX_ROLE_WALL_SECONDS)
    max_active_runtime_seconds: int | None = Field(default=None, ge=1, le=MAX_ROLE_ACTIVE_SECONDS)
    max_llm_calls: int | None = Field(default=None, ge=1, le=MAX_ROLE_CALLS)
    max_cost: float | None = Field(default=None, gt=0, le=MAX_ROLE_COST)
    max_parallel_llm_calls: int | None = Field(default=None, ge=1, le=MAX_ROLE_PARALLEL_CALLS)


class RoleOverride(BaseModel):
    model_config = {"extra": "forbid"}

    key: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    role: str | None = Field(default=None, min_length=1, max_length=120)
    goal: str | None = Field(default=None, min_length=1, max_length=10_000)
    budget: RoleBudgetOverride | None = None
    execution_engine: str | None = Field(default=None, min_length=1, max_length=50)


class CreateTeamFromPresetRequest(BaseModel):
    model_config = {"extra": "forbid"}

    preset_id: str = Field(min_length=1, max_length=100)
    preset_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    project_goal: str = Field(min_length=3, max_length=10_000)
    acceptance_criteria: str | None = Field(default=None, max_length=20_000)
    shared_context: str = Field(default="", max_length=30_000)
    base_workdir: str = Field(min_length=1, max_length=500)
    default_workspace_policy: WorkspacePolicy | None = None
    role_overrides: list[RoleOverride] = Field(default_factory=list, max_length=8)
    start_immediately: bool = True
    default_execution_engine: str = Field(default=DEFAULT_ENGINE_ID, min_length=1, max_length=50)
    team_mode: Literal["guided", "autonomous"] = "guided"
    budget_mode: Literal["bounded", "max"] = "bounded"
    folder_access: FolderAccess = "isolated"
    project_dir: str | None = Field(default=None, max_length=500)
    full_access_acknowledged: bool = False
    recommendation_source: Literal["ai", "local_fallback", "manual"] | None = None
    project_upload_id: uuid.UUID | None = None

    @field_validator("name", "project_goal")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("base_workdir")
    @classmethod
    def absolute_workdir(cls, value: str) -> str:
        value = value.strip()
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("must be an absolute normalized workspace path")
        return str(path)

    @field_validator("project_dir")
    @classmethod
    def canonical_project_dir(cls, value: str | None) -> str | None:
        return normalize_project_dir(value)

    @model_validator(mode="after")
    def unique_role_overrides(self):
        keys = [override.key for override in self.role_overrides]
        if len(keys) != len(set(keys)):
            raise ValueError("role_overrides must contain unique keys")
        validate_workspace_access(self.folder_access, self.project_dir)
        if self.folder_access == "full_access" and not self.full_access_acknowledged:
            raise ValueError("full_access_acknowledged is required for full_access")
        if self.folder_access == "isolated" and self.full_access_acknowledged:
            raise ValueError("full_access_acknowledged must be false for isolated access")
        if self.project_upload_id is not None and (
            self.folder_access != "isolated" or self.project_dir is not None
        ):
            raise ValueError("project_upload_id is only valid for isolated access without project_dir")
        return self


def _applied_role(role: RolePreset, override: RoleOverride | None, default_execution_engine: str) -> dict:
    budget = budget_to_dict(role.budget)
    if override and override.budget:
        budget.update(override.budget.model_dump(exclude_none=True))
    return {
        "key": role.key,
        "role": override.role.strip() if override and override.role else role.role,
        "goal": override.goal.strip() if override and override.goal else role.goal,
        "backstory": role.backstory,
        "skills": list(role.skills),
        "budget": budget,
        "execution_engine": (
            override.execution_engine if override and override.execution_engine else default_execution_engine
        ),
    }


def _filter_activation_plan(plan: dict, enabled_role_keys: set[str]) -> dict:
    waves = [
        {"stage": wave["stage"], "roles": [key for key in wave["roles"] if key in enabled_role_keys]}
        for wave in plan["activation_waves"]
    ]
    waves = [wave for wave in waves if wave["roles"]]
    active_stages = {wave["stage"] for wave in waves}
    return {
        **plan,
        "activation_waves": waves,
        "required_handoffs": [
            handoff
            for handoff in plan["required_handoffs"]
            if handoff["from_stage"] in active_stages and handoff["to_stage"] in active_stages
        ],
        "review_gates": [gate for gate in plan["review_gates"] if gate in active_stages],
    }


def _dispatch_runs(
    session: Session,
    container: WorkContainer,
    ordered_runs: list[TaskRun],
) -> dict:
    snapshot = dict(container.preset_snapshot or {})
    dispatch = dict(snapshot.get("dispatch") or {})
    dispatched = set(dispatch.get("dispatched_run_ids") or [])
    accepted: list[str] = []
    skipped: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for run in ordered_runs:
        run_id = str(run.id)
        if run_id in dispatched:
            skipped.append({"run_id": run_id, "reason": "already_dispatched"})
            continue
        if run.status != RunStatus.PENDING.value:
            skipped.append({"run_id": run_id, "reason": f"status_{run.status.lower()}"})
            continue
        engine_id = str((run.model_config or {}).get("execution_engine") or DEFAULT_ENGINE_ID)
        engine_status = engine_preflight(engine_id)
        if not engine_status.runtime_available:
            warnings.append({"run_id": run_id, "message": engine_status.reason})
            continue
        warning = _enqueue_or_warn(run.id)
        if warning:
            warnings.append({"run_id": run_id, "message": warning})
            continue
        dispatched.add(run_id)
        accepted.append(run_id)

    dispatch["dispatched_run_ids"] = sorted(dispatched)
    dispatch["last_requested_at"] = utcnow().isoformat()
    snapshot["dispatch"] = dispatch
    container.preset_snapshot = snapshot
    container.updated_at = utcnow()
    session.commit()
    return {"accepted": accepted, "skipped": skipped, "warnings": warnings}


def _ordered_runs(container: WorkContainer) -> list[TaskRun]:
    sessions_by_id = {str(item.id): item for item in container.sessions}
    snapshot = container.preset_snapshot or {}
    applied_by_key = {item["key"]: item for item in snapshot.get("applied_roles", [])}
    ordered: list[TaskRun] = []
    seen: set[uuid.UUID] = set()
    for wave in (snapshot.get("activation_plan") or {}).get("activation_waves", []):
        for key in wave.get("roles", []):
            applied = applied_by_key.get(key) or {}
            session_id = applied.get("session_id")
            item = sessions_by_id.get(session_id) if isinstance(session_id, str) else None
            if item and item.current_run and item.current_run.id not in seen:
                ordered.append(item.current_run)
                seen.add(item.current_run.id)
    for item in container.sessions:
        if item.current_run and item.current_run.id not in seen:
            ordered.append(item.current_run)
            seen.add(item.current_run.id)
    return ordered


def _runnable_runs(container: WorkContainer) -> list[TaskRun]:
    return eligible_autonomous_runs(container) if is_autonomous(container) else _ordered_runs(container)


@router.get("/work-container-presets")
def get_work_container_presets(
    category: Annotated[str | None, Query(max_length=50)] = None,
) -> dict:
    categories = tuple(dict.fromkeys(preset.category for preset in CATALOG))
    if category not in (None, "all") and category not in categories:
        raise HTTPException(status_code=422, detail="unknown preset category")
    gateway = resolve_gateway_config()
    return {
        "presets": [preset_to_dict(preset) for preset in list_presets(category)],
        "categories": list(categories),
        "runtime": {
            "graph": "LangGraph",
            "configuration_required": False,
            "recommendation_remote_calls": gateway.configured and gateway.recommendation_enabled,
            "ai_preferred": True,
            "local_fallback": True,
            "gateway_type": gateway.kind,
        },
    }


@router.post("/work-container-presets/recommend")
def recommend_work_container_presets(body: RecommendPresetRequest) -> dict:
    outcome = recommend_presets_ai_first(
        body.goal,
        industry=body.industry,
        pace=body.pace,
        risk=body.risk,
    )
    return {
        "recommendations": [item.to_dict() for item in outcome.recommendations],
        **outcome.public_metadata(),
    }


@router.post("/work-containers/from-preset", status_code=201)
def create_team_from_preset(
    body: CreateTeamFromPresetRequest,
    idempotency_key: RequiredIdempotencyKey,
    session: DbSession,
) -> dict:
    existing = session.execute(
        select(WorkContainer).where(WorkContainer.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        container = _container_or_404(session, existing.id)
        return {
            "container": _container_dict(container),
            "created": False,
            "dispatch": {"accepted": [], "skipped": [], "warnings": []},
        }

    preset = get_preset(body.preset_id, body.preset_version)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset version not found")
    overrides = {override.key: override for override in body.role_overrides}
    unknown_roles = set(overrides) - {role.key for role in preset.roles}
    if unknown_roles:
        raise HTTPException(status_code=422, detail=f"unknown preset roles: {sorted(unknown_roles)}")
    requested_engines = {body.default_execution_engine}
    requested_engines.update(
        override.execution_engine for override in body.role_overrides if override.execution_engine
    )
    unknown_engines = sorted(engine_id for engine_id in requested_engines if get_engine(engine_id) is None)
    if unknown_engines:
        raise HTTPException(status_code=422, detail=f"unknown execution engines: {unknown_engines}")

    if body.folder_access == "full_access":
        unsupported_engines = sorted(
            engine_id
            for engine_id in requested_engines
            if (engine := get_engine(engine_id)) is not None and engine.transport != "server"
        )
        if unsupported_engines:
            raise HTTPException(
                status_code=422,
                detail=(
                    "full_access Agent Teams require the OpenHands server engine; "
                    f"CLI engines cannot access the selected host folder: {unsupported_engines}"
                ),
            )

    applied_roles = []
    for role in preset.roles:
        override = overrides.get(role.key)
        enabled = override.enabled if override is not None else not role.optional
        if enabled:
            applied_roles.append(_applied_role(role, override, body.default_execution_engine))
    if not 2 <= len(applied_roles) <= 8:
        raise HTTPException(status_code=422, detail="a team must enable 2 to 8 roles")
    if body.start_immediately:
        preflights = {
            applied["execution_engine"]: engine_preflight(applied["execution_engine"])
            for applied in applied_roles
        }
        unavailable = [item for item in preflights.values() if not item.runtime_available]
        if unavailable:
            facts = "; ".join(f"{item.engine_id}: {item.reason}" for item in unavailable)
            raise HTTPException(status_code=409, detail=f"execution engine unavailable: {facts}")

    policy = body.default_workspace_policy or WorkspacePolicy(preset.default_workspace_policy)
    if body.folder_access == "full_access" and policy != WorkspacePolicy.WORKTREE:
        raise HTTPException(
            status_code=422,
            detail="full_access Agent Teams require default_workspace_policy=worktree",
        )
    container = WorkContainer(
        name=body.name,
        project_goal=body.project_goal,
        shared_context=body.shared_context,
        base_workdir=body.base_workdir,
        default_workspace_policy=policy.value,
        preset_id=preset.id,
        preset_version=preset.version,
        idempotency_key=idempotency_key,
    )
    session.add(container)
    session.flush()

    task_by_agent = {task.agent: task for task in preset.tasks}
    created_by_key: dict[str, tuple[WorkSession, TaskRun]] = {}
    for applied in applied_roles:
        task = task_by_agent[applied["key"]]
        private_context = (
            f"团队预设：{preset.name} v{preset.version}\n"
            f"角色背景：{applied['backstory']}\n"
            f"建议 Skills：{'、'.join(applied['skills'])}\n"
            "Skills 仅用于工作方法提示，不会授予额外工具、权限或跨 Session 访问。\n"
            f"预期产出：{task.expected_output}"
        )
        item, run = _create_work_session_records(
            session,
            container,
            CreateWorkSessionRequest(
                role=applied["role"],
                goal=applied["goal"],
                private_context=private_context,
                acceptance_criteria=(
                    f"{body.acceptance_criteria.strip()}\n\n角色预期产出：{task.expected_output}"
                    if body.acceptance_criteria and body.acceptance_criteria.strip()
                    else task.expected_output
                ),
                template=TaskTemplate.SMALL_FEATURE,
                require_approval=True,
                strategy=Strategy.DYNAMIC,
                budget=BudgetSpec(**applied["budget"]),
                worktree_enabled=policy == WorkspacePolicy.WORKTREE,
                execution_engine=applied["execution_engine"],
            ),
            idempotency_key=applied["key"],
            model_config_overrides={
                "team_mode": body.team_mode,
                "budget_mode": body.budget_mode,
                "folder_access": body.folder_access,
                **({"project_dir": body.project_dir} if body.project_dir else {}),
                **({"project_upload_id": str(body.project_upload_id)} if body.project_upload_id else {}),
            },
        )
        applied["session_id"] = str(item.id)
        applied["run_id"] = str(run.id)
        created_by_key[applied["key"]] = (item, run)

    enabled_keys = set(created_by_key)
    activation_plan = _filter_activation_plan(build_activation_plan(preset), enabled_keys)
    container.preset_snapshot = {
        "preset": preset_to_dict(preset),
        "applied_roles": applied_roles,
        "activation_plan": activation_plan,
        "workspace_access": {
            "folder_access": body.folder_access,
            "project_dir": body.project_dir,
            **({"project_upload_id": str(body.project_upload_id)} if body.project_upload_id else {}),
            "worktree_required": body.folder_access == "full_access",
        },
        "recommendation_source": body.recommendation_source,
        "team_mode": body.team_mode,
        "budget_mode": body.budget_mode,
        "setup_intent": {
            "acceptance_criteria": body.acceptance_criteria,
        },
        "dispatch": {"dispatched_run_ids": []},
    }
    container.updated_at = utcnow()
    session.commit()

    dispatch: dict[str, list] = {"accepted": [], "skipped": [], "warnings": []}
    if body.start_immediately:
        container = _container_or_404(session, container.id)
        dispatch = _dispatch_runs(session, container, _runnable_runs(container))
        container = _container_or_404(session, container.id)
    else:
        container = _container_or_404(session, container.id)

    return {"container": _container_dict(container), "created": True, "dispatch": dispatch}


@router.post("/work-containers/{container_id}/start")
def start_preset_team(container_id: uuid.UUID, session: DbSession) -> dict:
    container = _container_or_404(session, container_id)
    if not container.preset_id or not container.preset_snapshot:
        raise HTTPException(status_code=409, detail="work container was not created from a preset")
    return _dispatch_runs(session, container, _runnable_runs(container))
