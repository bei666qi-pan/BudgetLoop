# Team Progress Observability Specification

## Purpose

Provide structured, truthful progress observability at both the team and individual session level, grounded solely in Agent-declared progress signals — never inferred from heartbeats or tool-call activity — without incurring any additional LLM calls.

## ADDED Requirements

### Requirement: Structured Progress Signal Recording

The system SHALL persist per-session progress signals as explicit structured records in the `session_progress_signals` table. Each signal MUST be generated only when the Agent explicitly declares progress via the coordination protocol; the system SHALL NOT auto-generate signals from heartbeats, tool-call events, or any other execution-level activity.

Fields:
- `summary` — human-readable one-line description of current work
- `milestone` — name of the current milestone, explicitly declared by the Agent
- `completed_items` — JSON array of items completed since the last signal
- `next_step` — concrete next action the Agent intends to take
- `blocked` — boolean indicating whether the session is blocked
- `blocker_reason` — free-text explanation of the blocker when `blocked` is true
- `needs_operator` — boolean indicating whether operator intervention is required
- `evidence` — reference to concrete evidence (file path, line number, test result, command output)

#### Scenario: Agent declares a milestone achievement

- **WHEN** an Agent in session `s1` running under container `c1` completes a milestone and emits a structured progress signal through the coordination protocol
- **THEN** a row SHALL be inserted into `session_progress_signals` with `session_id = s1`, `milestone = "数据模型+迁移完成"`, `completed_items = ["users 表迁移", "tasks 表迁移"]`, `next_step = "实现 POST /api/tasks 路由处理"`, `blocked = false`, `needs_operator = false`, and `evidence = "models.py L392, migrations/003_add_tasks.py"`

#### Scenario: Agent declares a blocker requiring operator attention

- **WHEN** an Agent encounters a blocking condition it cannot resolve and emits a progress signal with `blocked = true` and `needs_operator = true`
- **THEN** the row SHALL be persisted with `blocked = true`, `blocker_reason` containing the specific obstacle and what was attempted, `needs_operator = true`, and the signal SHALL trigger a `session_progress` SSE event visible to the operator

#### Scenario: Heartbeat event does NOT create a progress signal

- **WHEN** an Agent emits a heartbeat or any tool-call execution event but does NOT explicitly declare progress via the coordination protocol
- **THEN** no row SHALL be written to `session_progress_signals`, and no progress update SHALL appear in the observatory

#### Scenario: Agent does not declare progress

- **WHEN** a session has no `session_progress_signals` rows because the Agent has not yet declared any progress
- **THEN** the observatory SHALL display "Agent 未声明进度" for that session rather than fabricating progress from execution events

#### Scenario: Multiple progress signals accumulate per session

- **WHEN** an Agent declares progress three times during a session lifecycle at iterations 5, 12, and 20
- **THEN** each declaration SHALL create a separate row in `session_progress_signals` with distinct `iteration` values (5, 12, 20) and distinct `created_at` timestamps, and the latest row (by `created_at`) SHALL be used as the current progress state

### Requirement: Session Progress State Query

The system SHALL expose the latest progress signal for a given session through the container detail API and the team progress aggregation endpoint. The latest signal is defined as the row with the maximum `created_at` for that session.

#### Scenario: Container detail includes latest progress per session

- **WHEN** `GET /api/work-containers/{id}` is called for a container with three sessions, each having at least one progress signal
- **THEN** the response SHALL include a `progress_summary` array with one entry per session, each containing `session_id`, `summary`, `milestone`, `next_step`, `blocked`, `needs_operator`, and `latest_signal_at`

#### Scenario: Session has no progress signals

- **WHEN** `GET /api/work-containers/{id}` is called and a session has zero rows in `session_progress_signals`
- **THEN** the corresponding `progress_summary` entry SHALL have `summary = null`, `milestone = null`, `next_step = null`, `blocked = false`, `needs_operator = false`, and `latest_signal_at = null`

#### Scenario: Team progress endpoint returns all session progress

