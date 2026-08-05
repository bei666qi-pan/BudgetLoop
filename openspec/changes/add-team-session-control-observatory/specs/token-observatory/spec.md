# token-observatory Delta Specification

## Purpose

Extend the token observatory spec to support team-level aggregation via `GET /api/work-containers/{id}/usage`, add session-split consumption breakdown, consumption rate and estimated depletion time, pressure mode classification, and enforce consistent '未上报' labeling for all missing fields across both run-level and team-level views. All aggregates remain derived from PostgreSQL `llm_calls` and `task_budgets` as the sole sources of truth.

## ADDED Requirements

### Requirement: Team-level usage aggregation endpoint

The application SHALL expose `GET /api/work-containers/{id}/usage` that returns real-time aggregated usage metrics for all active sessions within a container. The endpoint SHALL compute aggregates from the run's `llm_calls` and `task_budgets` data without pre-computed caches or materialized views, and SHALL return partial results (with `"未上报"` sentinel for unavailable fields) rather than failing when individual session data is incomplete.

#### Scenario: Active container with multiple sessions

- **WHEN** a container has 2 or more sessions with recorded LLM calls
- **THEN** the endpoint returns a JSON payload containing `team_total` (summed total/prompt/completion/reasoning/cache tokens, estimated cost, call count), `per_session` (array of per-session breakdowns keyed by `session_id`), `consumption_rate` (tokens per minute), `estimated_depletion` (ISO 8601 duration estimate), and `pressure_mode` (one of `NORMAL`, `CONSERVATIVE`, `CRITICAL`)

#### Scenario: Container with mixed session states

- **WHEN** a container has sessions in RUNNING, QUEUED, and completed states
- **THEN** the endpoint SHALL include running and queued sessions in the aggregation and SHALL exclude completed/failed/cancelled sessions whose reserved budget has been released

#### Scenario: Session with incomplete metering data

- **WHEN** a session's LLM calls lack optional fields such as `estimated_cost` or `ttft_ms`
- **THEN** the endpoint returns `"未上报"` for those fields rather than `0` or `null`, and the team total partials out those fields

### Requirement: Session-split consumption view

The team observatory panel SHALL display per-session consumption breakdown, showing for each active session: consumed tokens, reserved tokens, remaining budget, estimated cost, call count, wall-clock time, active time, and individual pressure classification. The session-split view SHALL be derived from the `per_session` array returned by `GET /api/work-containers/{id}/usage`.

#### Scenario: Operator inspects team consumption by session

- **WHEN** the operator views the team usage inspector
- **THEN** each active session is listed with its individual token consumption, budget status, and pressure indicator, sorted by consumption descending

#### Scenario: Session has unlimited budget

- **WHEN** a session's `max_*` budget is unset (unlimited)
- **THEN** the remaining budget displays `"∞"` and the session is excluded from depletion time calculation but included in the consumption rate aggregate

### Requirement: Consumption rate and estimated depletion time

The observatory panel SHALL compute and display a real-time consumption rate in tokens per minute derived from the trailing observation window of `llm_calls`, and SHALL derive an estimated depletion time based on the current rate and remaining budget. The rate and depletion estimate SHALL update on the same refresh cycle as the aggregate metrics.

#### Scenario: Sufficient call history for rate calculation

- **WHEN** the team has 2 or more LLM calls within the observation window (default 5 minutes)
- **THEN** the panel displays the consumption rate as `X.XK tok/min` and an estimated depletion time in human-readable form (e.g. `"2h 15m"`)

#### Scenario: Insufficient history for rate calculation

- **WHEN** the team has fewer than 2 LLM calls in the observation window
- **THEN** the panel displays the rate as `"--"` and the depletion estimate as `"数据不足"`, without fabricating a rate from a single data point

#### Scenario: Remaining budget is unlimited

- **WHEN** at least one active session has unlimited budget and no depletion boundary exists
- **THEN** the estimated depletion time displays `"∞"` for the team aggregate

### Requirement: Pressure mode classification

