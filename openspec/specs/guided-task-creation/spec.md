# guided-task-creation Specification

## Purpose

Define the guided, safe, and retryable task-creation experience while preserving the existing API contract.

## Requirements

### Requirement: Guided task setup
The task creation route SHALL group task intent, workspace and safety, and budget configuration into an understandable sequence while keeping all required fields reviewable before submission.

#### Scenario: Operator configures a standard task
- **WHEN** the operator supplies a task name, description, workspace, template, strategy, and budget
- **THEN** the interface presents the configuration in a clear hierarchy and allows the operator to review it before starting the task

### Requirement: Helpful defaults and budget presets
The creation experience SHALL provide safe existing defaults and understandable budget presets or guidance, while allowing every budget limit supported by the current API request to be edited.

#### Scenario: Operator selects a budget preset
- **WHEN** a preset is selected
- **THEN** the token, wall-time, active-runtime, call-count, cost, and parallel-call values update to the preset values and remain individually editable

#### Scenario: Operator chooses dynamic strategy
- **WHEN** the dynamic budget strategy is selected
- **THEN** the interface explains that BudgetLoop may reallocate effort under pressure without implying that configured hard limits can be exceeded

### Requirement: Inline validation and submission safety
The creation experience SHALL validate required and numeric inputs before submission, prevent duplicate in-flight submissions, and use an idempotency key with the existing create-task API.

#### Scenario: Required input is invalid
- **WHEN** the operator attempts to submit missing required text, an invalid workspace, or a non-positive required budget value
- **THEN** submission is blocked and the relevant field receives an actionable error message

#### Scenario: Task creation succeeds
- **WHEN** the API accepts a valid task request
- **THEN** the interface navigates to the returned run and does not submit a second request

#### Scenario: Task creation fails
- **WHEN** the API rejects or cannot complete the request
- **THEN** the entered configuration remains available and a trustworthy retryable error is shown

### Requirement: Explicit safety control
The creation experience SHALL present the high-risk approval setting as an explicit safety decision with plain-language consequences and SHALL transmit it unchanged in the current API payload.

#### Scenario: Approval is required
- **WHEN** the operator enables high-risk approval
- **THEN** the review state clearly indicates that qualifying actions will wait for human approval

### Requirement: Draft-backed configuration review
The creation experience SHALL accept a server-validated conversational setup draft, show every persisted or safety-relevant value before submission, and allow bounded edits without forcing the operator through the full advanced form.

#### Scenario: Ready draft is reviewed
- **WHEN** the draft service returns a ready setup
- **THEN** the interface shows the goal, acceptance criteria, selected team and roles, aggregate starter limits, approval state, execution readiness, and folder policy in one review surface

#### Scenario: Operator edits a suggested field
- **WHEN** the operator changes an allowed title, goal, criterion, trusted preset, optional role, bounded budget, or folder choice
- **THEN** validation and aggregate summaries update before confirmation and the server revalidates the submitted values

#### Scenario: Advanced configuration is requested
- **WHEN** the operator opens progressive disclosure from the review surface
- **THEN** the existing detailed role, engine, budget, workspace, and preset controls remain available without creating a second draft

### Requirement: Permission-aware final confirmation
The final creation action SHALL summarize the effective host path, folder access mode, worktree policy, approval setting, and aggregate hard limits, and SHALL remain disabled while a required permission acknowledgement or validation fact is missing.

#### Scenario: Isolation is retained
- **WHEN** the operator keeps the default isolated mode
- **THEN** the review states that the original host folder will not be directly modified and no writable-folder acknowledgement is required

#### Scenario: Writable access is selected
- **WHEN** the operator selects full access to a project folder
- **THEN** the review names the canonical folder, explains direct writes including `.git`, explains per-session worktrees, and requires an explicit acknowledgement before confirmation

#### Scenario: Writable selection changes
- **WHEN** the operator changes the selected folder or folder access mode
- **THEN** any previous high-risk acknowledgement is cleared and must be made again for the new effective selection
