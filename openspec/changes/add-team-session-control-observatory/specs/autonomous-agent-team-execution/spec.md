# autonomous-agent-team-execution Delta Specification

## Purpose

Extend autonomous agent team execution with team pause/resume/stop impact on autonomous dispatch, guided/autonomous runtime switch with confirmation flow, and coordination protocol requirements for autonomous agents.

## ADDED Requirements

### Requirement: Guided-to-autonomous runtime mode switch
The system SHALL allow an operator to switch a team's execution mode between `guided` and `autonomous` at any point during the team lifecycle, SHALL present a confirmation dialog explaining the operational impact before applying the switch, and SHALL persist the mode change as an auditable event.

#### Scenario: Switch from guided to autonomous at runtime
- **WHEN** an operator requests switching a `guided` team to `autonomous` mode while the team container is active
- **THEN** the system presents a confirmation detailing that staged parallel dispatch will activate, handoffs will flow automatically, and the operator should verify preset-stage dependency configuration
- **AND** upon operator confirmation, the mode is persisted to the run configuration snapshot and a `team_audit_events` record is written with `action = 'mode_switch'`, `old_value = {'mode': 'guided'}`, `new_value = {'mode': 'autonomous'}`

#### Scenario: Switch from autonomous to guided at runtime
- **WHEN** an operator requests switching an `autonomous` team to `guided` mode while the team container is active
- **THEN** the system presents a confirmation detailing that automatic stage dispatch and handoffs will cease, in-flight autonomous runs will complete their current stages, and the operator must manually advance stages thereafter
- **AND** upon operator confirmation, the mode change is persisted and audited, and any pending dependent-stage runs that were awaiting predecessor completion are held until the operator explicitly dispatches them

#### Scenario: Mode switch rejected by operator
- **WHEN** an operator declines the confirmation dialog for a mode switch
- **THEN** the current mode is preserved unchanged and no audit event is written

#### Scenario: Mode switch on a stopped team
- **WHEN** an operator attempts to switch mode on a team container in `completed` state
- **THEN** the request is rejected with a 422 status and an error message indicating the container is not in an editable state

### Requirement: Autonomous agent coordination protocol
Autonomous agents in a team execution SHALL follow a coordination protocol that governs inter-agent communication, structured progress reporting, blocking escalation, budget-pressure adaptation, and completion attestation. The protocol SHALL be enforced through both injected prompt constraints (soft) and control-plane guardrails (hard).

#### Scenario: Agent declares milestone progress
- **WHEN** an autonomous agent completes a meaningful milestone within its role-scoped work plan
- **THEN** the agent SHALL publish a structured `session_progress_signals` record containing the milestone name, completed items, next step, and verifiable evidence (file paths, test results, or command output)
- **AND** the progress signal is emitted as a team-level SSE event visible to the observatory dashboard

#### Scenario: Agent escalates a blocking condition
- **WHEN** an autonomous agent encounters a dependency or error that it cannot resolve on its own and that prevents further progress on its role
- **THEN** the agent SHALL set `blocked = true` in its progress signal, populate `blocker_reason` with the factual description of what was attempted and what is needed, and set `needs_operator = true` if the resolution requires operator intervention
- **AND** the blocking condition is surfaced in the team observatory as an attention item for the coordinator or operator

#### Scenario: Agent adapts to budget pressure
- **WHEN** the team budget pressure transitions to `CONSERVATIVE` or `CRITICAL`
- **THEN** each autonomous agent SHALL reduce exploratory work, prioritize reaching a verifiable completion checkpoint, and reuse previously gathered evidence where applicable
- **AND** the agent SHALL NOT silently exceed its session budget limits

#### Scenario: Agent completes its role with evidence
- **WHEN** an autonomous agent reaches its role completion criteria
- **THEN** the completion declaration SHALL include specific attestation evidence such as modified file paths, test results, or command execution output
- **AND** normal acceptance evaluation (budget/schema/optional human approval) applies before the run is marked completed

#### Scenario: Agent does not repeat active-status heartbeat
- **WHEN** an autonomous agent is actively executing work but has not reached a new milestone
- **THEN** the agent SHALL NOT emit redundant progress signals or heartbeat messages claiming continued activity
- **AND** the observatory relies on execution events (tool calls, LLM calls) to infer liveness between milestones

#### Scenario: Coordination messages are directed and concise
- **WHEN** an autonomous agent sends a message to another session in the team
- **THEN** the message SHALL be addressed to a specific, explicit recipient (no broadcast or `@all`)
- **AND** the message content SHALL be brief and directly relevant to the recipient's role task
- **AND** the message SHALL pass through the collaboration service's anti-abuse guardrails (idempotency, no self-send, no cross-container, rate limits)

## MODIFIED Requirements

### Requirement: Staged parallel autonomous execution
An autonomous team SHALL dispatch all eligible roles in a dependency-free activation stage concurrently and SHALL not dispatch a dependent stage until every role in every declared predecessor stage has completed successfully. When the team container is paused, no new stages SHALL be dispatched and already-running stages SHALL be allowed to complete their current invocation; upon resume, the system SHALL re-evaluate stage dependencies before dispatching eligible stages. A stopped team terminates all in-flight dispatch permanently.

#### Scenario: Entry stage contains multiple roles
- **WHEN** an autonomous team starts and its entry stage has multiple enabled roles
- **THEN** every eligible entry-stage run is submitted once without waiting for its peers

#### Scenario: Dependent stage is waiting
- **WHEN** any role in a predecessor stage is still non-terminal or did not complete successfully
- **THEN** runs in its dependent stage remain pending and are not dispatched

#### Scenario: Predecessors complete successfully
- **WHEN** every enabled role in all prerequisite stages completes successfully
- **THEN** the next stage is dispatched once and its eligible roles run in parallel

#### Scenario: Team container is paused during autonomous execution
- **WHEN** an operator pauses the team container while autonomous stages are in progress
- **THEN** already-running roles complete their current LLM invocation but do not start new tool calls or iteration cycles
- **AND** queued or pending roles in dependent stages are not dispatched while the container remains paused
- **AND** the dispatch loop respects the container paused state and suspends stage-progression evaluation

#### Scenario: Team container is resumed after pause
- **WHEN** an operator resumes a previously paused autonomous team container
- **THEN** the system re-evaluates the completion status of all stages and their predecessor dependencies
- **AND** any stage whose predecessors have all completed successfully is dispatched with its eligible roles running concurrently
- **AND** the dispatch loop resumes normal stage-progression evaluation as defined in the preset-stage configuration

#### Scenario: Team container is stopped during autonomous execution
- **WHEN** an operator stops the team container while autonomous stages are in progress
- **THEN** all in-flight runs are cancelled, all pending dependent-stage runs are permanently discarded, and the container transitions to `completed`
- **AND** no further autonomous dispatch occurs for the stopped container