- **WHEN** `GET /api/work-containers/{id}/progress` is called
- **THEN** the response SHALL contain a JSON array where each element represents one session with its latest progress signal fields, ordered by `latest_signal_at` descending

### Requirement: Team-Level Progress Aggregation

The system SHALL compute a team-level progress aggregate from all sessions within a container. The aggregate MUST include: counts of sessions in each status category (`running`, `waiting`, `paused`, `blocked`, `completed`), the active stage derived from the container state, and the most recent milestones across all sessions.

#### Scenario: Mixed team with running, waiting, and blocked sessions

- **WHEN** a container has 2 sessions in RUNNING state, 1 in QUEUED (waiting), 1 in PAUSED, 1 blocked (latest progress signal has `blocked = true`), and 1 in COMPLETED state
- **THEN** the team aggregate SHALL report `running = 2`, `waiting = 1`, `paused = 1`, `blocked = 1`, `completed = 1`

#### Scenario: Team aggregate includes recent milestones

- **WHEN** `GET /api/work-containers/{id}/progress` is called and sessions have progress signals with milestones `"数据模型完成"` (5m ago), `"API 路由完成"` (2m ago), and `"测试编写中"` (just now)
- **THEN** the team aggregate SHALL include a `recent_milestones` list ordered by `created_at` descending, containing at most the 10 most recent milestones across all sessions

#### Scenario: Team aggregate includes active stage

- **WHEN** a container is in the `active` state with sessions predominantly in implementation phases
- **THEN** the `active_stage` in the team aggregate SHALL reflect the container's current stage (e.g., `"实现+审查"`) as derived from session statuses and milestone names

#### Scenario: All sessions completed

- **WHEN** all sessions in a container have status COMPLETED
- **THEN** the team aggregate SHALL report `running = 0`, `completed = N` (where N is the total session count), `active_stage` SHALL indicate completion, and `recent_milestones` SHALL include the final milestones from each session

### Requirement: Percentage Only for Explicit Finite Milestones

The system SHALL display a completion percentage ONLY when the Agent declares a milestone with a finite, countable scope. Percentages MUST NOT be inferred from elapsed time, iteration count, tool-call count, or any other proxy metric. When a milestone is open-ended or the total is unknown, the UI SHALL show the milestone name and `completed_items` count without a percentage.

#### Scenario: Finite milestone with known total

- **WHEN** an Agent declares `milestone = "编写测试用例"` with `completed_items = ["test_auth.py", "test_models.py"]` and the milestone definition implies 5 total test files
- **THEN** the observatory MAY display "编写测试用例 2/5 (40%)" using the Agent-declared items as numerator and the explicit milestone total as denominator

#### Scenario: Open-ended milestone without known total

- **WHEN** an Agent declares `milestone = "代码审查"` with `completed_items = ["reviewed auth.py"]` and no explicit total is known
- **THEN** the observatory SHALL display "代码审查 · 完成 1 项" without a percentage, and SHALL NOT compute a percentage from iteration count or elapsed time

#### Scenario: Milestone has no completed_items

- **WHEN** an Agent declares a milestone with `completed_items = []` or `completed_items` is an empty array
- **THEN** the observatory SHALL display the milestone name without a count or percentage (e.g., "数据模型设计")

#### Scenario: Percentage must not be derived from heartbeats

- **WHEN** a session has emitted 12 heartbeat events but the Agent has not declared any milestone with a finite total
- **THEN** the observatory SHALL NOT display "12/?" or any percentage derived from event counts, and SHALL NOT use heartbeat frequency as an implicit progress indicator

### Requirement: Progress Signals Do Not Require Additional LLM Calls

The system SHALL NOT invoke any LLM call to generate, refresh, or enrich progress signals. Progress signals SHALL originate exclusively from the Agent's own structured output during its normal execution loop via the coordination protocol. The observatory backend SHALL only read from the `session_progress_signals` table; it SHALL NOT synthesize, summarize, or rephrase progress data through an LLM.

#### Scenario: Progress aggregation query does not trigger LLM

