# team-runtime-control Specification

## Purpose

Define team-level and session-level real-time control operations — pause, resume, stop, cancel, budget adjustment, parallelism adjustment, and correction instruction injection — with idempotent semantics, mandatory audit trails, and safe budget guardrails.

## ADDED Requirements

### Requirement: Idempotent container-level pause
The system SHALL support an idempotent `POST /api/work-containers/{id}/pause` operation that transitions a running container to the paused state, and SHALL return the same container state without error when called repeatedly on an already-paused container.

#### Scenario: Pause an active container
- **WHEN** an operator calls the container pause endpoint while the container is in the `active` state with running and queued sessions
- **THEN** the container transitions to `paused`, all currently running session runs reach their next safety checkpoint and suspend further LLM calls, all queued and pending sessions stop being dispatched, and an audit event is written with `action=pause` and `old_value={"status":"active"}`

#### Scenario: Pause an already-paused container
- **WHEN** an operator calls the container pause endpoint on a container already in the `paused` state
- **THEN** the endpoint returns 200 with the existing paused state, no duplicate audit event is written, and no session state is altered

#### Scenario: In-flight LLM calls during pause
- **WHEN** a container is paused while sessions have LLM calls already in transit to the provider
- **THEN** those in-flight calls SHALL complete normally and their usage SHALL be settled, but no new LLM calls SHALL be started after the pause is acknowledged

### Requirement: Idempotent container-level resume
The system SHALL support an idempotent `POST /api/work-containers/{id}/resume` operation that transitions a paused container back to the active state, and SHALL return the same state without error when called on an already-active container.

#### Scenario: Resume a paused container
- **WHEN** an operator calls the container resume endpoint on a paused container
- **THEN** the container transitions to `active`, paused session runs resume from their last safety checkpoint, queued sessions begin dispatching again, and an audit event is written with `action=resume`

#### Scenario: Resume an already-active container
- **WHEN** an operator calls the container resume endpoint on a container already in the `active` state
- **THEN** the endpoint returns 200 with the existing active state and no duplicate audit event is written

### Requirement: Container-level stop with mandatory confirmation
The system SHALL require explicit operator confirmation before executing a container stop, and SHALL make the stop irreversible once confirmed.

#### Scenario: Stop request without confirmation
- **WHEN** an operator calls `POST /api/work-containers/{id}/stop` without a confirmation token or `confirm=true`
- **THEN** the system returns a response indicating confirmation is required, describing the affected sessions and their current progress, without executing the stop

#### Scenario: Confirmed stop on active container
- **WHEN** an operator calls the stop endpoint with explicit confirmation
- **THEN** the container transitions to `completed`, all associated sessions are marked cancelled or completed, no new runs are dispatched, an audit event is written with `action=stop`, and the stop is irreversible

#### Scenario: Stop an already-stopped container
- **WHEN** an operator calls the container stop endpoint with confirmation on a container already `completed`
- **THEN** the endpoint returns 200 with the existing completed state and no duplicate audit event is written

### Requirement: Idempotent session-level pause
The system SHALL support idempotent session-level pause that only affects the specified session's run without altering other sessions in the same container.

#### Scenario: Pause a running session
- **WHEN** an operator calls `PATCH /api/work-containers/{id}/sessions/{sid}/pause` on a session whose run is in the RUNNING state
- **THEN** the session run transitions to PAUSED at the next safety checkpoint, no new LLM calls are started for that session, other sessions in the container continue unaffected, and an audit event is written with `action=session_pause`

#### Scenario: Pause an already-paused session
- **WHEN** an operator calls the session pause endpoint on a session already in the PAUSED state
- **THEN** the endpoint returns 200 with the existing paused state and no duplicate audit event is written

#### Scenario: Pause a session in a paused container
- **WHEN** an operator calls the session pause endpoint on a session in a container that is already paused at the container level
- **THEN** the endpoint returns the current state, the session remains paused, and the operation is idempotent

### Requirement: Idempotent session-level resume
The system SHALL support idempotent session-level resume that restores a paused session to the running state only when the parent container is also active.

#### Scenario: Resume a paused session in an active container
- **WHEN** an operator calls `PATCH /api/work-containers/{id}/sessions/{sid}/resume` on a PAUSED session in an active container
- **THEN** the session run transitions from PAUSED to RUNNING, LLM calls resume from the last safety checkpoint, and an audit event is written with `action=session_resume`

#### Scenario: Resume a session in a paused container
- **WHEN** an operator calls the session resume endpoint on a PAUSED session in a container that is currently paused
- **THEN** the session state remains PAUSED and the response includes a `container_paused: true` flag indicating the container must be resumed first

#### Scenario: Resume an already-running session
- **WHEN** an operator calls the session resume endpoint on a session already in the RUNNING state
- **THEN** the endpoint returns 200 with the existing state and no duplicate audit event is written

### Requirement: Session-level cancel with mandatory confirmation
The system SHALL require explicit operator confirmation before cancelling a session, and the cancellation SHALL be irreversible.

