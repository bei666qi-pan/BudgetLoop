# team-budget-observatory Specification

## Purpose

Define the team-level and session-split usage observatory: aggregate and per-session metering metrics, token sub-type breakdowns, consumption rate, estimated depletion time, budget pressure mode, and honest handling of missing fields — all derived from real `llm_calls` and `task_budgets` ledger data with PostgreSQL as the sole source of truth.

## ADDED Requirements

### Requirement: Team aggregate usage endpoint
The system SHALL provide `GET /api/work-containers/{id}/usage` that returns a team-level usage aggregate computed from all non-terminal (RUNNING/QUEUED) sessions' `task_budgets` and `llm_calls` within the container. The aggregate SHALL include at minimum: used tokens, reserved tokens, remaining tokens, `max_total_tokens`, used cost, `max_cost`, used calls, `max_llm_calls`, wall-clock elapsed time, active runtime, `max_active_runtime_seconds`, current parallelism count, and a `pressure_mode` computed using the existing `compute_pressure_mode` logic. Remaining cost and remaining calls SHALL be derived from `max` minus `used`; reserved tokens SHALL be counted only for sessions whose status is RUNNING or QUEUED.

#### Scenario: Team with multiple running sessions
- **WHEN** a container has two RUNNING sessions with `task_budgets.used_tokens` of 45000 and 32000, `task_budgets.reserved_tokens` of 5000 and 3000, and `task_budgets.max_total_tokens` of 200000 and 100000
- **THEN** the aggregate returns used_tokens=77000, reserved_tokens=8000, remaining_tokens=223000, and max_total_tokens=300000

#### Scenario: Completed session excluded from reserved
- **WHEN** a container has one RUNNING session with reserved_tokens=5000 and one COMPLETED session with reserved_tokens=3000
- **THEN** the team aggregate reserved_tokens=5000, excluding the completed session's reservation

#### Scenario: Unlimited max on a session
- **WHEN** a session's `max_total_tokens` is set to a sentinel value indicating unlimited
- **THEN** the team aggregate `max_total_tokens` displays as "∞" and is excluded from the total sum

### Requirement: Session-split usage breakdown
The team usage endpoint SHALL return a per-session breakdown that includes, for each session in the container: used tokens, reserved tokens, remaining tokens, `max_total_tokens`, used cost, `max_cost`, used calls, `max_llm_calls`, wall-clock elapsed time, active runtime, `max_active_runtime_seconds`, `max_parallel_llm_calls`, and `pressure_mode`. Inactive (COMPLETED/FAILED/CANCELLED) sessions SHALL report their final used values but SHALL have `reserved_*` fields set to zero. The per-session breakdown SHALL be ordered by the same sort as the SessionRail in the UI.

#### Scenario: Mixed active and finished sessions
- **WHEN** a container has one RUNNING session, one QUEUED session, and one COMPLETED session
- **THEN** the per-session breakdown returns all three with the RUNNING and QUEUED sessions reporting non-zero reserved values and the COMPLETED session reporting reserved_tokens=0, reserved_cost=0, reserved_calls=0

### Requirement: Token sub-type breakdown from llm_calls
The team and per-session usage responses SHALL include a token sub-type breakdown aggregated from `llm_calls`: `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `cache_read_tokens`, and `cache_write_tokens`. The aggregate SHALL compute `total_tokens` as the sum of `prompt_tokens + completion_tokens`. Sub-type fields SHALL be computed independently so that partial reporting (e.g., a provider that does not report reasoning tokens) does not affect the ability to display reported sub-types.

#### Scenario: All sub-types reported
- **WHEN** all `llm_calls` for a session report `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, and cache tokens
- **THEN** the sub-type breakdown returns summed values for each field

#### Scenario: Sparse sub-type reporting
- **WHEN** some `llm_calls` report `reasoning_tokens` but others report NULL for that field
- **THEN** `reasoning_tokens` in the aggregate includes only the non-NULL values; the frontend SHALL NOT treat the aggregate as incomplete

### Requirement: Consumption rate calculation
The system SHALL compute a consumption rate expressed as tokens consumed per minute. The rate SHALL be derived from `(used_tokens) / (active_runtime_ms / 60000)` when active runtime is greater than zero. When `active_runtime_ms` is zero (session not yet active), the consumption rate SHALL NOT be reported and the frontend SHALL display "未上报" or an equivalent unavailable label.