- **WHEN** `GET /api/work-containers/{id}/progress` is called
- **THEN** the backend SHALL execute only PostgreSQL SELECT queries against `session_progress_signals` and related tables; no LLM API call SHALL be made

#### Scenario: Progress summary in container detail is SQL-only

- **WHEN** `GET /api/work-containers/{id}` includes `progress_summary` in its response
- **THEN** the `progress_summary` SHALL be computed entirely from SQL joins and aggregations; the backend SHALL NOT pass progress data through an LLM for summarization

#### Scenario: Frontend displays raw progress fields

- **WHEN** the frontend renders a session's progress card
- **THEN** it SHALL display the `summary`, `milestone`, `next_step`, and `blocker_reason` fields as-provided by the Agent, without sending them to an LLM for rephrasing, translation, or enrichment

### Requirement: Progress Signal SSE Events

The system SHALL emit an SSE event of type `session_progress` on the team event stream whenever a new row is inserted into `session_progress_signals`. The event payload SHALL include the full progress signal fields (`session_id`, `summary`, `milestone`, `completed_items`, `next_step`, `blocked`, `blocker_reason`, `needs_operator`, `evidence`, `iteration`, `created_at`).

#### Scenario: Progress signal triggers SSE event

- **WHEN** an Agent declares progress and a row is inserted into `session_progress_signals`
- **THEN** an SSE event with `event: session_progress` SHALL be published on `GET /api/work-containers/{container_id}/stream`, and the data payload SHALL be valid JSON containing all progress signal fields

#### Scenario: SSE reconnection replays missed progress events

- **WHEN** a client disconnects from the team SSE stream and reconnects with `Last-Event-ID` set to a prior `seq` value
- **THEN** all `session_progress` events with `seq` greater than the provided `Last-Event-ID` SHALL be replayed in order, ensuring the client receives any progress signals emitted during the disconnection

#### Scenario: Progress event emitted on correct team stream

- **WHEN** a session `s1` belonging to container `c1` emits a progress signal
- **THEN** the `session_progress` SSE event SHALL be published ONLY on the stream for container `c1`, and SHALL NOT appear on streams for other containers

### Requirement: Progress Data Isolation

The system SHALL NOT expose progress data from one session to the UI context of another session, except through the team aggregate view where individual session progress is displayed alongside all other sessions. The system SHALL NOT leak `private_context`, hidden reasoning, or credential data through progress signal fields.

#### Scenario: Session progress card shows only that session's data

- **WHEN** an operator selects session `s1` in the observatory
- **THEN** the progress inspector SHALL display only the progress signals belonging to `s1`, and SHALL NOT include fields from other sessions' progress signals

#### Scenario: Private context is not exposed in progress fields

- **WHEN** an Agent includes internal reasoning in its execution but declares a progress signal
- **THEN** the `summary`, `milestone`, `next_step`, `blocker_reason`, and `evidence` fields SHALL NOT contain hidden reasoning, API keys, passwords, or any data from `private_context`

#### Scenario: Team aggregate includes all non-sensitive session progress

- **WHEN** the team progress aggregate is displayed
- **THEN** it SHALL include the latest progress signal summary for every session in the container, and SHALL NOT filter out any session's public progress data

### Requirement: Progress Data Retention and Query Performance

The system SHALL retain all `session_progress_signals` rows for the lifetime of the container. Queries for the latest progress signal per session SHALL use an index on `(session_id, created_at DESC)` to ensure sub-millisecond lookup regardless of historical signal count.

#### Scenario: Historical progress signals are preserved

- **WHEN** a session has emitted 50 progress signals over its lifetime
- **THEN** all 50 rows SHALL remain queryable; the latest-signal query SHALL return only the most recent row without scanning all 50

#### Scenario: Team progress aggregation performs within budget

- **WHEN** `GET /api/work-containers/{id}/progress` is called for a container with 8 sessions, each having up to 100 historical progress signals
- **THEN** the query SHALL complete in under 100ms using the `(session_id, created_at DESC)` index with a `DISTINCT ON` or `ROW_NUMBER()` window function