#### Scenario: Cancel request without confirmation
- **WHEN** an operator calls the session cancel endpoint without a confirmation token or `confirm=true`
- **THEN** the system returns a response indicating confirmation is required, describing the session's current progress, budget consumed, and pending work, without executing the cancellation

#### Scenario: Confirmed session cancel
- **WHEN** an operator calls the session cancel endpoint with explicit confirmation
- **THEN** the session run transitions to CANCELLED, no further LLM calls are dispatched, any reserved budget is released, an audit event is written with `action=session_cancel`, and the cancellation is irreversible

### Requirement: Budget adjustment with used-plus-reserved floor
The system SHALL enforce that any runtime budget adjustment satisfies `new_max >= used + reserved`, and SHALL reject adjustments that would leave insufficient headroom with a 422 response.

#### Scenario: Valid budget increase
- **WHEN** an operator submits a budget PATCH with `new_max` greater than the current `used + reserved` total
- **THEN** the budget is updated, an audit event is written recording both `old_value` and `new_value`, and the response includes the updated budget state

#### Scenario: Budget adjustment below the floor
- **WHEN** an operator submits a budget PATCH with `new_max` less than the current `used + reserved` total
- **THEN** the system returns 422 with a message stating the minimum allowed value and the current `used + reserved` figures, and the budget remains unchanged

#### Scenario: Budget adjustment to exactly the floor
- **WHEN** an operator submits a budget PATCH with `new_max` exactly equal to `used + reserved`
- **THEN** the budget is updated because `new_max >= used + reserved` is satisfied

### Requirement: Session-level budget adjustment
The system SHALL support runtime budget adjustment at the individual session level, applying the same `used + reserved` floor constraint.

#### Scenario: Adjust a running session budget
- **WHEN** an operator PATCHes the budget of a specific session with a valid `new_max`
- **THEN** only that session's budget is updated, the team aggregate reflects the change, and an audit event is written with the affected `session_id`

#### Scenario: Adjust a completed session budget
- **WHEN** an operator attempts to adjust the budget of a session that is already CANCELLED, COMPLETED, or FAILED
- **THEN** the system returns 422 with a message that the session is no longer active

### Requirement: Budget increase does not silently resume
The system SHALL NOT automatically resume a paused run when its budget is increased. The response SHALL include a `needs_resume: true` flag indicating the operator must explicitly call the resume endpoint.

#### Scenario: Increase budget on a budget-exhausted paused session
- **WHEN** a session is paused due to budget exhaustion and an operator increases its budget above the exhaustion threshold
- **THEN** the budget is updated but the session remains paused, and the response returns `needs_resume: true` with a message indicating the operator must explicitly resume the session

#### Scenario: Increase budget on an active session
- **WHEN** an operator increases the budget of a session that is currently RUNNING
- **THEN** the budget is updated, the session continues running, and `needs_resume` is `false`

### Requirement: Old and new values shown before modification
The system SHALL provide the current and proposed values to the operator before any budget, parallelism, or status mutation is committed, so the operator can review the impact before confirming.

#### Scenario: Preview budget adjustment
- **WHEN** the frontend prepares to submit a budget adjustment
- **THEN** the UI displays the current `max_tokens`, the proposed `new_max`, the `used + reserved` floor, and whether `needs_resume` would be triggered

#### Scenario: Preview parallelism adjustment
- **WHEN** the frontend prepares to submit a parallelism adjustment
- **THEN** the UI displays the current `max_parallel_llm_calls` and the proposed new value, with a note that in-flight calls are not affected

### Requirement: Parallelism adjustment only affects new requests
The system SHALL apply a lowered `max_parallel_llm_calls` value only to new LLM call dispatches, and SHALL NOT interrupt or cancel LLM calls already in flight at the time of the adjustment.

#### Scenario: Lower parallelism with in-flight calls
- **WHEN** an operator lowers `max_parallel_llm_calls` from 4 to 2 while 3 LLM calls are already in flight
- **THEN** the 3 in-flight calls complete normally, but no new calls are dispatched until the count of in-flight calls drops below 2

#### Scenario: Raise parallelism
- **WHEN** an operator raises `max_parallel_llm_calls` from 2 to 4
- **THEN** the new limit takes effect immediately for all subsequent dispatch decisions, and any queued calls awaiting a slot may be dispatched up to the new limit

### Requirement: Correction instruction injection
The system SHALL support injecting a correction instruction into a running session at the next safety checkpoint, with the instruction delivered as a high-priority system message.

#### Scenario: Inject correction into a running session
- **WHEN** an operator calls `POST /api/work-containers/{id}/correct` targeting a specific session with a non-empty instruction
- **THEN** the instruction is queued for injection at the session's next safety checkpoint, delivered as a high-priority system message in the next iteration prompt, and an audit event is written with `action=correct`

#### Scenario: Inject correction into a paused session
- **WHEN** an operator calls the correction endpoint on a paused session
- **THEN** the instruction is queued and will be injected when the session is resumed and reaches its next safety checkpoint

#### Scenario: Injection timing for CLI engines
- **WHEN** a CLI engine session receives a correction instruction
- **THEN** the instruction is injected at the next iteration start, and the frontend displays the message status as `queued` with the note "等待下次执行检查点" (waiting for next execution checkpoint) until the Agent acknowledges it

