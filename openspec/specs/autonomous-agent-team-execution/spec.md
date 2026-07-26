# autonomous-agent-team-execution Specification

## Purpose

Define opt-in staged parallel execution and auditable automatic Handoff for autonomous preset Agent Teams.

## Requirements

### Requirement: Explicit autonomous team selection
The preset-team creation flow SHALL let an operator choose `guided` or `autonomous` mode before creating a team, SHALL default existing clients to `guided`, and SHALL persist the effective mode in the public applied snapshot and each created run configuration.

#### Scenario: Operator enables autonomous mode
- **WHEN** an operator confirms a valid preset team with autonomous mode selected
- **THEN** the created team and all enabled runs record autonomous mode without changing folder access, approval, engine, or workspace-policy requirements

#### Scenario: Existing client creates a team
- **WHEN** a compatible client omits the mode field
- **THEN** the server creates the existing guided behavior and records the guided default

### Requirement: Staged parallel autonomous execution
An autonomous team SHALL dispatch all eligible roles in a dependency-free activation stage concurrently and SHALL not dispatch a dependent stage until every role in every declared predecessor stage has completed successfully.

#### Scenario: Entry stage contains multiple roles
- **WHEN** an autonomous team starts and its entry stage has multiple enabled roles
- **THEN** every eligible entry-stage run is submitted once without waiting for its peers

#### Scenario: Dependent stage is waiting
- **WHEN** any role in a predecessor stage is still non-terminal or did not complete successfully
- **THEN** runs in its dependent stage remain pending and are not dispatched

#### Scenario: Predecessors complete successfully
- **WHEN** every enabled role in all prerequisite stages completes successfully
- **THEN** the next stage is dispatched once and its eligible roles run in parallel

### Requirement: Autonomous role planning and handoff
Autonomous runs SHALL receive a trusted coordination instruction to derive a role-scoped work plan, publish concise factual output, remain within their assigned workspace, and finish through normal acceptance evaluation. On successful source-stage completion, the system SHALL create auditable recipient-scoped Handoff records from public output for each newly eligible downstream role.

#### Scenario: Autonomous source stage completes
- **WHEN** an autonomous role completes and a later stage depends on its stage
- **THEN** the system stores one attributable handoff per downstream recipient without exposing private context or hidden reasoning

#### Scenario: Handoff is delivered
- **WHEN** the released downstream role begins its next worker iteration
- **THEN** the existing inbox delivery contract presents the queued handoff with immutable source and delivery state

#### Scenario: Source stage fails
- **WHEN** an autonomous source role fails, is cancelled, or exhausts a bounded budget
- **THEN** no dependent stage is automatically released and the team retains an actionable attention state