The team observatory SHALL classify budget pressure into three modes — NORMAL, CONSERVATIVE, CRITICAL — based on the ratio of `(used + reserved) / max` across all active sessions. The pressure mode SHALL be displayed as a visual indicator (color-coded) on both the team top bar and per-session entries, and SHALL be returned in the `pressure_mode` field of the usage aggregation endpoint.

#### Scenario: Budget consumption under 60%

- **WHEN** the team's `(used + reserved) / max` ratio is below 0.6
- **THEN** the pressure mode is NORMAL with a neutral/green indicator

#### Scenario: Budget consumption between 60% and 85%

- **WHEN** the team's `(used + reserved) / max` ratio is at or above 0.6 and below 0.85
- **THEN** the pressure mode is CONSERVATIVE with a warning/yellow indicator

#### Scenario: Budget consumption at or above 85%

- **WHEN** the team's `(used + reserved) / max` ratio is at or above 0.85
- **THEN** the pressure mode is CRITICAL with an alert/red indicator

#### Scenario: Consumption crosses a pressure threshold during a live session

- **WHEN** a new LLM call causes the ratio to cross a pressure threshold (e.g. NORMAL → CONSERVATIVE)
- **THEN** a `budget_pressure_change` SSE event is emitted with the old and new pressure modes, and the frontend updates the indicator without requiring a full page refresh

## MODIFIED Requirements

### Requirement: Aggregate metering metrics

The run detail page and the team observatory dashboard SHALL present an observability panel that aggregates LLM calls into at minimum: total, prompt, completion, reasoning, and cache token counts; summed estimated cost; average call duration and average time-to-first-token when reported; call success rate by `request_status`; and cache-hit rate over calls that report cache fields. For team-level views, the panel SHALL additionally display: consumption rate in tokens per minute, estimated depletion time, pressure mode (NORMAL/CONSERVATIVE/CRITICAL), and per-session consumption breakdown. Aggregates SHALL be derived from real `llm-calls` API data (run-level) or `GET /api/work-containers/{id}/usage` (team-level), and SHALL update on the same refresh cycle as the rest of the page.

#### Scenario: Run with completed LLM calls

- **WHEN** a run has one or more recorded LLM calls with token, duration, and status fields
- **THEN** the panel displays aggregate token, cost, latency, and success metrics computed from those calls without requiring a separate fetch

#### Scenario: Metrics refresh while the run is live

- **WHEN** a new LLM call is recorded during an active run's poll cycle
- **THEN** the aggregate metrics reflect the new call on the next refresh without operator interaction

#### Scenario: Team-level aggregation with multiple sessions

- **WHEN** a container has 2 or more active sessions with recorded LLM calls
- **THEN** the team observatory panel displays summed team totals, per-session breakdown, consumption rate, estimated depletion time, and pressure mode, all derived from the team usage aggregation endpoint

#### Scenario: Team usage inspector section visibility

- **WHEN** the operator opens the team observatory right-side inspector
- **THEN** the usage section shows team-level totals (Token/费用/时间) and pressure indicator by default, with per-session breakdown and rate/depletion details available in a collapsible expanded view

### Requirement: Honest partial metering data

The observability panel SHALL label unavailable or unconfigured metering values explicitly as `"未上报"` and SHALL NOT render them as zeroes, fabricated numbers, or misleading chart lines. This labeling SHALL be consistent across run-level detail views, team-level aggregate views, and per-session breakdown views.

#### Scenario: Cost is not configured

- **WHEN** every recorded call reports a null estimated cost
- **THEN** the panel labels cost as `"未上报"` and omits or empty-states the cost trend instead of plotting zero

#### Scenario: Sparse optional fields

- **WHEN** individual calls lack optional fields such as `ttft_ms` or cache token counts
- **THEN** those cells display `"未上报"` rather than zero or blank

#### Scenario: Team-level aggregate with partial session data

- **WHEN** the team usage endpoint returns partial data because some sessions have not reported cost or optional metering fields
- **THEN** the team total row SHALL display `"未上报"` for fields where no session contributed a value, the per-session rows SHALL individually label missing fields as `"未上报"`, and the team-level estimated cost SHALL only sum sessions that reported cost
