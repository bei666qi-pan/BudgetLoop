import { roleBoundsValid, roleBudgetValid, roleDrafts, roleOverride } from "@/lib/team-presets";
import type {
  CreateTeamFromPresetRequest,
  EditableTaskDraft,
  TaskSetupDraft,
  TeamRoleDraft,
  WorkspaceAccessSelection,
} from "@/lib/types";

export const DEFAULT_WORKSPACE_ACCESS: WorkspaceAccessSelection = {
  folder_access: "isolated",
  project_dir: "",
  full_access_acknowledged: false,
  project_upload_id: null,
};

export function editableTaskDraft(
  draft: TaskSetupDraft,
): EditableTaskDraft {
  return {
    schema_version: 1,
    ...draft.intent,
    preset_id: draft.team.preset.id,
    preset_version: draft.team.preset.version,
  };
}

export function rolesForTaskDraft(draft: TaskSetupDraft): TeamRoleDraft[] {
  return roleDrafts(draft.team.preset).map((role) => ({
    ...role,
    execution_engine: draft.execution.default_engine,
  }));
}

export function workspaceAccessError(
  access: WorkspaceAccessSelection,
): string | null {
  if (access.folder_access === "isolated") return null;
  const projectDir = access.project_dir.trim();
  if (!projectDir) return "请选择 Agent 可以直接读写的项目文件夹。";
  if (!projectDir.startsWith("/") || projectDir.includes("/../")) {
    return "项目文件夹需要使用规范的绝对路径。";
  }
  if (!access.full_access_acknowledged) {
    return "请确认 Agent 将直接修改该文件夹（包括 .git）。";
  }
  return null;
}

export function teamDraftError(
  draft: TaskSetupDraft,
  roles: TeamRoleDraft[],
  access: WorkspaceAccessSelection,
): string | null {
  if (!draft.intent.title.trim() || !draft.intent.goal.trim()) {
    return "请补全任务名称和目标。";
  }
  if (!draft.intent.acceptance_criteria.trim()) {
    return "请保留至少一条可检查的验收条件。";
  }
  if (!roleBoundsValid(roles)) return "请启用 2–8 个团队角色。";
  if (roles.some((role) => role.enabled && (!role.role.trim() || !role.goal.trim()))) {
    return "已启用角色需要名称和明确目标。";
  }
  if (roles.some((role) => role.enabled && !roleBudgetValid(role.budget))) {
    return "角色预算超出安全范围；单个角色 Token 上限为 200,000。";
  }
  const available = new Set(
    draft.execution.engines
      .filter((engine) => engine.runtime_available)
      .map((engine) => engine.id),
  );
  if (roles.some((role) => role.enabled && !available.has(role.execution_engine))) {
    return "所选执行引擎尚未就绪。可以在 Agent Team 高级配置中更换。";
  }
  return workspaceAccessError(access);
}

export function createTeamRequestFromDraft(
  draft: TaskSetupDraft,
  roles: TeamRoleDraft[],
  access: WorkspaceAccessSelection,
): CreateTeamFromPresetRequest {
  return {
    preset_id: draft.team.preset.id,
    preset_version: draft.team.preset.version,
    name: draft.intent.title.trim(),
    project_goal: draft.intent.goal.trim(),
    acceptance_criteria: draft.intent.acceptance_criteria.trim(),
    shared_context: draft.intent.shared_context.trim(),
    base_workdir: draft.execution.base_workdir,
    default_workspace_policy:
      access.folder_access === "full_access"
        ? "worktree"
        : draft.execution.default_workspace_policy,
    role_overrides: roles.map(roleOverride),
    start_immediately: true,
    default_execution_engine: draft.execution.default_engine,
    folder_access: access.folder_access,
    project_dir: access.project_dir.trim() || null,
    full_access_acknowledged: access.full_access_acknowledged,
    recommendation_source: draft.provenance.source,
    project_upload_id: access.project_upload_id,
  };
}
