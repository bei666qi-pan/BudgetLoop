// BudgetLoop API 类型定义，严格对齐 docs/api-contract.md 与 backend/app/core/models.py。

export type Strategy = "none" | "fixed" | "dynamic";

export type RunStatus =
  | "PENDING"
  | "PLANNING"
  | "EXECUTING"
  | "OBSERVING"
  | "EVALUATING"
  | "REPLANNING"
  | "WAITING_APPROVAL"
  | "PAUSED"
  | "COMPLETED"
  | "PARTIAL_COMPLETED"
  | "FAILED"
  | "BUDGET_EXHAUSTED"
  | "CANCELLED";

export const TERMINAL_STATUSES: RunStatus[] = [
  "COMPLETED",
  "PARTIAL_COMPLETED",
  "FAILED",
  "BUDGET_EXHAUSTED",
  "CANCELLED",
];

export function isTerminal(status: RunStatus | string): boolean {
  return (TERMINAL_STATUSES as string[]).includes(status);
}

export type PressureMode = "NORMAL" | "CONSERVATIVE" | "CRITICAL";

export type TaskTemplate =
  | "fix_bug"
  | "locate_issue"
  | "add_tests"
  | "small_feature"
  | "fix_build";

export type FolderAccess = "isolated" | "full_access";

// ---- 创建任务 ----

export interface BudgetConfig {
  max_total_tokens: number;
  max_wall_time_seconds: number;
  max_active_runtime_seconds: number;
  max_llm_calls: number;
  max_cost: number;
  max_parallel_llm_calls: number;
}

export interface CreateTaskRequest {
  name: string;
  description: string;
  workdir: string;
  acceptance_criteria?: string | null;
  template: TaskTemplate;
  require_approval: boolean;
  strategy: Strategy;
  budget: BudgetConfig;
  project_dir?: string | null;
  folder_access?: FolderAccess;
}

export interface CreateTaskResponse {
  task_id: string;
  run_id: string;
}

// ---- 任务列表 ----

export interface LatestRunSummary {
  id: string;
  status: RunStatus;
  iteration: number;
  used_tokens: number;
  used_cost: number | null;
}

export interface TaskListItem {
  id: string;
  name: string;
  template?: TaskTemplate | string;
  created_at?: string;
  latest_run?: LatestRunSummary | null;
}

// ---- Run 聚合详情 ----

// run.model_config 是后端持久化的 JSONB 配置（含 folder_access / project_dir 等），键集合会随版本扩展。
export interface RunModelConfig {
  folder_access?: FolderAccess | string | null;
  project_dir?: string | null;
  [key: string]: unknown;
}

export interface RunInfo {
  id: string;
  task_id: string;
  attempt_no: number;
  strategy: Strategy;
  status: RunStatus;
  current_phase: string | null;
  pressure_mode: PressureMode;
  iteration: number;
  started_at: string | null;
  finished_at: string | null;
  deadline_at: string | null;
  active_runtime_ms: number;
  error: string | null;
  model_config?: RunModelConfig | null;
  work_container_id?: string | null;
  work_session_id?: string | null;
  work_session_role?: string | null;
}

export interface TaskInfo {
  id: string;
  name: string;
  description: string;
  workdir: string;
  acceptance_criteria: string | null;
  template: TaskTemplate | string;
  require_approval: boolean;
}

export interface BudgetState {
  max_total_tokens: number;
  max_wall_time_seconds: number;
  max_active_runtime_seconds: number;
  max_llm_calls: number;
  max_cost: number;
  max_parallel_llm_calls: number;
  used_tokens: number;
  used_cost: number;
  used_calls: number;
  reserved_tokens: number;
  reserved_cost: number;
  reserved_calls: number;
  remaining_tokens?: number | null;
  remaining_calls?: number | null;
  remaining_cost?: number | null;
  projected_tokens?: number | null;
  unlimited?: boolean;
}

export interface RunDetail {
  run: RunInfo;
  task: TaskInfo;
  budget: BudgetState | null;
}

// ---- 观测数据 ----

