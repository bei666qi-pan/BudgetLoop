# work-container-lifecycle Delta Specification

## Purpose

Extend the work container lifecycle with container-level pause/resume/stop control operations, team status derivation from aggregated session states (never invented), runtime budget and parallelism adjustment via PATCH, and a container-level SSE event stream endpoint that aggregates all session public events.

## ADDED Requirements

### Requirement: Container-level pause, resume, and stop control operations

The system SHALL provide idempotent container-level pause, resume, and stop operations that transition the container lifecycle state and propagate to all owned sessions, and SHALL write an audit event for every control operation.

#### Scenario: Operator pauses an active container

- **WHEN** an authenticated operator submits a pause request for a container in `active` state
- **THEN** the system transitions the container to `paused`, pauses all RUNNING sessions' current runs, prevents QUEUED/PENDING sessions from being dispatched, and writes a `team_audit_events` row with action `pause`

#### Scenario: Operator pauses an already-paused container

- **WHEN** an authenticated operator submits a pause request for a container already in `paused` state
- **THEN** the system returns success without changing state and does not create a duplicate audit event

#### Scenario: Operator resumes a paused container

- **WHEN** an authenticated operator submits a resume request for a container in `paused` state
- **THEN** the system transitions the container to `active`, resumes all previously-paused session runs that were paused by the container-level pause, re-enables dispatch for QUEUED/PENDING sessions, and writes a `team_audit_events` row with action `resume`

#### Scenario: Operator resumes an already-active container

- **WHEN** an authenticated operator submits a resume request for a container already in `active` state
- **THEN** the system returns success without changing state and does not create a duplicate audit event

#### Scenario: Operator stops a container

- **WHEN** an authenticated operator submits a stop request with explicit confirmation for an active or paused container
- **THEN** the system transitions the container to `completed`, stops all running session runs, cancels all QUEUED/PENDING sessions, and writes a `team_audit_events` row with action `stop`

#### Scenario: Stop is rejected without confirmation

- **WHEN** an authenticated operator submits a stop request without the required confirmation flag
- **THEN** the system rejects the request with a 400 response requiring explicit confirmation

#### Scenario: Container-level pause allows in-flight calls to complete

- **WHEN** a container pause is issued while one or more sessions have in-progress LLM calls
- **THEN** the system allows those in-flight calls to complete and does not start new LLM calls after pause is acknowledged

### Requirement: Runtime budget and parallelism adjustment

The system SHALL allow runtime adjustment of container-level budget limits and maximum parallel LLM calls via a PATCH endpoint, SHALL enforce `new_max >= used + reserved` for budget increases, SHALL require an explicit resume after a budget exhaustion recovery, and SHALL write an audit event for every adjustment.

#### Scenario: Operator increases container budget

- **WHEN** an authenticated operator submits a PATCH with an increased `max_total_tokens` that is at least `used_total_tokens + reserved_total_tokens`
- **THEN** the system updates the budget, returns the new and old values, sets `needs_resume: true` if the container was paused due to budget exhaustion, and writes a `team_audit_events` row with old and new budget values

#### Scenario: Budget adjustment is rejected below used-plus-reserved

- **WHEN** an authenticated operator submits a PATCH with a `max_total_tokens` less than `used_total_tokens + reserved_total_tokens`
- **THEN** the system rejects the request with a 422 response and a field-specific error indicating the minimum allowed value

#### Scenario: Operator adjusts maximum parallel LLM calls

- **WHEN** an authenticated operator submits a PATCH with a new `max_parallel_llm_calls` value
- **THEN** the system updates the limit, applies it only to newly initiated LLM calls without interrupting in-flight calls, and writes a `team_audit_events` row with old and new values

#### Scenario: Budget increase after exhaustion does not silently resume

- **WHEN** an operator increases the budget for a container that was paused due to budget exhaustion
- **THEN** the response includes `needs_resume: true` and the container remains paused until an explicit resume request is received

### Requirement: Container-level SSE event stream

The system SHALL provide a container-level SSE endpoint at `GET /api/work-containers/{id}/stream` that aggregates public events from all sessions owned by the container, SHALL support `Last-Event-ID` replay for disconnected clients, and SHALL emit only events with a non-null `container_id`.

#### Scenario: Client connects to container SSE stream

- **WHEN** a client opens an EventSource connection to `GET /api/work-containers/{id}/stream`
- **THEN** the system streams events of types `session_message`, `session_progress`, `session_status_change`, `team_control_audit`, and `budget_pressure_change` from all sessions belonging to the container, ordered by sequence number

#### Scenario: Client reconnects after disconnection

- **WHEN** a client reconnects with a `Last-Event-ID` header set to the last received event sequence number
- **THEN** the system resumes the stream from the next event after that sequence, ensuring no events are missed during the disconnection

#### Scenario: Legacy run events are excluded from container stream

- **WHEN** an execution event has a null `container_id` (belonging to a legacy run without container ownership)
- **THEN** the container SSE stream does not emit that event

#### Scenario: Single event payload does not exceed size limit

- **WHEN** any SSE event is emitted
- **THEN** the event payload SHALL NOT exceed 4KB

## MODIFIED Requirements

### Requirement: Trustworthy container lifecycle

The interface SHALL distinguish active, paused, completed and archived container states, SHALL derive live execution summaries from session runs rather than inventing progress, SHALL derive team status exclusively from aggregated session states (never inventing a team-level state independent of session states), and SHALL transition container state in response to explicit pause, resume, and stop control operations.

#### Scenario: Container has mixed session states

- **WHEN** some sessions are running, waiting or terminal
- **THEN** the container summary reports those counts and does not collapse them into a false single run state

#### Scenario: Team status is derived from session states

- **WHEN** the container's team status is requested
- **THEN** the system derives the status exclusively from aggregated session states — for example, `running` when at least one session is RUNNING, `paused` when the container is paused, `blocked` when one or more sessions are blocked and no session is running, `completed` when all sessions are terminal — and never fabricates a team status independent of session states

#### Scenario: Container state transitions via control operations

- **WHEN** a container-level pause, resume, or stop operation is executed
- **THEN** the container lifecycle state transitions to `paused`, `active`, or `completed` respectively, and the team status derivation reflects the new container state

### Requirement: Container session membership

The system SHALL list only sessions owned by the requested work container, SHALL preserve their independent role, goal, context, status and current run linkage, and SHALL include derived team status, usage summary, and progress summary in the container response.

#### Scenario: Operator opens a container

- **WHEN** the container exists
- **THEN** the response includes container facts, ordered session summaries with derived live and attention counts, a `team_status` field derived from aggregated session states, a `usage_summary` aggregating token and cost across all sessions, and a `progress_summary` aggregating milestone and blocker counts across all sessions

#### Scenario: Nested session does not belong to container

- **WHEN** a session identifier is requested under a different container identifier
- **THEN** the system returns not found without exposing the foreign session

#### Scenario: Team status in container response reflects real session states

- **WHEN** the container response includes `team_status`
- **THEN** the `team_status` value is derived exclusively from the states of sessions owned by the container, and does not represent an independently stored or invented team-level state