#### Scenario: Active session with measurable runtime
- **WHEN** a session has used_tokens=30000 and active_runtime_ms=900000 (15 minutes)
- **THEN** the consumption rate is 2000 tokens/minute

#### Scenario: Session not yet active
- **WHEN** a session's `active_runtime_ms` is zero
- **THEN** the consumption rate field is absent or null, and the frontend SHALL display "未上报"

### Requirement: Estimated depletion time
The system SHALL compute an estimated depletion time for the team and each session. The estimate SHALL be `(remaining_tokens) / (consumption_rate)` converted to a human-readable duration when the consumption rate is available and greater than zero. When the consumption rate is unavailable or zero, the estimated depletion time SHALL NOT be reported and the frontend SHALL display "未上报". When `remaining_tokens <= 0`, the estimate SHALL be reported as zero (already depleted).

#### Scenario: Stable consumption
- **WHEN** team remaining_tokens=223000 and the aggregate consumption rate is 6000 tokens/minute
- **THEN** the estimated depletion time is approximately 37 minutes 10 seconds

#### Scenario: No consumption rate
- **WHEN** no session has accrued active runtime and the consumption rate is unavailable
- **THEN** the estimated depletion time SHALL display "未上报"

### Requirement: Budget pressure mode
The team and per-session usage SHALL include a `pressure_mode` field computed using the existing `compute_pressure_mode` function from `app/policy/pressure.py`. The mode SHALL be one of NORMAL, CONSERVATIVE, or CRITICAL. The team-level pressure SHALL be the tightest pressure across all non-terminal sessions. Pressure mode SHALL be recomputed on every usage query and SHALL NOT be cached beyond the request lifetime.

#### Scenario: All sessions have ample budget
- **WHEN** every session's token and time remaining ratios are above 0.5
- **THEN** the team pressure_mode is NORMAL

#### Scenario: One session critically low on tokens
- **WHEN** one RUNNING session has `remaining_tokens / max_total_tokens < 0.2` while all other sessions are above 0.5
- **THEN** the team pressure_mode is CONSERVATIVE (token ratio below CRITICAL_THRESHOLD forces at least CONSERVATIVE)

#### Scenario: Wall-clock deadline looming
- **WHEN** a session's `(deadline_at - now) / max_wall_time_seconds < 0.2`
- **THEN** the session pressure_mode is CRITICAL and the team pressure_mode is CRITICAL

### Requirement: Default collapsed detail view
The usage observatory UI SHALL display only tokens, cost, time, and pressure health status by default. The token sub-type breakdown, consumption rate, estimated depletion time, parallelism, and per-call details SHALL be hidden behind an expandable "详情" (details) toggle. When the details section is collapsed, the visible summary SHALL still convey whether the budget is healthy (NORMAL), under strain (CONSERVATIVE), or critically low (CRITICAL) via the pressure mode indicator.

#### Scenario: Operator opens the usage panel
- **WHEN** the usage panel renders for the first time
- **THEN** only tokens (used/max), cost (used/max), wall-clock elapsed, and a pressure mode badge are visible; the detail section toggle is in its collapsed state

#### Scenario: Operator expands detail
- **WHEN** the operator clicks the "详情" toggle
- **THEN** the panel reveals prompt/completion/reasoning/cache token sub-types, consumption rate, estimated depletion time, parallelism count, and per-call counts

### Requirement: Honest handling of missing fields
The usage observatory frontend SHALL label unavailable or unconfigured metric values explicitly as "未上报" and SHALL NOT render them as zero, fabricated numbers, or hidden values. Fields that SHALL be treated as "未上报" when absent include: `estimated_cost` when NULL across all calls, `reasoning_tokens` when no call reports them, `cache_read_tokens` / `cache_write_tokens` when no call reports them, `ttft_ms` aggregates, consumption rate when active runtime is zero, and estimated depletion time when the consumption rate is unavailable. The backend SHALL return these fields as `null` (not zero) in JSON responses.

#### Scenario: Cost is not configured for any model
- **WHEN** every `llm_call` in the container has `estimated_cost` as NULL
- **THEN** the backend returns `used_cost: null` and `max_cost: null`; the frontend displays "未上报" for both used and max cost

#### Scenario: Some calls report cache tokens, others do not
- **WHEN** 3 of 5 calls report `cache_read_tokens` and 2 report NULL
- **THEN** the backend returns `cache_read_tokens` as the sum of the 3 non-NULL values; the frontend displays that sum without a "未上报" label because partial data is still valid

