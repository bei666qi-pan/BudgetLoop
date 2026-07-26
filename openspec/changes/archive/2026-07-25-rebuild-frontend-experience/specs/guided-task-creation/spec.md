## ADDED Requirements

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