export interface LlmCall {
  id: string;
  run_id: string;
  call_id: string;
  iteration: number;
  phase: string | null;
  call_kind: "agent" | "condenser" | "other" | string;
  agent_name?: string;
  model: string | null;
  provider?: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  ttft_ms?: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  reasoning_tokens?: number | null;
  cache_read_tokens?: number | null;
  cache_write_tokens?: number | null;
  total_tokens: number | null;
  token_source?: string;
  estimated_cost: number | null; // null = 价格未配置
  finish_reason: string | null;
  request_status: "success" | "failed" | "rejected_budget" | string;
  retry_count: number;
  input_summary: string | null;
  output_summary: string | null;
  decision?: string | null;
  effective?: boolean | null;
  progress_score: number | null;
  inefficiency_reason: string | null;
}

export interface PhaseBudget {
  id?: string;
  phase: string;
  budget_tokens: number;
  budget_seconds?: number;
  budget_calls?: number;
  budget_cost?: number;
  used_tokens: number;
  used_ms?: number;
  used_calls?: number;
  used_cost?: number;
  status: "pending" | "active" | "done" | "capped" | string;
}

export interface Reallocation {
  id?: string;
  from_phase?: string | null;
  to_phase?: string | null;
  tokens?: number | null;
  reason?: string | null;
  created_at?: string;
  [key: string]: unknown;
}

export interface BudgetDetail {
  budget: BudgetState;
  phases: PhaseBudget[];
  reallocations: Reallocation[];
}

export interface ExecutionEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface EventsResponse {
  events: ExecutionEvent[];
}

// ---- 审批 ----
// 契约中没有"列出审批"的端点，审批信息由 approval_requested 事件 payload 携带。

export interface ApprovalPayload {
  approval_id?: string;
  id?: string;
  action_type?: string;
  description?: string;
  reason?: string;
  risk?: string;
  est_tokens?: number;
  est_seconds?: number;
  [key: string]: unknown;
}

export type ApprovalAction = "approve" | "reject" | "modify";

// ---- 最终报告 ----

export interface FinalReport {
  run_id?: string;
  status: RunStatus | string;
  acceptance_result?: unknown;
  files_changed?: unknown;
  diff_summary?: string | null;
  totals?: Record<string, unknown>;
  strategy_switches?: unknown;
  open_issues?: unknown;
  suggestions?: unknown;
  report_md?: string | null;
  created_at?: string;
}

// ---- Agent Team / 工作容器 ----

export type ContainerLifecycle = "active" | "paused" | "completed" | "archived";
export type WorkspacePolicy = "isolated" | "worktree";
export type MessageKind = "message" | "handoff";
export type DeliveryState = "queued" | "delivered" | "recorded";

// Agent Team 消息类型（团队频道/观测台）
export type TeamMessageType = "message" | "handoff" | "progress_update" | "system_fact";
export type TeamDeliveryState = "queued" | "injected" | "acknowledged" | "failed";

/** 团队频道消息——聚合所有 Session 的消息流 */
export interface TeamChatMessage {
  id: string;
  idempotency_key?: string | null;
  entry_type: TeamMessageType | "agent_output";
  author_type: string;
  sender_session_id: string | null;
  sender_role: string;
  recipient_session_id: string | null;
  recipient_role: string | null;
  content: string;
  delivery_state: TeamDeliveryState | string;
  metadata: Record<string, unknown>;
  created_at: string;
  delivered_at?: string | null;
}

export interface WorkContainerCounts {
  sessions: number;
  running: number;
  waiting: number;
  attention: number;
}