### Requirement: Data sourced exclusively from PostgreSQL
All usage data SHALL be computed from live PostgreSQL queries against `task_budgets`, `llm_calls`, `task_runs`, and `work_sessions`. The system SHALL NOT use in-memory caches, pre-computed materialized views, or secondary data stores as the primary source for any usage metric. Aggregation queries SHALL join `llm_calls` via `run_id → task_runs → work_sessions.current_run_id` to associate calls with sessions and SHALL join `work_sessions` via `container_id` to scope to the team.

#### Scenario: Usage endpoint called during active execution
- **WHEN** a new LLM call is committed to `llm_calls` while the team is running
- **THEN** the next `GET /api/work-containers/{id}/usage` call reflects that call in both the team aggregate and the owning session's breakdown

#### Scenario: Budget reservation changes
- **WHEN** the worker updates `task_budgets.reserved_tokens` in a transaction
- **THEN** the team aggregate reserved_tokens reflects the new value on the next usage query without any cache invalidation step

### Requirement: Usage data refresh on SSE event stream
The team SSE event stream (`GET /api/work-containers/{id}/stream`) SHALL emit a `budget_update` event whenever a significant budget threshold is crossed: pressure mode changes (NORMAL→CONSERVITIVE, CONSERVATIVE→CRITICAL, CRITICAL→CONSERVATIVE, CONSERVATIVE→NORMAL), or a session's remaining tokens drop below 20% or 10% of its max. The frontend SHALL listen for `budget_update` events and refresh the usage panel without a full page reload. When the SSE connection is lost and the frontend falls back to polling, the usage panel SHALL refresh on the poll interval.

#### Scenario: Pressure mode degrades
- **WHEN** a session's remaining token ratio drops below 0.2, causing its pressure to change from NORMAL to CONSERVATIVE
- **THEN** a `budget_update` event is emitted on the team SSE stream with the new pressure_mode and affected session_id

#### Scenario: SSE disconnected, polling fallback
- **WHEN** the SSE EventSource connection is lost for more than 10 seconds
- **THEN** the usage panel refreshes its data on the polling interval and displays a "数据可能过期" label until the next successful fetch

### Requirement: Team budget consistency constraint
The team aggregate `used_*` and `reserved_*` values SHALL equal the sum of the corresponding per-session values for non-terminal sessions. The `POST /api/work-containers/{id}/pause`, `POST /api/work-containers/{id}/resume`, and `PATCH /api/work-containers/{id}/budget` endpoints SHALL validate that `new_max >= used + reserved` for the affected scope and SHALL return HTTP 422 with a descriptive error when the constraint would be violated. Modifying a team budget SHALL NOT silently adjust individual session budgets; session-level budget adjustments SHALL be explicit.

#### Scenario: Team budget adjustment below floor
- **WHEN** the operator attempts to PATCH team `max_total_tokens` to a value below `used_tokens + reserved_tokens`
- **THEN** the endpoint returns HTTP 422 with an error body containing the current `used + reserved` total and the rejected new max

#### Scenario: Team aggregate equals session sum
- **WHEN** a container has sessions with used_tokens of 10000, 20000, and 5000 (all RUNNING)
- **THEN** the team aggregate used_tokens is 35000 and each session's individual used_tokens appears in the per-session breakdown

### Requirement: Runtime budget adjustment with old/new audit
Every runtime budget adjustment via `PATCH /api/work-containers/{id}/budget` and session-level `PATCH /api/work-containers/{id}/sessions/{sid}/budget` SHALL write an audit event to `team_audit_events` recording the `action`, `old_value` (the budget fields before modification), `new_value` (the budget fields after modification), `operator` identity, and `created_at` timestamp. The response SHALL include `needs_resume: true` when a budget increase was applied to a session that was previously capped due to exhaustion, and the frontend SHALL display a "已增加预算，请点击恢复" prompt.

#### Scenario: Increasing a depleted session's token budget
- **WHEN** the operator increases `max_total_tokens` on a session that has `used_tokens >= max_total_tokens` (capped)
- **THEN** the response includes `needs_resume: true` and the frontend shows a resume button with the prompt

#### Scenario: Audit event recorded
- **WHEN** any budget PATCH is processed successfully
- **THEN** a row is inserted into `team_audit_events` with action="budget_update", old_value and new_value as JSONB snapshots of the changed budget fields, and the operator from the auth context