### Requirement: All operator interventions written to audit events
The system SHALL record every operator-initiated control action — pause, resume, stop, cancel, budget adjustment, parallelism adjustment, correction, and guided/autonomous switch — in the `team_audit_events` table with the acting operator identity, old and new values, affected container, and optional session.

#### Scenario: Pause action generates audit event
- **WHEN** an operator pauses a container
- **THEN** a row is inserted into `team_audit_events` with `action=pause`, `container_id` set to the affected container, `old_value` containing the previous status, `new_value` containing the new status, `operator` extracted from the auth token, and `created_at` set to the current timestamp

#### Scenario: Budget adjustment generates audit event with full diff
- **WHEN** an operator adjusts a budget
- **THEN** a row is inserted into `team_audit_events` with `action=budget_update`, `old_value` containing the full previous budget snapshot (max, used, reserved), `new_value` containing the full new budget snapshot, and `session_id` set if the adjustment was session-scoped or null if team-scoped

#### Scenario: Audit events are queryable
- **WHEN** an operator or auditor retrieves the team audit events for a container
- **THEN** all interventions are returned in chronological order with the acting operator, action, timestamps, and value diffs

### Requirement: SSE disconnect shows stale data warning
The system SHALL indicate when the SSE connection is interrupted and the displayed control state may be stale, with graduated warnings based on disconnection duration.

#### Scenario: Brief SSE interruption
- **WHEN** the SSE connection has been interrupted for more than 10 seconds
- **THEN** the frontend displays a yellow "数据可能过期" (data may be stale) indicator on the control panel and top bar, without blocking control operations

#### Scenario: Extended SSE disconnection
- **WHEN** the SSE connection has been interrupted for more than 30 seconds
- **THEN** the frontend displays a red "已断开" (disconnected) indicator, and control operations display a warning that the current state may be stale before the operator confirms the action

#### Scenario: SSE reconnection restores freshness
- **WHEN** the SSE connection is re-established after an interruption
- **THEN** the stale data warning is cleared, all control state is refreshed from the latest received events via `Last-Event-ID` replay, and subsequent control operations proceed without the staleness warning

### Requirement: Guided-to-autonomous switch requires explicit confirmation
The system SHALL require explicit operator confirmation before switching a running team from `guided` to `autonomous` mode, explaining that the mode change affects stage dispatch, dependency evaluation, and handoff behavior.

#### Scenario: Switch to autonomous mode without confirmation
- **WHEN** an operator attempts to switch a guided team to autonomous mode without providing confirmation
- **THEN** the system returns a response listing the behavioral changes — automatic stage dispatch, dependency-driven execution, and handoff generation — and requires the operator to confirm before the switch is applied

#### Scenario: Confirmed switch to autonomous mode
- **WHEN** an operator confirms the switch from guided to autonomous mode
- **THEN** the team mode is updated, the mode change is persisted in the applied snapshot, an audit event is written with `action=mode_switch` recording the old and new modes, and the next stage dispatch evaluates dependencies autonomously

#### Scenario: Switch from autonomous to guided mode
- **WHEN** an operator confirms the switch from autonomous to guided mode
- **THEN** the team mode reverts to guided, no new automatic stage dispatches occur, currently running autonomous sessions continue to completion, and an audit event is written

### Requirement: Autonomous resume re-evaluates stage dependencies
When an autonomous team is resumed after a pause, the system SHALL re-evaluate stage dependencies before dispatching the next eligible stage.

#### Scenario: Resume autonomous team after pause
- **WHEN** an autonomous team is resumed after being paused
- **THEN** the system re-evaluates which stages are eligible for dispatch based on the current completion states of all runs, rather than blindly continuing from the pre-pause dispatch state

#### Scenario: Resume with changed dependencies
- **WHEN** an autonomous team is resumed and some previously incomplete stages have since been manually cancelled or completed
- **THEN** the dependency re-evaluation correctly skips satisfied or no-longer-applicable stages and dispatches only the newly eligible ones

### Requirement: Container-level pause prevents new session dispatch
When a container is paused, the system SHALL prevent dispatch of any QUEUED or PENDING session runs within that container, and SHALL hold them until the container is resumed.

#### Scenario: Queued session during container pause
- **WHEN** a session is in the QUEUED state and the container is paused
- **THEN** the session SHALL NOT be dispatched to a worker, and its state SHALL remain QUEUED

#### Scenario: Session queued after container resume
- **WHEN** a container is resumed and sessions were held in QUEUED state during the pause
- **THEN** those queued sessions SHALL begin dispatching according to normal scheduling rules

### Requirement: Control operations available on SSE event stream
The system SHALL emit team control audit events to the team SSE event stream so that all connected observers receive real-time notification of control actions.

#### Scenario: Control action appears in team SSE stream
- **WHEN** an operator performs any control action (pause, resume, stop, budget adjustment, etc.)
- **THEN** a `team_control_audit` event is emitted to the team SSE stream with the action type, affected container/session, operator, and timestamp, and all connected frontend instances update their control state accordingly