export interface WorkSessionSummary {
  id: string;
  container_id: string;
  role: string;
  session_kind: "agent" | "judge" | string;
  system_managed: boolean;
  goal: string;
  status: RunStatus | string;
  task_id: string;
  current_run_id: string;
  conversation_id: string | null;
  iteration: number;
  worktree_enabled: boolean;
  worktree_branch: string | null;
  worktree_path: string | null;
  workspace_status: "PENDING" | "PROVISIONING" | "READY" | "FAILED" | string;
  workspace_error: string | null;
  run_started_at?: string | null;
  // Enriched budget fields from team obsertory (optional, present when container detail is enriched)
  budget_used_tokens?: number | null;
  budget_max_tokens?: number | null;
  budget_used_cost?: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkContainer {
  id: string;
  name: string;
  project_goal: string;
  shared_context?: string;
  lifecycle_state: ContainerLifecycle;
  base_workdir: string;
  default_workspace_policy: WorkspacePolicy;
  preset_id?: string | null;
  preset_version?: number | null;
  preset_snapshot?: TeamPresetSnapshot | null;
  counts: WorkContainerCounts;
  sessions: WorkSessionSummary[];
  judge?: JudgeState;
  /** 团队观测台 enriched 字段 — GET /api/containers 返回 */
  team_status?: TeamStatus | null;
  alert_count?: number | null;
  active_session_count?: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkSessionDetail extends WorkSessionSummary {
  private_context: string;
  budget: BudgetState | null;
}

export interface SessionTranscriptEntry {
  id: string;
  entry_type: "message" | "handoff" | "agent_output";
  author_type: "operator" | "session" | "agent" | string;
  sender_session_id: string | null;
  sender_role: string;
  recipient_session_id: string | null;
  recipient_role: string | null;
  content: string;
  delivery_state: DeliveryState | string;
  metadata: Record<string, unknown>;
  created_at: string;
  delivered_at: string | null;
}

export interface WorkSessionDetailResponse {
  session: WorkSessionDetail;
  transcript: SessionTranscriptEntry[];
}

export interface CreateWorkContainerRequest {
  name: string;
  project_goal: string;
  shared_context: string;
  base_workdir: string;
  default_workspace_policy: WorkspacePolicy;
}

export interface CreateWorkSessionRequest {
  role: string;
  goal: string;
  private_context: string;
  acceptance_criteria?: string | null;
  template: TaskTemplate;
  require_approval: boolean;
  strategy: Strategy;
  budget: BudgetConfig;
  worktree_enabled: boolean;
}

// ---- Agent Team presets ----

export interface TeamPresetSource {
  key: string;
  repository: string;
  url: string;
  license: string;
  reviewed_stars: number;
  reviewed_at: string;
  integration: "runtime" | "pattern";
  runtime_dependency: boolean;
}

export interface TeamPresetRole {
  key: string;
  role: string;
  goal: string;
  backstory: string;
  responsibility: string;
  skills: string[];
  optional: boolean;
  budget: BudgetConfig;
}

export interface TeamPresetTask {
  key: string;
  description: string;
  expected_output: string;
  agent: string;
}

export interface TeamPresetStage {
  id: string;
  agents: string[];
  requires_handoff: string[];
  review_gate: boolean;
}

export interface TeamPreset {
  id: string;
  version: number;
  name: string;
  category: string;
  summary: string;
  best_for: string;
  coordination_pattern: string;
  roles: TeamPresetRole[];
  sources: TeamPresetSource[];
  starter_budget: Pick<BudgetConfig, "max_total_tokens" | "max_llm_calls" | "max_cost">;
  default_workspace_policy: WorkspacePolicy;
  requires_third_party_setup: boolean;
  tasks: TeamPresetTask[];
  sop: { entry: string; stages: TeamPresetStage[] };
}

export interface TeamPresetCatalogResponse {
  presets: TeamPreset[];
  categories: string[];
  runtime: {
    graph: "LangGraph" | string;
    configuration_required: boolean;
    recommendation_remote_calls: boolean;
    ai_preferred: boolean;
    local_fallback: boolean;
    gateway_type: string;
  };
}

export interface AIGatewayProvenance {
  name: string;
  repository: string;
  repository_url: string;
  release: string;
  revision: string;
  license: string;
  reviewed_stars: number;
  reviewed_at: string;
}

export interface AIGatewayStatus {
  type: string;
  configured: boolean;
  healthy: boolean;
  recommendation_enabled: boolean;
  recommendation_model: string | null;
  default_model: string | null;
  deployment_label: string | null;
  network_label: string | null;
  reasoning_effort: string | null;
  thinking_enabled: boolean;
  thinking_budget_tokens: number | null;
  managed_app_runtime: {
    enabled: boolean;
    credential_source: "budgetloop_scoped_runtime" | string;
    project_env_required: false;
    browser_direct_access: false;
  };
  console_url: string | null;
  protocols: string[];
  routing: string;
  semantic_ai_router: false;
  provenance: AIGatewayProvenance | null;
  reason_code: string | null;
  status_class: string | null;
}

export interface AIGatewaySettings {
  kind: "new-api" | "litellm" | "compatible";
  base_url: string;
  console_url: string;
  recommendation_model: string;
  default_model: string;
  deployment_label: string;
  network_label: string;
  reasoning_effort: "" | "low" | "medium" | "high" | "max";
  thinking_enabled: boolean;
  thinking_budget_tokens: number;
  managed_app_inheritance_enabled: boolean;
  secret_configured: boolean;
  secret_store: "macos_keychain" | "environment" | string;
}

export interface TeamPresetRecommendation {
  preset: TeamPreset;
  confidence: number;
  reason: string;
  matched_signals: string[];
  fallback: boolean;
}

export interface TeamPresetRecommendationResponse {
  recommendations: TeamPresetRecommendation[];
  explanation: string;
  runtime: "langgraph" | "ai-gateway" | string;
  source: "ai" | "local_fallback";
  gateway: {
    type: string;
    model: string | null;
    status_class: string | null;
  };
  fallback_reason: string | null;
}

export interface TeamRoleDraft {
  key: string;
  enabled: boolean;
  role: string;
  goal: string;
  budget: BudgetConfig;
  optional: boolean;
  execution_engine: string;
}

export interface TeamRoleOverride {
  key: string;
  enabled: boolean;
  role?: string;
  goal?: string;
  budget?: Partial<BudgetConfig>;
  execution_engine?: string;
}

export interface CreateTeamFromPresetRequest {
  preset_id: string;
  preset_version: number;
  name: string;
  project_goal: string;
  acceptance_criteria?: string | null;
  shared_context: string;
  base_workdir: string;
  default_workspace_policy: WorkspacePolicy;
  role_overrides: TeamRoleOverride[];
  start_immediately: boolean;
  default_execution_engine: string;
  team_mode?: "guided" | "autonomous";
  budget_mode?: "bounded" | "max";
  folder_access?: FolderAccess;
  project_dir?: string | null;
  full_access_acknowledged?: boolean;
  recommendation_source?: "ai" | "local_fallback" | "manual" | null;
  project_upload_id?: string | null;
}

export interface TeamDispatchResult {
  accepted: string[];
  skipped: Array<{ run_id: string; reason: string }>;
  warnings: Array<{ run_id: string; message: string }>;
}

export interface CreateTeamFromPresetResponse {
  container: WorkContainer;
  created: boolean;
  dispatch: TeamDispatchResult;
}

// ---- 首页对话式任务草稿（未确认前不属于业务持久状态） ----

export interface TaskDraftIntent {
  title: string;
  goal: string;
  acceptance_criteria: string;
  shared_context: string;
}

export interface EditableTaskDraft extends TaskDraftIntent {
  schema_version: 1;
  preset_id: string;
  preset_version: number;
}

export interface TaskDraftEngineFact {
  id: string;
  name: string;
  runtime_available: boolean;
  availability_reason: string;
}

export interface TaskSetupDraft {
  schema_version: 1;
  state: "ready" | "needs_input";
  clarifications: string[];
  intent: TaskDraftIntent;
  team: {
    preset: TeamPreset;
    confidence: number;
    reason: string;
    matched_signals: string[];
    activation_plan: TeamPresetSnapshot["activation_plan"];
  };
  execution: {
    task_kind: "coding" | "general";
    recommended_engine: string;
    default_engine: string;
    ready: boolean;
    engines: TaskDraftEngineFact[];
    require_approval: true;
    start_immediately: true;
    base_workdir: string;
    default_workspace_policy: WorkspacePolicy;
  };
  provenance: {
    source: "ai" | "local_fallback";
    runtime: "ai-gateway" | "langgraph";
    gateway_type: string;
    model: string | null;
    status_class: string | null;
    fallback_reason: string | null;
    duration_ms: number;
    explanation: string;
  };
}

export interface CreateTaskDraftRequest {
  message: string;
  previous_draft?: EditableTaskDraft | null;
}

export interface WorkspaceAccessSelection {
  folder_access: FolderAccess;
  project_dir: string;
  full_access_acknowledged: boolean;
  project_upload_id: string | null;
}

export interface ProjectUploadSummary {
  upload_id: string;
  file_count: number;
  total_bytes: number;
  folder_name?: string;
}

export interface TeamPresetSnapshot {
  preset: TeamPreset;
  applied_roles: Array<TeamRoleDraft & { session_id: string; run_id: string }>;
  activation_plan: {
    entry: string;
    activation_waves: Array<{ stage: string; roles: string[] }>;
    required_handoffs: Array<{ from_stage: string; to_stage: string }>;
    review_gates: string[];
    runtime: "langgraph" | string;
  };
  dispatch: { dispatched_run_ids: string[]; last_requested_at?: string };
  workspace_access?: {
    folder_access: FolderAccess;
    project_dir: string | null;
    project_upload_id?: string | null;
    worktree_required: boolean;
  };
  recommendation_source?: "ai" | "local_fallback" | "manual" | null;
  team_mode?: "guided" | "autonomous";
  budget_mode?: "bounded" | "max";
}

export interface ExecutionEngineInfo {
  id: string;
  name: string;
  repository: string;
  url: string;
  revision: string;
  reviewed_stars: number;
  license: string;
  license_scope: string;
  source_path: string;
  source_downloaded: boolean;
  package_installed: boolean | null;
  managed_ai_ready: boolean | null;
  transport: "server" | "cli";
  command: string | null;
  capabilities: string[];
  credential_hint: string;
  runtime_available: boolean;
  availability_reason: string;
  default: boolean;
}

export interface ExecutionEnginesResponse {
  default_engine: string;
  engines: ExecutionEngineInfo[];
  authority: {
    control_plane: "BudgetLoop" | string;
    durable_state: "PostgreSQL" | string;
    engines_are_replaceable: boolean;
    silent_fallback: boolean;
  };
}

// ---- 团队观测台 / Session Rail ----

/** 观测台 Session 列表项，聚合了基础摘要、进度信号和预算比率。 */
export interface TeamSessionView {
  id: string;
  container_id: string;
  role: string;
  status: RunStatus | string;
  pressure_mode: PressureMode;
  /** 当前阶段/里程碑，来自进度信号，缺失时显示"未上报" */
  current_phase?: string | null;
  /** ISO 时间戳，用于排序和相对时间展示 */
  last_activity?: string | null;
  /** 进度信号标记的阻塞状态 */
  blocked?: boolean;
  /** 进度信号标记的是否需要操作员介入 */
  needs_operator?: boolean;
  /** Token 使用比率 (used / max)，用于进度条展示；范围 0-1 */
  budget_ratio?: number;
}

// ---- Team Observatory ----

export type TeamStatus = "active" | "paused" | "blocked" | "completed";
export type ConnectionState = "connected" | "stale" | "disconnected";

export interface TeamAlert {
  kind: "approval" | "blocking" | "overspend" | "budget_exhausted";
  message: string;
  session_id?: string | null;
  session_role?: string | null;
}

export interface TeamUsageSummary {
  total_tokens: number;
  max_tokens: number;
  total_cost: number | null;
  max_cost: number;
  total_calls: number;
  max_calls: number;
  elapsed_seconds: number;
  max_wall_time_seconds: number;
  pressure: PressureMode;
  burn_rate_tokens_per_min: number | null;
  est_depletion: string | null;
}

export interface TeamPhaseInfo {
  current_phase: string | null;
  next_milestone: string | null;
}

export interface TeamObservatoryResponse {
  team_status: TeamStatus;
  active_session_count: number;
  total_session_count: number;
  alert_count: number;
  alerts: TeamAlert[];
  usage: TeamUsageSummary | null;
  phase: TeamPhaseInfo | null;
}

export interface TeamStreamEvent {
  seq: number;
  type:
    | "session_message"
    | "session_progress"
    | "session_status_change"
    | "team_control_audit"
    | "budget_pressure_change"
    | "judge_state_changed"
    | "judge_gate_completed"
    | "judge_feedback_dispatched"
    | "judge_verdict_recorded";
  payload: Record<string, unknown>;
  created_at: string;
}

export type JudgeVerdict = "approve" | "rework" | "blocked";

export interface DeterministicGateResult {
  id: string;
  gate_name: string;
  passed: boolean;
  evidence: Record<string, unknown>;
  failure_reason: string | null;
}

export interface JudgeFinding {
  id: string;
  responsible_session_id: string | null;
  severity: string;
  summary: string;
  evidence_refs: unknown[];
  feedback: string | null;
}

export interface JudgeRound {
  id: string;
  sequence: number;
  status: string;
  phase: string;
  verdict: JudgeVerdict | null;
  summary: string | null;
  evidence_refs: unknown[];
  model_verdict: Record<string, unknown> | null;
  feedback_message_ids: string[];
  pending_session_ids: string[];
  gates: DeterministicGateResult[];
  findings: JudgeFinding[];
  created_at: string;
  updated_at: string;
}

export interface JudgePolicy {
  id: string;
  gates: Array<{ name: string; required: boolean }>;
  model_config: Record<string, unknown>;
  safety_limits: Record<string, unknown>;
}

export interface JudgeState {
  enabled: boolean;
  reason?: string | null;
  session?: {
    id: string;
    role: string;
    status: string;
    system_managed: boolean;
    budget: BudgetState;
  } | null;
  policy?: JudgePolicy | null;
  state?: string | null;
  current_round?: JudgeRound | null;
  rounds: JudgeRound[];
  pending_reply_session_ids: string[];
}

export const TEAM_STATUS_LABELS: Record<TeamStatus, string> = {
  active: "运行中",
  paused: "已暂停",
  blocked: "已阻塞",
  completed: "已完成",
};

export const CONNECTION_STATUS_LABELS: Record<ConnectionState, string> = {
  connected: "已连接",
  stale: "数据可能过期",
  disconnected: "已断开",
};

// ---- 团队观测台 / Agent Team 观测台 ----

/** Agent 声明的结构化进度信号（来自 session_progress_signals 表）。 */
export interface SessionProgressSignal {
  id: string;
  session_id: string;
  run_id: string;
  summary: string | null;
  milestone: string | null;
  completed_items: string[] | null;
  next_step: string | null;
  blocked: boolean;
  blocker_reason: string | null;
  needs_operator: boolean;
  evidence: string | null;
  iteration: number;
  created_at: string;
}

/** 轻量容器信息，用于 Run 页面的团队上下文。 */
export interface ContainerTeamInfo {
  id: string;
  name: string;
  lifecycle_state: ContainerLifecycle;
  team_status?: string | null;
}

// ---- Team Inspector 面板 ----

/** 团队进度聚合（含团队摘要和所有 Session 的进度信号）。 */
export interface TeamInspectorProgress {
  team_summary: {
    total: number;
    running: number;
    waiting: number;
    paused: number;
    blocked: number;
    completed: number;
  };
  active_stage: string | null;
  next_focus: string | null;
  sessions: SessionProgressSignal[];
}

/** 团队用量详情（含 Token 分类细项）。 */
export interface TeamInspectorUsage {
  tokens: {
    used: number;
    max: number;
    remaining: number;
    prompt: number | null;
    completion: number | null;
    reasoning: number | null;
    cache_read: number | null;
  };
  cost: {
    used: number | null;
    max: number;
    remaining: number | null;
  };
  wall_time_ms: number;
  max_wall_time_ms: number;
  calls: {
    used: number;
    max: number;
  };
  health: PressureMode;
  active_time_ms: number | null;
  parallelism: {
    current: number;
    max: number;
  };
  consumption_rate_tokens_per_min: number | null;
  estimated_depletion_at: string | null;
}

/** 团队预算调整请求体。 */
export interface TeamBudgetPatch {
  max_total_tokens?: number;
  max_wall_time_seconds?: number;
  max_llm_calls?: number;
  max_cost?: number;
  max_parallel_llm_calls?: number;
}

/** 团队预算调整后响应（含 needs_resume 标记）。 */
export interface TeamBudgetPatchResponse {
  budget: BudgetState;
  needs_resume: boolean;
}

/** Session 预算调整请求体。 */
export interface SessionBudgetPatch {
  max_total_tokens?: number;
  max_wall_time_seconds?: number;
  max_llm_calls?: number;
  max_cost?: number;
}
